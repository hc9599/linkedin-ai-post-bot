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
    
    # Remove italic *text* or _text_ (FIX 2: word-boundary guard to protect hashtags)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.*?)_(?!\w)', r'\1', text)
    
    # Remove headers ### ## #
    text = re.sub(r'#{1,6}\s+', '', text)
    
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
    
    # Clean up extra blank lines (more than 2 in a row)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def fetch_devto_posts():
    tag_rotation = {
        0: ["csharp", "dotnet"],        # Monday
        1: ["dotnet", "azure"],          # Tuesday
        2: ["csharp", "webdev"],         # Wednesday
        3: ["dotnet", "architecture"],   # Thursday
        4: ["csharp", "career"],         # Friday
    }
    
    today = datetime.now().weekday()
    tags = tag_rotation.get(today, ["csharp", "dotnet"])
    tag = random.choice(tags)
    page = random.randint(1, 3)
    
    print(f"Fetching Dev.to posts with tag: #{tag}, page: {page}")
    
    url = f"https://dev.to/api/articles?tag={tag}&page={page}&per_page=20"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    
    if response.status_code != 200:
        print(f"Dev.to API error: {response.status_code}")
        return []
    
    articles = response.json()
    print(f"Total articles fetched: {len(articles)}")
    
    # Fallback to page 1 if current page is empty
    if not articles:
        print("Page empty, falling back to page 1...")
        url = f"https://dev.to/api/articles?tag={tag}&page=1&per_page=20"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        articles = response.json()
        print(f"Fallback articles fetched: {len(articles)}")

    # Fallback to dotnet tag if csharp returns nothing
    if not articles:
        print("No articles found, trying dotnet tag...")
        url = f"https://dev.to/api/articles?tag=dotnet&page=1&per_page=20"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        articles = response.json()
        print(f"Dotnet fallback articles fetched: {len(articles)}")

    # Print reactions count to help debug
    print("Reactions count for fetched articles:")
    for a in articles:
        print(f"  - [{a.get('positive_reactions_count', 0)} 👍] {a['title']}")

    # Filter with reactions >= 0 so nothing gets excluded
    filtered = [
        a for a in articles
        if a.get("positive_reactions_count", 0) >= 0
        and len(a.get("title", "")) > 20
    ]
    
    print(f"Filtered articles: {len(filtered)}")
    
    random.shuffle(filtered)
    selected = filtered[:5]
    
    posts = []
    for article in selected:
        posts.append({
            "title": article["title"],
            "link": article["url"],
            "summary": article.get("description", "")[:200],
            "reactions": article.get("positive_reactions_count", 0),
            "tag": tag
        })
    
    return posts


def generate_linkedin_post(posts):
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    
    today = datetime.now().strftime("%A, %B %d")
    
    posts_text = "\n".join([
        f"- {p['title']} (👍 {p['reactions']} reactions): {p['summary']}"
        for p in posts
    ])
    
    styles = [
        "Start with a relatable developer struggle or funny observation",
        "Start with a surprising fact or controversial opinion about .NET/C#",
        "Start with a short story or scenario a developer would recognize",
        "Start with a bold claim that grabs attention",
        "Start with a question that makes developers stop and think",
    ]
    chosen_style = random.choice(styles)
    
    # FIX 1: Added clear label before articles so the model knows what it's reading
    # FIX 3: Expanded banned phrases list to prevent beginner/AI-sounding language
    prompt = f"""Today is {today}. You are ghostwriting a LinkedIn post for a senior C#/.NET developer with 5+ years of production experience.

Persona rules (never break these):
- Write as someone who has SEEN things — battle-tested opinions, not beginner discoveries
- Never use: "I just learned", "I recently discovered", "building my first", "I was surprised to find", "it's all about", "straightforward", "seamless", "dive into", "delve into", "I stumbled upon", "robust", "game-changer", "I recently dove into", "the key to", "the importance of"
- Instead use: "something I keep coming back to", "a pattern I've seen break teams", "after years of this...", "we've all been there", "production taught me"
- The tone is confident but not arrogant — like a tech lead sharing hard-won insight with peers
- Assume the audience are also experienced developers, not beginners

Professional context (always respect this):
- This developer works primarily in: cloud migration, NAS storage systems, remediation workflows (archive, quarantine), compliance, and governance
- Core product areas include: metadata scanning (SMB, NFS, S3, SharePoint), permission management (SMB, NFS, SharePoint), and datastore integrations (SMB, NFS, SharePoint, Azure Storage, S3, OneDrive)
- When choosing a topic in STEP 1, strongly prefer articles that connect to: cloud infrastructure, data pipelines, file system integrations, security & permissions, compliance automation, enterprise storage, or scalable .NET backend patterns
- If no article directly matches, pick the one whose underlying concept (e.g. async pipelines, error handling, security, background workers, performance) maps closest to enterprise storage or compliance infrastructure work
- Never pick topics about: game dev, UI/UX, web APIs for e-commerce, payment systems, consumer-facing app development, or beginner tutorials
- The post should feel written by someone whose daily .NET work involves scanning millions of files, managing cross-protocol permissions, integrating with cloud datastores, and keeping enterprise data compliant — not someone building web apps or startups

Here are the trending C# and .NET articles to choose from:
{posts_text}

STEP 1 — Choose ONE topic:
- Read all the articles above
- Pick exactly ONE that is most relatable to everyday C#/.NET developers
- Prefer topics about: async/await, performance, debugging, architecture, tooling, security, or common pain points
- Avoid overly niche topics (e.g. game dev mechanics, obscure libraries) unless the concept maps broadly to .NET dev work
- Output your choice on the very first line as: Chosen topic: [article title]

STEP 2 — Write the LinkedIn post using ONLY that chosen topic:
- Every sentence must connect to that single topic — do not drift
- Do NOT mention, reference, or allude to any other article from the list
- The post should feel like it was inspired by one article, not a digest of many
- If you catch yourself switching to a different technical subject mid-post, stop and rewrite

Post requirements:
- {chosen_style}
- Transitions smoothly into insight from the chosen topic
- Keeps technical content accurate and insightful for .NET/C# developers
- Has a light conversational tone — like a smart colleague sharing knowledge
- Adds mild humor or a clever observation
- Ends with an engaging question to the audience
- Uses 2-3 relevant emojis naturally (not forced)
- Ends with hashtags: #CSharp #DotNet #Programming #SoftwareDevelopment
- Is between 150-200 words
- Sounds like a real human developer wrote it, not an AI
"""

    # FIX 4: Retry logic — retries up to 3 times on Groq API failure
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
                "temperature": 0.9,
                "top_p": 0.9
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
    print("Fetching Dev.to posts...")
    posts = fetch_devto_posts()
    
    if not posts:
        print("No posts fetched, exiting.")
        return
    
    print(f"\nSelected {len(posts)} posts:")
    for p in posts:
        print(f"  - [{p['reactions']} 👍] {p['title']}")
    
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
