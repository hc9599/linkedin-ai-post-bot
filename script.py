import requests
import os

# Fetch reddit posts
url = "https://www.reddit.com/r/csharp/top.json?t=day&limit=10"
headers = {"User-Agent": "csharp-trend-bot"}

response = requests.get(url, headers=headers)
data = response.json()

titles = [post["data"]["title"] for post in data["data"]["children"]]

posts = "\n".join(titles)

# Build prompt
prompt = f"""
Analyze these Reddit discussions about C# and .NET.

Generate a LinkedIn post with:
- insights
- bullet points
- hashtags

Posts:
{posts}
"""

# Call Groq API
groq_key = os.environ["GROQ_API_KEY"]

response = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
)

result = response.json()

linkedin_post = result["choices"][0]["message"]["content"]

print(linkedin_post)

# Save result
with open("linkedin_post.txt","w") as f:
    f.write(linkedin_post)