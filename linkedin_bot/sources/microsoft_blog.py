"""
Official Microsoft .NET blog.

RSS first, Atom if RSS is empty. Same retry helper as the other sites.
"""
import re

from linkedin_bot.http import fetch_feed_entries
from linkedin_bot.models import CandidatePost

FEED_URLS = [
    "https://devblogs.microsoft.com/dotnet/feed/",
    "https://devblogs.microsoft.com/dotnet/feed/atom/",
]


class MicrosoftBlogSource:
    """Microsoft's own .NET blog RSS. Official news, no upvotes."""

    def fetch(self) -> list[CandidatePost]:
        print("Fetching .NET Dev Blog RSS...")
        entries = []
        for url in FEED_URLS:
            print(f"  trying {url}")
            entries = fetch_feed_entries(url)
            if entries:
                print(f"  .NET blog: {len(entries)} entries fetched")
                break
        else:
            print(".NET blog fetch error: all feed URLs failed")
            return []

        posts: list[CandidatePost] = []
        for entry in entries[:20]:
            title = entry.get("title", "")
            if len(title) < 20:
                continue

            raw_summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))
            raw_summary = re.sub(r"\s+", " ", raw_summary).strip()
            summary = raw_summary[:500]

            posts.append(CandidatePost(
                title=title,
                link=entry.get("link", ""),
                summary=summary,
                reactions=0,
                source=".NET Dev Blog",
            ))

        print(f"Total .NET blog posts collected: {len(posts)}")
        return posts
