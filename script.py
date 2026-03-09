import requests
import os
import random
from datetime import datetime

def fetch_devto_posts():
    # Rotate tags based on day of week so content varies daily
    tag_rotation = {
        0: ["csharp", "dotnet"],        # Monday
        1: ["dotnet", "azure"],          # Tuesday
        2: ["csharp", "webdev"],         # Wednesday
        3: ["dotnet", "architecture"],   # Thursday
        4: ["csharp", "career"],         # Friday
    }
    
    today = datetime.now().weekday()
    tags = tag_rotation.get(today, ["csharp", "dotnet"])
    
    # Randomly pick one tag from today's options
    tag = random.choice(tags)
    
    # Randomly vary the page to avoid always getting same posts
    page = random.randint(1, 3)
    
    print(f"Fetching Dev.to posts with tag: #{tag}, page: {page}")
    
    url = f"https://dev.to/api/articles?tag={tag}&page={page}&per_page=20"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    
    if response.status_code != 200:
        print(f"Dev.to API error: {response.status_code}")
        return []
    
    articles = response.json()
    
    if not articles:
        # Fallback to page 1 if page has no results
        url = f"https://dev.to/api/articles?tag={tag}&page=1&per_page=20"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        articles = response.json()
    
    # Filter articles - only pick ones with decent engagement
    filtered = [
        a for a in articles
        if a.get("positive_reactions_count", 0) > 5
        and a.get("comments_count", 0) >= 0
        and len(a.get("title", "")) > 20
    ]
    
    # Randomly shuffle and pick 5 posts
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
    
    # Add current date so each post feels fresh and timely
    today = datetime.now().strftime("%A, %B %d")
    
    posts_text = "\n".join([
        f"- {p['title']} (👍 {p['reactions']} reactions): {p['summary']}"
        for p in posts
    ])
    
    # Randomly vary the post style so it doesn't feel repetitive
    styles = [
        "Start with a relatable developer struggle or funny observation",
        "Start with a surprising fact or controversial opinion about .NET/C#",
        "Start with a short story or scenario a developer would recognize",
        "Start with a bold claim that grabs attention",
        "Start with a question that makes developers stop and think",
    ]
    chosen_style = random.choice(styles)
    
    prompt = f"""Today is {today}. Based on these trending C# and .NET articles:

{posts_text}

Write a professional LinkedIn post that:
- {chosen_style}
- Transitions smoothly into the technical highlights from the articles
- Keeps technical content accurate and insightful for .NET/C# developers
- Has a light conversational tone — like a smart colleague sharing knowledge
- Adds mild humor or a clever observation between points
- Ends with an engaging question to the audience
- Uses 2-3 relevant emojis naturally (not forced)
- Ends with hashtags: #CSharp #DotNet #Programming #SoftwareDevelopment
- Is between 150-300 words
- Sounds like a real human developer wrote it, not an AI
- IMPORTANT: Make it feel different from a generic AI post
"""
    
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,   # higher = more creative and varied output
            "top_p": 0.9
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
        "author": f"urn:li:member:{LINKEDIN_PERSON_ID}",
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
    
    print("\nPosting to LinkedIn...")
    post_to_linkedin(linkedin_content)

if __name__ == "__main__":
    main()
