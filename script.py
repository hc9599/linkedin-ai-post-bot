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

    # Lowered filter to reactions >= 0 so nothing gets excluded
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
