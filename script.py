import requests
import os
import random
import time
from datetime import datetime
import re

def clean_markdown(text):
    # Strip the "Chosen topic:" debug line from the model's output
    text = re.sub(r'^Chosen topic:.*\n?', '', text, flags=re.IGNORECASE)
    
    # Remove bold **text** or __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    
    # Remove italic *text* or _text_ (word-boundary guard to protect hashtags)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.*?)_(?!\w)', r'\1', text)
    
    # Remove headers ### ## # — only at start of line AND followed by a space
    # This protects inline hashtags like #CSharp which have no space after #
    text = re.sub(r'^(#{1,6})\s+', '', text, flags=re.MULTILINE)
    
    # Remove bullet points - or * at start of line
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    
    # Remove numbered lists 1. 2. 3.
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove horizontal rules ---
    text = re.sub(r'---+', '', text)
    
    # Remove backticks for inline code
    text = re.sub(r'`(.*?)`', r'\1', text)
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # Remove emojis and unicode symbols — but preserve plain ASCII (including # in C#)
    # Targets: emoticons, symbols, pictographs, transport, flags, supplemental symbols
    text = re.sub(
        r'[\U0001F600-\U0001F64F'  # emoticons
        r'\U0001F300-\U0001F5FF'   # symbols & pictographs
        r'\U0001F680-\U0001F6FF'   # transport & map
        r'\U0001F700-\U0001F77F'   # alchemical symbols
        r'\U0001F780-\U0001F7FF'   # geometric shapes extended
        r'\U0001F800-\U0001F8FF'   # supplemental arrows
        r'\U0001F900-\U0001F9FF'   # supplemental symbols & pictographs
        r'\U0001FA00-\U0001FA6F'   # chess symbols
        r'\U0001FA70-\U0001FAFF'   # symbols and pictographs extended-A
        r'\U00002702-\U000027B0'   # dingbats
        r'\U000024C2-\U0001F251'   # enclosed characters
        r']+',
        '',
        text
    )
    
    # Strip the word "hashtag" that some models write before # signs
    # e.g. "hashtag#CSharp" → "#CSharp"
    text = re.sub(r'\bhashtag#', '#', text, flags=re.IGNORECASE)

    # Clean up extra blank lines (more than 2 in a row)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def fetch_reddit_posts():
    """
    Pulls hot/top posts from r/csharp and r/dotnet using Reddit's official OAuth API.
    Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.

    To get these (free, takes 2 minutes):
    1. Go to https://www.reddit.com/prefs/apps
    2. Click 'Create another app' at the bottom
    3. Name it anything, select 'script', set redirect URI to http://localhost:8080
    4. Copy the client ID (under the app name) and secret
    5. Set as env vars: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET
    """
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not set — skipping Reddit.")
        print("See instructions in fetch_reddit_posts() to set these up in 2 minutes.")
        return []

    # Step 1 — get an OAuth access token using client credentials flow
    print("Authenticating with Reddit OAuth...")
    try:
        token_response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={
                "User-Agent": "linkedin-dotnet-bot/2.0 by /u/your_reddit_username"
            },
            timeout=10
        )
        if token_response.status_code != 200:
            print(f"Reddit OAuth failed: {token_response.status_code} — {token_response.text}")
            return []

        access_token = token_response.json().get("access_token")
        if not access_token:
            print("Reddit OAuth: no access token in response")
            return []

        print("Reddit OAuth: authenticated successfully")

    except Exception as e:
        print(f"Reddit OAuth error: {e}")
        return []

    # Step 2 — use the token to fetch posts from the OAuth API endpoint
    session = requests.Session()
    session.headers.update({
        "Authorization": f"bearer {access_token}",
        "User-Agent": "linkedin-dotnet-bot/2.0 by /u/your_reddit_username",
    })

    subreddits = ["csharp", "dotnet"]
    sort = "top" if datetime.now().weekday() % 2 == 0 else "hot"
    time_filter = "week" if sort == "top" else ""

    posts = []

    for subreddit in subreddits:
        if sort == "top":
            url = f"https://oauth.reddit.com/r/{subreddit}/top?t={time_filter}&limit=25"
        else:
            url = f"https://oauth.reddit.com/r/{subreddit}/hot?limit=25"

        print(f"Fetching Reddit r/{subreddit} ({sort})...")

        try:
            response = session.get(url, timeout=15)

            if response.status_code != 200:
                print(f"  r/{subreddit}: error {response.status_code} — skipping")
                continue

            data = response.json()
            children = data.get("data", {}).get("children", [])
            print(f"  r/{subreddit}: {len(children)} posts fetched")

            for child in children:
                post = child.get("data", {})

                if post.get("stickied"):
                    continue
                if post.get("is_video") or post.get("post_hint") == "image":
                    continue
                title = post.get("title", "")
                if len(title) < 20:
                    continue

                summary = post.get("selftext", "")[:500].strip()
                if not summary:
                    summary = post.get("url", "")

                posts.append({
                    "title": title,
                    "link": f"https://reddit.com{post.get('permalink', '')}",
                    "summary": summary,
                    "reactions": post.get("score", 0),
                    "source": f"r/{subreddit}"
                })

        except Exception as e:
            print(f"  Reddit fetch error for r/{subreddit}: {e}")
            continue

        time.sleep(1)

    print(f"Total Reddit posts collected: {len(posts)}")
    return posts


def fetch_dotnet_blog_posts():
    """
    Pulls latest posts from the official Microsoft .NET Dev Blog RSS feed.
    Uses feedparser to parse the RSS. Falls back gracefully if unavailable.
    """
    try:
        import feedparser
    except ImportError:
        print("feedparser not installed — skipping .NET blog. Run: pip install feedparser")
        return []

    feed_url = "https://devblogs.microsoft.com/dotnet/feed/"
    print(f"Fetching .NET Dev Blog RSS...")

    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries[:20]
        print(f"  .NET blog: {len(entries)} entries fetched")
    except Exception as e:
        print(f".NET blog fetch error: {e}")
        return []

    posts = []
    for entry in entries:
        title = entry.get("title", "")
        if len(title) < 20:
            continue

        # Strip HTML tags from summary, collapse whitespace, take 500 chars
        # More content here means the model can write something specific rather than generic
        raw_summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))
        raw_summary = re.sub(r"\s+", " ", raw_summary).strip()
        summary = raw_summary[:500]

        posts.append({
            "title": title,
            "link": entry.get("link", ""),
            "summary": summary,
            "reactions": 0,  # RSS has no reaction count — treated equally in selection
            "source": ".NET Dev Blog"
        })

    print(f"Total .NET blog posts collected: {len(posts)}")
    return posts


def fetch_posts():
    """
    Combines Reddit and .NET Dev Blog sources.
    Picks a balanced mix: 3 from Reddit (community signal) + 2 from .NET blog (authority).
    Falls back cleanly if either source is unavailable.
    """
    reddit_posts = fetch_reddit_posts()
    blog_posts = fetch_dotnet_blog_posts()

    # Sort Reddit posts by score so we pick from the most upvoted
    reddit_posts.sort(key=lambda x: x["reactions"], reverse=True)

    # Shuffle blog posts since they have no score signal
    random.shuffle(blog_posts)

    # Take top posts from each source
    selected_reddit = reddit_posts[:10]
    selected_blog = blog_posts[:10]

    # Shuffle each bucket individually then interleave
    random.shuffle(selected_reddit)
    random.shuffle(selected_blog)

    combined = selected_reddit[:3] + selected_blog[:2]

    # If one source failed entirely, fill from the other
    if not combined:
        combined = (reddit_posts + blog_posts)[:5]

    random.shuffle(combined)
    final = combined[:5]

    print(f"\nFinal selected posts ({len(final)}):")
    for p in final:
        print(f"  - [{p['reactions']} upvotes | {p['source']}] {p['title']}")

    return final


def generate_linkedin_post(posts):
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    today = datetime.now().strftime("%A, %B %d")
    weekday = datetime.now().weekday()  # 0=Mon, 6=Sun

    posts_text = "\n\n".join([
        f"[{p['source']}] {p['title']} ({p['reactions']} upvotes)\n{p['summary']}"
        for p in posts
    ])

    # ---------------------------------------------------------------
    # TOPIC ANGLE: rotate daily across different .NET/C# dimensions
    # Each angle has a focus, an audience signal, and an avoid rule
    # ---------------------------------------------------------------
    topic_angles = {
        0: {  # Monday — language & runtime
            "focus": "Focus on C# language features or .NET runtime improvements — new syntax, "
                     "type system changes, performance characteristics, or how the language is "
                     "evolving. Explain what the change means in practice, not just what it is.",
            "audience_signal": "Recruiting managers should come away thinking: this person understands "
                               "the platform deeply and keeps up with where it is going. Developers "
                               "should feel like a peer is sharing something genuinely useful.",
            "avoid": "Do not reduce it to a feature announcement. Connect it to real decisions a developer makes."
        },
        1: {  # Tuesday — tooling & developer experience
            "focus": "Focus on developer tooling, IDE improvements, SDK changes, debugging experience, "
                     "NuGet, or build systems. Describe the practical impact on daily development work.",
            "audience_signal": "Recruiting managers should see evidence of someone who cares about "
                               "engineering craft and productivity, not just shipping. Developers should "
                               "find something they can actually use or think about today.",
            "avoid": "Do not make it sound like a product review. Frame it around what changes in your workflow and why that matters."
        },
        2: {  # Wednesday — architecture & engineering decisions
            "focus": "Focus on software architecture, design patterns, or engineering tradeoffs in .NET — "
                     "async patterns, dependency injection, modular design, scalability decisions, "
                     "or how to structure systems that are built to last.",
            "audience_signal": "Recruiting managers should see a developer who thinks beyond features — "
                               "someone who reasons about systems and tradeoffs. Developers should find "
                               "a concrete angle they can apply or debate.",
            "avoid": "No vague architecture talk. Name a specific pattern, tradeoff, or decision point."
        },
        3: {  # Thursday — C# positioning & career perspective
            "focus": "Focus on where C# and .NET stand in the broader software industry — how it compares "
                     "to other languages, why developers choose it, what the community is doing, or what "
                     "makes it a strong platform choice for serious backend work in the current market.",
            "audience_signal": "Recruiting managers should see someone who understands the market and can "
                               "articulate why their stack matters. Developers should find a perspective "
                               "they can agree or disagree with — something worth discussing.",
            "avoid": "Do not write a generic 'C# is great' post. Take a position on something specific — adoption, community, competition, or direction."
        },
        4: {  # Friday — enterprise & infrastructure
            "focus": "Focus on enterprise-scale .NET concerns — cloud infrastructure, data pipelines, "
                     "file system integrations, security and permissions, compliance, or building "
                     "systems that handle large volumes reliably. Be specific about what breaks at scale.",
            "audience_signal": "Recruiting managers should see someone with genuine enterprise experience, "
                               "not someone who has only built tutorials. Developers working at scale "
                               "should recognise the problem being described.",
            "avoid": "Do not reference NAS, SMB, or internal product details. Keep it generalisable to any senior .NET developer working on backend infrastructure."
        },
        5: {  # Saturday — performance & internals
            "focus": "Focus on .NET performance — Span<T>, memory management, GC behaviour, benchmarking, "
                     "JIT compilation, or low-level runtime details. Explain why it matters and what "
                     "a developer should actually do with the information.",
            "audience_signal": "Recruiting managers should see someone who cares about performance at a "
                               "level most developers do not. Developers should learn something concrete "
                               "or be challenged to think about performance differently.",
            "avoid": "Do not just name a concept. Show the implication — what goes wrong without it, or what gets better with it."
        },
        6: {  # Sunday — new releases & future direction
            "focus": "Focus on what is new or coming in .NET — release previews, the C# roadmap, "
                     "upcoming features, or the direction the platform is heading. Evaluate what "
                     "the changes actually mean for developers, not just what they are.",
            "audience_signal": "Recruiting managers should see someone who stays current and thinks "
                               "critically about platform direction, not just someone who reads release notes. "
                               "Developers should get a useful filter on what to pay attention to.",
            "avoid": "Do not write a changelog summary. Evaluate, filter, or push back on what is worth caring about."
        },
    }

    angle = topic_angles[weekday]

    # ---------------------------------------------------------------
    # OPENERS: entries that signal expertise to both technical and non-technical readers
    # ---------------------------------------------------------------
    openers = [
        "Open with a clear statement of what the topic is and why it matters — no jargon without explanation, "
        "but do not oversimplify. A recruiting manager should understand the stakes; a developer should respect the framing.",

        "Open with a contrast: what most teams or developers do by default, versus what the evidence or "
        "experience suggests is better. Keep it specific — name the default behaviour, not just 'most people'.",

        "Open with a direct, confident observation about a real tradeoff or tension in the topic. "
        "State your position clearly in the first sentence. Do not hedge.",

        "Open with a question that surfaces something developers have faced but rarely discussed explicitly. "
        "Make it specific enough that a developer immediately knows what you mean, "
        "and clear enough that a non-developer can follow the direction of the post.",

        "Open by naming a specific behaviour, pattern, or change — then in the next sentence, "
        "explain what makes it significant. Do not assume the reader already knows why it matters.",

        "Open with a short scenario (2 sentences max) that sets up the problem. "
        "It should be recognisable to developers and understandable to anyone who has worked with software teams.",
    ]

    # ---------------------------------------------------------------
    # ENDINGS: closes that invite engagement from both audiences
    # ---------------------------------------------------------------
    endings = [
        "End with a single genuine question that invites both developers and non-developers to share "
        "a perspective. Not rhetorical — actually curious about how others have dealt with this.",

        "End with your clearest takeaway in one sentence. State it plainly so a non-developer "
        "can repeat it to someone else and have it still make sense.",

        "End with a concrete action or check — one specific thing a developer can do, "
        "explained clearly enough that a manager understands why it is worth doing.",

        "End by connecting the technical point to a broader engineering or team dynamic — "
        "one sentence that shows you think about the human side of the work, not just the code.",

        "End with an honest, grounded observation about how common it is to get this wrong, "
        "or how long it takes most teams to notice the problem.",
    ]

    # ---------------------------------------------------------------
    # FORMATS: structures that work for both technical and non-technical readers
    # ---------------------------------------------------------------
    formats = [
        "Two paragraphs. First paragraph (2-3 sentences): explain the context or problem clearly enough "
        "that a non-developer can follow it. Second paragraph (3-4 sentences): give your specific take, "
        "name what is interesting or underappreciated about it, and explain the practical implication. "
        "Every sentence ends with a full stop.",

        "Three short paragraphs, 2-3 sentences each. "
        "First: set up the situation or problem. "
        "Second: explain what most people miss or get wrong about it. "
        "Third: your specific take and what it means in practice. "
        "Every sentence ends with a full stop. No bullet points.",

        "One flowing paragraph of 6-8 sentences. "
        "Open with the context, move to the technical detail, explain why it matters to someone "
        "building real systems, and close with a clear point. "
        "Write so a smart non-developer can follow the logic even if they miss the technical details.",

        "Short lines, one sentence each, building toward a conclusion. "
        "Start with the broad context (1-2 lines), move to the specific technical point (2-3 lines), "
        "then explain the implication clearly (2 lines). "
        "Every line is a complete sentence. Full stops throughout. No fragments. No dashes as sentence starters.",
    ]

    # ---------------------------------------------------------------
    # WORD COUNTS: descriptive range — enough space to explain, not enough to ramble
    # ---------------------------------------------------------------
    word_counts = [
        "between 130 and 160 words — enough to explain the context and make a clear point",
        "between 150 and 180 words — room for a specific example or concrete detail that grounds the insight",
        "between 160 and 200 words — use the space to build a proper argument: context, insight, implication",
        "between 120 and 150 words — tight and descriptive: every sentence should add something a reader could not infer themselves",
    ]

    chosen_opener = random.choice(openers)
    chosen_ending = random.choice(endings)
    chosen_format = random.choice(formats)
    chosen_word_count = random.choice(word_counts)

    # ---------------------------------------------------------------
    # BANNED PHRASES
    # ---------------------------------------------------------------
    banned_phrases = [
        "production taught me", "something I keep coming back to",
        "a pattern I've seen break teams", "we've all been there",
        "after years of", "hard-won", "battle-tested",
        "I just learned", "I recently discovered", "building my first",
        "I was surprised to find", "it's all about", "straightforward",
        "seamless", "dive into", "delve into", "I stumbled upon",
        "robust", "game-changer", "the key to", "the importance of",
        "in today's world", "in the world of", "navigating",
        "ever-evolving", "tech landscape", "as developers", "as a developer",
        "let that sink in", "food for thought", "it's worth noting",
        "at the end of the day", "take it to the next level",
        "I'm excited about", "I'm looking forward to",
        "I recall a particular", "I remember when",
        "highlighting the need for", "I'm thrilled", "noteworthy",
        "worth exploring", "it's a great time to", "can't wait to",
        "this is a must", "ultimate guide", "reduce repetitive",
        "exploring how", "looking forward to trying",
        "could have saved us", "hit a snag",
        "good reminder", "top of mind", "proactive approach",
        "always top of mind", "taking a proactive",
        "warrant a closer look", "without a second thought",
        "should always be", "most critical aspect",
        "cannot be overstated", "goes without saying",
        "in conclusion", "to summarise", "as we know",
    ]
    banned_str = "\n".join(f"- {p}" for p in banned_phrases)

    prompt = f"""Today is {today}. You are ghostwriting a LinkedIn post for a senior C#/.NET developer with 5+ years of backend and enterprise experience.

TARGET AUDIENCE — write so both of these people find value in the post:
1. Recruiting managers: they are not developers. They are assessing whether this person thinks clearly, communicates well, and has genuine depth. They should come away thinking "this person knows what they are doing."
2. Developer community: experienced .NET and C# developers. They should find something specific, accurate, and worth engaging with — a real point they can agree with, push back on, or learn from.

The post must be descriptive enough that a non-developer can follow the point, and specific enough that an experienced developer respects it. Avoid jargon without explanation. Avoid oversimplification. Find the level where both audiences get something out of it.

TODAY'S ANGLE:
{angle['focus']}

AUDIENCE SIGNAL FOR TODAY:
{angle['audience_signal']}

{angle['avoid']}

Choose ONE article from the list below that best fits today's angle. Read the summary carefully. The post must reference at least one specific detail from the summary — not just the title. A post that could have been written from the title alone will be rejected.

Here are the articles:
{posts_text}

STEP 1 — Output on the first line: Chosen topic: [article title]

STEP 2 — Write the LinkedIn post about ONLY that topic.

Post structure and style:
- {chosen_opener}
- {chosen_ending}
- {chosen_format}
- Tone: clear and direct, confident without being arrogant, peer-level not lecture-level
- Have a specific point of view — do not just describe what the article says
  BAD: "This is a good reminder that security should be top of mind." (no stance, obvious)
  BAD: "This feature is worth paying attention to." (vague, non-committal)
  GOOD: "Most teams apply these updates without reading the changelog — and that is exactly how silent regressions slip in."
  GOOD: "The new collection expression syntax looks minor, but it quietly removes one of the most common sources of unnecessary allocations in everyday C# code."
- No invented anecdotes. No "I recall when..." or fabricated scenarios.
- No emojis. No smiley faces. No symbols.
- No markdown formatting.
- {chosen_word_count}
- Hashtags on their own line at the very end, exactly: #CSharp #DotNet #Programming #SoftwareDevelopment

Banned phrases — do not use any of these:
{banned_str}
"""

    for attempt in range(3):
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.95,
                "top_p": 0.92,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.4,
            }
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]

        print(f"Groq attempt {attempt + 1} failed: {response.status_code} - {response.text}")
        time.sleep(5)

    raise Exception(f"Groq API failed after 3 attempts: {response.text}")


def generate_image_prompt(post_content):
    """
    Asks Groq to generate a clean image prompt based on the post content.
    Returns a short descriptive prompt suitable for Pollinations.
    """
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

    system = (
        "You generate image prompts for LinkedIn tech posts. "
        "Output only the image prompt — no explanation, no preamble, no quotes. "
        "Style: clean flat illustration, dark background, subtle code or tech motif. "
        "No people, no faces, no text in the image. "
        "Keep it abstract and professional — suitable for a developer's LinkedIn post."
    )

    user = (
        f"Based on this LinkedIn post, write a short image generation prompt (max 30 words):\n\n"
        f"{post_content}"
    )

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "temperature": 0.7,
                "max_tokens": 80,
            }
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Image prompt generation failed: {e}")

    return None


def generate_image(image_prompt):
    """
    Generates an image via Pollinations AI (free, no API key needed).
    Returns the image bytes or None on failure.
    """
    import urllib.parse

    encoded = urllib.parse.quote(image_prompt)
    # nologo=true removes the Pollinations watermark, enhance=true applies quality boost
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=627&nologo=true&enhance=true&model=flux"

    print(f"Generating image with prompt: {image_prompt}")
    print("Waiting for image generation (this can take 15-30s)...")

    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image"):
            print(f"Image generated — {len(response.content) // 1024}KB")
            return response.content
        else:
            print(f"Image generation failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"Image generation error: {e}")
        return None


def upload_image_to_linkedin(image_bytes, token, person_id):
    """
    Uploads image bytes to LinkedIn using the Assets API.
    Returns the asset URN needed to attach the image to a post.
    LinkedIn requires a two-step process: register upload → upload binary.
    """
    headers_base = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Step 1: Register the upload and get an upload URL
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": f"urn:li:person:{person_id}",
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }
            ]
        }
    }

    reg_response = requests.post(
        register_url,
        headers={**headers_base, "Content-Type": "application/json"},
        json=register_payload
    )

    if reg_response.status_code != 200:
        raise Exception(f"LinkedIn image register failed: {reg_response.status_code} - {reg_response.text}")

    reg_data = reg_response.json()
    upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset = reg_data["value"]["asset"]

    print(f"LinkedIn upload URL obtained. Asset: {asset}")

    # Step 2: Upload the actual image bytes
    upload_response = requests.put(
        upload_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
        },
        data=image_bytes
    )

    if upload_response.status_code not in [200, 201]:
        raise Exception(f"LinkedIn image upload failed: {upload_response.status_code} - {upload_response.text}")

    print("Image uploaded to LinkedIn successfully.")
    return asset


def post_to_linkedin(content, image_bytes=None):
    LINKEDIN_TOKEN = os.environ.get("LINKEDIN_TOKEN")
    LINKEDIN_PERSON_ID = os.environ.get("LINKEDIN_PERSON_ID")

    if not LINKEDIN_TOKEN or not LINKEDIN_PERSON_ID:
        raise ValueError("LinkedIn credentials not set")

    url = "https://api.linkedin.com/v2/ugcPosts"

    headers = {
        "Authorization": f"Bearer {LINKEDIN_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    # If an image was generated, upload it first then attach to the post
    if image_bytes:
        try:
            asset = upload_image_to_linkedin(image_bytes, LINKEDIN_TOKEN, LINKEDIN_PERSON_ID)
            payload = {
                "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": content},
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "media": asset,
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            print("Posting with image...")
        except Exception as e:
            print(f"Image upload failed ({e}) — falling back to text-only post")
            image_bytes = None

    if not image_bytes:
        payload = {
            "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code not in [200, 201]:
        raise Exception(f"LinkedIn API error: {response.status_code} - {response.text}")

    print("Successfully posted to LinkedIn!")
    return response.json()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate and post a LinkedIn update.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print the post without publishing to LinkedIn."
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        help="Skip image generation and post text only."
    )
    args = parser.parse_args()

    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    skip_image = args.no_image or os.environ.get("NO_IMAGE", "").lower() in ("1", "true", "yes")

    if dry_run:
        print("*** DRY RUN MODE — post will NOT be published to LinkedIn ***\n")

    print("Fetching posts from Reddit and .NET Dev Blog...")
    posts = fetch_posts()

    if not posts:
        print("No posts fetched, exiting.")
        return

    print("\nGenerating LinkedIn post with Groq...")
    linkedin_content = generate_linkedin_post(posts)
    print("\nGenerated post (raw):")
    print(linkedin_content)

    print("\nCleaning markdown...")
    linkedin_content = clean_markdown(linkedin_content)

    print("\n" + "=" * 60)
    print("FINAL POST:")
    print("=" * 60)
    print(linkedin_content)
    print("=" * 60)
    print(f"Word count: {len(linkedin_content.split())}")

    # Image generation
    image_bytes = None
    if not skip_image:
        print("\nGenerating image prompt...")
        image_prompt = generate_image_prompt(linkedin_content)
        if image_prompt:
            print(f"Image prompt: {image_prompt}")
            image_bytes = generate_image(image_prompt)
        else:
            print("Could not generate image prompt — skipping image.")
    else:
        print("\nImage generation skipped (--no-image).")

    if dry_run:
        print("\n*** DRY RUN — skipping LinkedIn publish ***")
        if image_bytes:
            # Save image locally so you can preview it in dry run
            img_path = f"dry_run_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(img_path, "wb") as f:
                f.write(image_bytes)
            print(f"Image saved locally for preview: {img_path}")
    else:
        print("\nPosting to LinkedIn...")
        post_to_linkedin(linkedin_content, image_bytes)


if __name__ == "__main__":
    main()
