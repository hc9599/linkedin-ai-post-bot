"""
Hacker News via Algolia's public search.

No login needed. Queries come from niche profile; off-topic hits filtered
by profile relevance keywords.
"""
from datetime import datetime
import time

from linkedin_bot.http import fetch_json
from linkedin_bot.models import CandidatePost
from linkedin_bot.sources.relevance import is_relevant


class HackerNewsSource:
    """Search HN for niche stories from the last week (two weeks on weekends)."""

    def __init__(
        self,
        queries: list[str],
        keywords: list[str],
        extra_queries: list[str] | None = None,
    ):
        self._queries = list(queries)
        self._keywords = keywords
        self._extra_queries = list(extra_queries or [])

    def fetch(self) -> list[CandidatePost]:
        all_queries = self._queries + self._extra_queries
        posts: list[CandidatePost] = []
        seen: set[str] = set()
        window_days = 14 if datetime.now().weekday() >= 5 else 7
        created_after = int(time.time()) - window_days * 24 * 3600

        for query in all_queries:
            print(f"Fetching HackerNews: '{query}'...")
            payload = fetch_json(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{created_after}",
                    "hitsPerPage": 15,
                },
            )
            if not isinstance(payload, dict):
                print(f"  HN '{query}': no JSON — skipping")
                continue

            hits = payload.get("hits", [])
            print(f"  HN '{query}': {len(hits)} stories fetched")

            for hit in hits:
                title = hit.get("title", "")
                summary = hit.get("story_text", "")[:500].strip()

                if len(title) < 20:
                    continue
                if title in seen:
                    continue
                if not hit.get("url"):
                    continue
                if not is_relevant(title, summary, self._keywords):
                    print(f"    Skipping off-topic: {title[:70]}")
                    continue

                seen.add(title)
                posts.append(CandidatePost(
                    title=title,
                    link=hit.get("url", ""),
                    summary=summary or title,
                    reactions=hit.get("points", 0),
                    source="HackerNews",
                ))

            time.sleep(0.3)

        posts.sort(key=lambda x: x.reactions, reverse=True)
        print(f"Total HackerNews posts collected: {len(posts)}")
        return posts
