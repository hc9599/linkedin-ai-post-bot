"""
News sites the bot reads.

Each website has its own class with a fetch() method.
The mixer (SourceAggregator) takes a couple of articles from each so the AI
has a mixed menu, not multiple posts from one site.
"""
import random
import re
from typing import Protocol

from linkedin_bot.models import CandidatePost
from linkedin_bot.niche import NicheProfile
from linkedin_bot.sources.devto import DevToSource
from linkedin_bot.sources.hackernews import HackerNewsSource
from linkedin_bot.sources.reddit import RedditSource
from linkedin_bot.sources.rss_feed import RssFeedSource


class PostSource(Protocol):
    """A website we can ask for recent niche articles."""

    def fetch(self) -> list[CandidatePost]:
        ...


def build_sources(profile: NicheProfile, *, focus_topic: str | None = None) -> list[PostSource]:
    """Construct enabled sources from a niche profile."""
    sources: list[PostSource] = []
    cfg = profile.sources

    if cfg.reddit_subreddits:
        sources.append(RedditSource(cfg.reddit_subreddits))
    if cfg.devto_tags:
        sources.append(DevToSource(cfg.devto_tags))
    for feed in cfg.rss_feeds:
        sources.append(RssFeedSource(feed.urls, feed.name))
    if cfg.hn_queries:
        extra: list[str] = []
        if focus_topic:
            extra = [
                f"{focus_topic} {profile.display_name.split('/')[0].strip()}",
                focus_topic,
            ]
        sources.append(HackerNewsSource(
            queries=cfg.hn_queries,
            keywords=profile.relevance_keywords,
            extra_queries=extra,
        ))

    return sources


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

        seen_titles: set[str] = set()
        deduped: list[CandidatePost] = []
        for post in combined:
            norm = re.sub(r"[^a-z0-9\s]", "", post.title.lower()).strip()
            if norm not in seen_titles:
                seen_titles.add(norm)
                deduped.append(post)

        final = deduped[:self._final_count]

        print(f"\nFinal selected posts ({len(final)}):")
        for post in final:
            print(f"  - [{post.reactions} reactions | {post.source}] {post.title}")

        return final
