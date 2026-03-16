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
    
    # Remove italic *text* or _text_ (Word-boundary guard protects hashtags/emails)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.*?)_(?!\w)', r'\1', text)
    
    # FIX: Only remove headers (###) if they are at the START of a line.
    # The `^` anchor and `MULTILINE` flag prevent it from stripping the '#' in 'C# '
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Note: Numbered list (1. 2.) and bullet point (- or *) strippers have been REMOVED.
    # This allows the AI's structural formatting to survive to LinkedIn.
    
    # Remove horizontal rules ---
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    
    # Remove backticks for inline code
    text = re.sub(r'`(.*?)`', r'\1', text)
    
    # Remove code blocks completely (LinkedIn doesn't format them well anyway)
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
    
    # 1. Rotate persona phrases (Pick 1-2 randomly)
    persona_phrases = [
        "Something I keep coming back to...",
        "A pattern I've seen break teams...",
        "After years of wrestling with this in production...",
        "Production has a funny way of teaching you...",
        "I used to overcomplicate this, but...",
        "The unglamorous truth about enterprise .NET dev...",
        "If I see one more PR doing this...",
        "Hard truth for backend devs:"
    ]
    selected_phrases = random.sample(persona_phrases, k=random.randint(1, 2))
    phrases_instruction = "\n".join([f'- "{p}"' for p in selected_phrases])

    # 2. Vary post structure
    structures = [
        "A hot take with absolutely NO question or call-to-action at the end. Just state your peace and end it abruptly.",
        "A mini-story about a messy code review, a PR comment, or a debugging session.",
        "A direct observation ending with a highly specific, deeply technical question (NOT a generic one).",
        "A mild, relatable technical complaint about how things usually go wrong in legacy code."
    ]
    chosen_structure = random.choice(structures)

    # 3. Add a format randomizer
    formats = [
        "Short, punchy lines separated by line breaks (but don't make it cringey).",
        "One flowing, conversational paragraph. Very casual.",
        "A brief intro followed by exactly 2 or 3 short numbered observations."
    ]
    chosen_format = random.choice(formats)
    
    prompt = f"""Today is {today}. You are ghostwriting a LinkedIn post for a senior C#/.NET developer with 5+ years of production experience.

CRITICAL RULES FOR SOUNDING HUMAN (Never break these):
- NEVER USE THESE BANNED PHRASES: "We've all been there", "In today's fast-paced", "Crucial", "Game-changer", "Delve", "Robust", "Seamless", "Picture this", "It's amazing how", "Navigating the complexities", "Let's dive in", "A friendly reminder".
- DO NOT use the word "hashtag" before the # symbol.
- Keep the word count flexible: anywhere from 100 to 220 words. Shorter is often much better and more natural.
- Sound like a tired but experienced tech lead chatting on Slack, not a marketer.

Professional context (always respect this):
- This developer works primarily in: cloud migration, NAS storage systems, remediation workflows, compliance, and governance.
- Core product areas: metadata scanning, permission management, and datastore integrations (SMB, NFS, SharePoint, Azure Storage, S3).
- Avoid frontend, game dev, UI/UX, or beginner tutorials.

Here are the trending C# and .NET articles to choose from:
{posts_text}

STEP 1 — Choose ONE topic:
- Pick exactly ONE article that maps closest to enterprise storage, data pipelines, security, or scalable .NET backend patterns.
- Output your choice on the very first line as: Chosen topic: [article title]

STEP 2 — Write the LinkedIn post using ONLY the core concept of that chosen topic:
- Structure the post like this: {chosen_structure}
- Format the text like this: {chosen_format}
- Naturally work in at least one of these exact phrases (but do not force it if it sounds awkward):
{phrases_instruction}

Post requirements:
- Use 1 or 2 emojis maximum.
- End with 3-4 standard hashtags (e.g., #CSharp #DotNet). Just use the # symbol.
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
                "temperature": 0.85, # Slightly lowered for more consistent tone constraints
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
