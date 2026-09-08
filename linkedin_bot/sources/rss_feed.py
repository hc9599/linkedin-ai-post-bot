"""
Generic RSS/Atom feed source.

Replaces niche-specific blog sources — feed URLs and label come from profile.
"""
import re

from linkedin_bot.http import fetch_feed_entries
from linkedin_bot.models import CandidatePost


class RssFeedSource:
    """Fetch recent entries from one or more RSS/Atom feed URLs."""

    def __init__(self, feed_urls: list[str], source_name: str):
        self._feed_urls = feed_urls
        self._source_name = source_name

    def fetch(self) -> list[CandidatePost]:
        print(f"Fetching RSS: {self._source_name}...")
        entries = []
        for url in self._feed_urls:
            print(f"  trying {url}")
            entries = fetch_feed_entries(url)
            if entries:
                print(f"  {self._source_name}: {len(entries)} entries fetched")
                break
        else:
            print(f"  {self._source_name}: all feed URLs failed")
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
                source=self._source_name,
            ))

        print(f"Total {self._source_name} posts collected: {len(posts)}")
        return posts
