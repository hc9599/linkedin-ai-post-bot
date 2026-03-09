import requests
import os

def fetch_devto_posts(tag="csharp", limit=10):
    url = f"https://dev.to/api/articles?tag={tag}&top=1&per_page={limit}"
    
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    
    if response.status_code != 200:
        print(f"Dev.to API error: {response.status_code}")
        return []
    
    articles = response.json()
    
    posts = []
    for article in articles:
        posts.append({
            "title": article["title"],
            "link": article["url"],
            "summary": article.get("description", "")[:200],
            "reactions": article.get("positive_reactions_count", 0)
        })
    
    return posts

def generate_linkedin_post(posts):
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    
    posts_text = "\n".join([f"- {p['title']}: {p['summary']}" for p in posts])
    
    prompt = f"""Based on these trending C# and .NET articles today:

{posts_text}

Write a professional LinkedIn post that:
- Highlights the most interesting trends
- Is engaging and insightful for .NET/C# developers
- Ends with relevant hashtags like #CSharp #DotNet #Programming
- Is between 150-300 words
- Sounds like a human wrote it
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
    print("Fetching Dev.to posts...")
    posts = fetch_devto_posts(tag="csharp", limit=10)
    
    if not posts:
        # Fallback to dotnet tag if csharp returns nothing
        print("Trying 'dotnet' tag...")
        posts = fetch_devto_posts(tag="dotnet", limit=10)
    
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
