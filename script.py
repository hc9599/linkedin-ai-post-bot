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
    
    # Remove headers ### ## # — only when # appears at the start of a line
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
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
    Pulls hot posts from r/csharp and r/dotnet using Reddit's free JSON API.
    No API key required for read-only access.
    Rotates between 'hot' and 'top' (week) to vary content across days.
    """
    subreddits = ["csharp", "dotnet"]
    # Alternate between hot and top-of-week based on day
    sort = "top" if datetime.now().weekday() % 2 == 0 else "hot"
    time_filter = "?t=week" if sort == "top" else ""

    headers = {
        "User-Agent": "linkedin-post-bot/1.0 (automated content generator)"
    }

    posts = []

    for subreddit in subreddits:
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json{time_filter}&limit=25"
        print(f"Fetching Reddit r/{subreddit} ({sort})...")

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Reddit r/{subreddit} error: {response.status_code}")
                continue

            data = response.json()
            children = data.get("data", {}).get("children", [])
            print(f"  r/{subreddit}: {len(children)} posts fetched")

            for child in children:
                post = child.get("data", {})

                # Skip stickied mod posts, image/video posts, and very short titles
                if post.get("stickied"):
                    continue
                if post.get("is_video") or post.get("post_hint") == "image":
                    continue
                title = post.get("title", "")
                if len(title) < 20:
                    continue

                # Use selftext as summary if available, else fall back to URL
                # 500 chars gives the model enough to write something specific
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
            print(f"Reddit fetch error for r/{subreddit}: {e}")
            continue

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
    
    posts_text = "\n\n".join([
        f"[{p['source']}] {p['title']} ({p['reactions']} upvotes)\n{p['summary']}"
        for p in posts
    ])

    # ---------------------------------------------------------------
    # OPENERS: rotate so structure never repeats two days in a row
    # ---------------------------------------------------------------
    openers = [
        "Open with a one-sentence hot take that a senior .NET dev would either strongly agree or disagree with. No hedging.",
        "Open with a very short story — one or two sentences — about a specific moment in a production system that went sideways. Make it feel real, not hypothetical.",
        "Open with a direct observation about something most .NET developers do out of habit that you think deserves a second look.",
        "Open with a question that a junior dev would never think to ask but a senior dev loses sleep over.",
        "Open with a blunt, slightly frustrated observation about something in the .NET ecosystem that wastes peoples time.",
        "Open mid-thought, as if continuing a conversation already in progress. No setup, no intro — just the insight.",
    ]

    # ---------------------------------------------------------------
    # ENDINGS: rotate so the post does not always close with a question
    # ---------------------------------------------------------------
    endings = [
        "End with a casual question to the audience — one line, conversational, not formal.",
        "End with a short punchy statement that gives your opinion and leaves no question. No call to action.",
        "End with a challenge: tell the reader one concrete thing to go and check in their own codebase.",
        "End by zooming out — one sentence connecting the technical point to something broader about how teams or systems fail.",
        "End with a dry, slightly self-aware observation about how long it took you to learn this.",
    ]

    # ---------------------------------------------------------------
    # FORMATS: vary post shape so it does not always read as paragraphs
    # ---------------------------------------------------------------
    formats = [
        "Write it as one flowing block of text, no line breaks between thoughts.",
        "Write it as short punchy lines, each on its own line. Like how real people write on LinkedIn — not essays.",
        "Write two short paragraphs. First one sets up the problem, second one is your take.",
        "Write it as a single paragraph that builds to one sharp final sentence.",
    ]

    # ---------------------------------------------------------------
    # WORD COUNTS: rotate so post length varies across days
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
    # BANNED PHRASES: kill repeated AI patterns
    # ---------------------------------------------------------------
    banned_phrases = [
        "production taught me",
        "something I keep coming back to",
        "a pattern I've seen break teams",
        "we've all been there",
        "after years of",
        "hard-won",
        "battle-tested",
        "I just learned",
        "I recently discovered",
        "building my first",
        "I was surprised to find",
        "it's all about",
        "straightforward",
        "seamless",
        "dive into",
        "delve into",
        "I stumbled upon",
        "robust",
        "game-changer",
        "the key to",
        "the importance of",
        "in today's world",
        "in the world of",
        "navigating",
        "ever-evolving",
        "tech landscape",
        "as developers",
        "as a developer",
        "let that sink in",
        "food for thought",
        "it's worth noting",
        "at the end of the day",
        "take it to the next level",
    ]
    banned_str = "\n".join(f"- {p}" for p in banned_phrases)

    prompt = f"""Today is {today}. You are ghostwriting a LinkedIn post for a senior C#/.NET developer.

This person works on cloud migration, NAS storage systems, remediation workflows (archive, quarantine), compliance, and governance. Their daily work involves scanning millions of files, managing cross-protocol permissions (SMB, NFS, SharePoint, S3, OneDrive), and keeping enterprise data compliant. Write from that world — not from the world of web APIs, startups, or consumer apps.

Choose ONE article from the list below that connects best to: cloud infrastructure, data pipelines, file system integrations, security and permissions, compliance automation, enterprise storage, or scalable .NET backend patterns. If nothing is a direct match, pick the one whose underlying concept — async pipelines, error handling, security, background workers, performance — maps closest to that work.

Each article includes a summary. Read it. The post must reference at least one specific detail, behaviour, or finding from that summary — not just the title. A post that could have been written without reading the summary will be rejected.

Here are the articles:
{posts_text}

STEP 1 — Choose one topic:
Output your choice on the very first line as: Chosen topic: [article title]

STEP 2 — Write the LinkedIn post about ONLY that topic. Do not reference any other article from the list.

Post rules:
- {chosen_opener}
- {chosen_ending}
- {chosen_format}
- Write like a real person typing, not like someone drafting a press release
- Confident and direct — peer to peer, not teacher to student
- No emojis. Not a single one. No smiley faces, no symbols, nothing.
- No markdown formatting
- {chosen_word_count}
- End with: #CSharp #DotNet #Programming #SoftwareDevelopment

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


def post_to_linkedin(content):
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
    
    payload = {
        "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": content
                },
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
    print("Fetching posts from Reddit and .NET Dev Blog...")
    posts = fetch_posts()
    
    if not posts:
        print("No posts fetched, exiting.")
        return
    
    print("\nGenerating LinkedIn post with Groq...")
    linkedin_content = generate_linkedin_post(posts)
    print("\nGenerated post:")
    print(linkedin_content)
    print("\nCleaning markdown before posting...")
    linkedin_content = clean_markdown(linkedin_content)
    print("\nCleaned post:")
    print(linkedin_content)
    print("\nPosting to LinkedIn...")
    post_to_linkedin(linkedin_content)


if __name__ == "__main__":
    main()
