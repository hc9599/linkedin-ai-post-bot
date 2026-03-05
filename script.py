import requests
import os

# Reddit API endpoint
url = "https://www.reddit.com/r/csharp/top.json?t=day&limit=10"

headers = {
    "User-Agent": "linkedin-ai-post-bot/1.0"
}

response = requests.get(url, headers=headers)

# Check if request succeeded
if response.status_code != 200:
    print("Reddit API error:", response.status_code)
    print(response.text)
    exit(1)

data = response.json()

titles = [post["data"]["title"] for post in data["data"]["children"]]

posts = "\n".join(titles)

print("Fetched posts:")
print(posts)