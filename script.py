import feedparser
import requests
import os
import json

def fetch_reddit_posts(subreddit="csharp", limit=10):
    url = f"https://www.reddit.com/r/{subreddit}/top.rss?t=day&limit={limit}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    feed = feedparser.parse(url, request_headers=headers)
    
    if not feed.entries:
        print("No entries found in feed")
        return []
    
    posts = []
    for entry in feed.entries:
        posts.append({
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", "")[:200]
        })
    
    return posts

def generate_linkedin_post(posts):
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    
    posts_text = "\n".join([f"- {p['title']}" for p in posts])
    
    prompt = f"""Based on these trending C# topics from Reddit today:

{posts_text}

Write a professional LinkedIn post that:
- Highlights the most interesting trends
- Is engaging and insightful for .NET/C# developers
- Ends with relevant hashtags like #CSharp #DotNet #Programming
- Is between 150-300 words
- Does not mention Reddit as the source
"""
    
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Groq API error: {response.status_code} - {response.text}")
    
    return response.json()["choices"][0]["message"]["content"]

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
    print("Fetching Reddit posts via RSS...")
    posts = fetch_reddit_posts(subreddit="csharp", limit=10)
    
    if not posts:
        print("No posts fetched, exiting.")
        return
    
    print(f"Fetched {len(posts)} posts:")
    for p in posts:
        print(f"  - {p['title']}")
    
    print("\nGenerating LinkedIn post with Groq...")
    linkedin_content = generate_linkedin_post(posts)
    print("\nGenerated post:")
    print(linkedin_content)
    
    print("\nPosting to LinkedIn...")
    post_to_linkedin(linkedin_content)

if __name__ == "__main__":
    main()
