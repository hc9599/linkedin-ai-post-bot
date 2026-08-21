"""
News sites the bot reads.

Each website has its own class with a fetch() method.
The mixer (SourceAggregator) takes a couple of articles from each so the AI
has a mixed menu, not 6 posts from one site.
"""
import random
import re
from typing import Protocol

from linkedin_bot.models import CandidatePost


class PostSource(Protocol):
    """A website we can ask: "give me recent C# / .NET articles." """

    def fetch(self) -> list[CandidatePost]:
        ...


class SourceAggregator:
    """
    Mix articles from every source.

    Takes up to 2 from each site, shuffles, then keeps 6.
    If a site is blocked and returns nothing, we backfill from whatever we got.
    """

    def __init__(
        self,
        sources: list[PostSource],
        per_source: int = 2,
        final_count: int = 6,
        pool_size: int = 10,
    ):
        self._sources = sources
        self._per_source = per_source
        self._final_count = final_count
        self._pool_size = pool_size

    def fetch(self) -> list[CandidatePost]:
        buckets: list[list[CandidatePost]] = []
        leftovers: list[CandidatePost] = []

        for source in self._sources:
            posts = source.fetch()
            leftovers.extend(posts)
            ranked = sorted(posts, key=lambda x: x.reactions, reverse=True)
            pool = ranked[:self._pool_size]
            random.shuffle(pool)
            buckets.append(pool[:self._per_source])

        combined: list[CandidatePost] = []
        for bucket in buckets:
            combined.extend(bucket)

        if len(combined) < 3:
            combined = leftovers[:6]

        random.shuffle(combined)

        # Deduplicate across sources by normalised title
        # Keeps the first occurrence (highest ranked source wins)
        seen_titles: set[str] = set()
        deduped: list[CandidatePost] = []
        for p in combined:
            norm = re.sub(r"[^a-z0-9\s]", "", p.title.lower()).strip()
            if norm not in seen_titles:
                seen_titles.add(norm)
                deduped.append(p)

        final = combined[:self._final_count]

        print(f"\nFinal selected posts ({len(final)}):")
        for p in final:
            print(f"  - [{p.reactions} reactions | {p.source}] {p.title}")

        return final
