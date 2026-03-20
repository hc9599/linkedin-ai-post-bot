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
    # TOPIC ANGLE: rotate daily so posts cover different dimensions
    # of the .NET/C# world and never fixate on one area
    # ---------------------------------------------------------------
    topic_angles = {
        0: {  # Monday — language & runtime
            "focus": "Focus on the C# language itself or the .NET runtime — new language features, "
                     "syntax improvements, performance characteristics, type system changes, or how "
                     "the language is evolving compared to other ecosystems.",
            "avoid": "Do not frame this through cloud migration or enterprise storage unless the article directly covers it."
        },
        1: {  # Tuesday — tooling & developer experience
            "focus": "Focus on developer tooling, IDE support, SDK improvements, build systems, "
                     "NuGet, debugging experience, or anything that affects the day-to-day workflow "
                     "of a .NET developer.",
            "avoid": "Do not default to cloud or compliance framing. This is about the developer experience."
        },
        2: {  # Wednesday — architecture & patterns
            "focus": "Focus on software architecture, design patterns, system design decisions, "
                     "or engineering tradeoffs relevant to .NET backend systems — async patterns, "
                     "dependency injection, modular design, scalability, or API design.",
            "avoid": "Keep it architectural, not product-specific. No cloud migration unless the article is explicitly about it."
        },
        3: {  # Thursday — ecosystem & community
            "focus": "Focus on where C# and .NET sit in the broader software development landscape — "
                     "how it competes with or complements other languages, adoption trends, open source "
                     "momentum, community contributions, or what makes .NET a strong choice in 2025.",
            "avoid": "No enterprise storage or compliance framing. Think positioning and community, not internal workflows."
        },
        4: {  # Friday — enterprise & infrastructure (original persona)
            "focus": "Focus on enterprise infrastructure concerns — cloud migration, data pipelines, "
                     "file system integrations, security and permissions, compliance automation, or "
                     "scalable .NET backend patterns for large-scale systems.",
            "avoid": "This is the one day to draw on the enterprise storage persona. Keep it grounded in real system challenges."
        },
        5: {  # Saturday — performance & internals
            "focus": "Focus on .NET performance, memory management, Span<T>, benchmarking, GC tuning, "
                     "JIT behaviour, or any low-level runtime internals that affect how .NET applications run.",
            "avoid": "No high-level cloud or business framing. Get into the technical weeds."
        },
        6: {  # Sunday — new releases & future direction
            "focus": "Focus on what is new or coming — .NET release previews, C# version roadmap, "
                     "upcoming features, deprecations, or the direction Microsoft and the community "
                     "are taking the platform.",
            "avoid": "Do not frame it as a product announcement. Have an opinion about the direction, not just a summary of it."
        },
    }

    angle = topic_angles[weekday]

    # ---------------------------------------------------------------
    # OPENERS
    # ---------------------------------------------------------------
    openers = [
        "Open with a one-sentence hot take that a senior .NET dev would either strongly agree or disagree with. No hedging.",
        "Open with a blunt, slightly frustrated observation about something in the .NET ecosystem that wastes peoples time.",
        "Open with a direct observation about something most .NET developers do out of habit that deserves a second look.",
        "Open with a question that a junior dev would never think to ask but a senior dev loses sleep over.",
        "Open mid-thought, as if continuing a conversation already in progress. No setup, no intro — just the insight.",
        "Open with a specific technical opinion — not a feeling, not a story, just a clear stance on how something should or should not be done.",
    ]

    # ---------------------------------------------------------------
    # ENDINGS
    # ---------------------------------------------------------------
    endings = [
        "End with a casual question to the audience — one line, conversational, not formal.",
        "End with a short punchy statement that gives your opinion and leaves no question. No call to action.",
        "End with a challenge: tell the reader one concrete thing to go and check in their own codebase.",
        "End by zooming out — one sentence connecting the technical point to something broader about how teams or systems fail.",
        "End with a dry, slightly self-aware observation about how long it took you to learn this.",
    ]

    # ---------------------------------------------------------------
    # FORMATS
    # ---------------------------------------------------------------
    formats = [
        "Write it as one flowing block of text, no line breaks between thoughts. Every sentence ends with a full stop.",
        "Write it as short punchy lines, each on its own line. Every line must be a complete sentence with a full stop. No fragments.",
        "Write two short paragraphs. First one sets up the problem, second one is your take. Proper sentences throughout.",
        "Write it as a single paragraph that builds to one sharp final sentence.",
    ]

    # ---------------------------------------------------------------
    # WORD COUNTS
    # ---------------------------------------------------------------
    word_counts = [
        "between 80 and 100 words — keep it tight, every sentence must earn its place",
        "between 100 and 130 words — concise but with room for one concrete example",
        "between 130 and 160 words — enough space to build an argument, not a word more",
        "between 160 and 180 words — use the length only if the insight genuinely needs it",
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
    ]
    banned_str = "\n".join(f"- {p}" for p in banned_phrases)

    prompt = f"""Today is {today}. You are ghostwriting a LinkedIn post for a senior C#/.NET developer.

Today's focus: {angle['focus']}
{angle['avoid']}

Choose ONE article from the list below that best fits today's focus angle. If no article is a direct match, pick the one whose underlying concept maps closest to today's angle.

Each article includes a summary. Read it. The post must reference at least one specific detail, behaviour, or finding from that summary — not just the title. A post that could have been written without reading the summary will be rejected.

Here are the articles:
{posts_text}

STEP 1 — Choose one topic:
Output your choice on the very first line as: Chosen topic: [article title]

STEP 2 — Write the LinkedIn post about ONLY that topic.

Post rules:
- {chosen_opener}
- {chosen_ending}
- {chosen_format}
- Write like a real person typing, not like someone drafting a press release
- Confident and direct — peer to peer, not teacher to student
- Have an actual opinion — agree, disagree, push back, or add a take. Do not just describe what the article says.
- No invented personal anecdotes. No "I recall when..." or "we once had a situation where...".
- No emojis. Not a single one. No smiley faces, no symbols, nothing.
- No markdown formatting
- {chosen_word_count}
- The hashtags must be on their own line at the very end, exactly as: #CSharp #DotNet #Programming #SoftwareDevelopment

Banned phrases — do not use any of these, even loosely paraphrased:
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
