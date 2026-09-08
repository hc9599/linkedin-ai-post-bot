# Contract: PostSource Protocol

**Version**: 1.0  
**Feature**: 001-generic-topic-trend

## Protocol

```python
class PostSource(Protocol):
    def fetch(self) -> list[CandidatePost]: ...
```

## CandidatePost (unchanged)

```python
@dataclass
class CandidatePost:
    title: str
    link: str
    summary: str
    reactions: int
    source: str  # display label, e.g. "Reddit", ".NET Dev Blog"
```

## Implementations

| Class | Constructor params | Source of params |
| --- | --- | --- |
| `RedditSource` | `subreddits: list[str]` | `profile.sources.reddit_subreddits` |
| `DevToSource` | `tags: list[str]` | `profile.sources.devto_tags` |
| `HackerNewsSource` | `queries`, `keywords`, `extra_queries: list[str] \| None` | profile + runtime focus topic |
| `RssFeedSource` | `feed_urls: list[str]`, `source_name: str` | each entry in `profile.sources.rss_feeds` |

## Factory

```python
def build_sources(profile: NicheProfile) -> list[PostSource]: ...
```

Skips source types with empty config lists.

## SourceAggregator

```python
class SourceAggregator:
    def __init__(
        self,
        sources: list[PostSource],
        per_source: int = 2,
        final_count: int = 6,
        pool_size: int = 10,
    ): ...

    def fetch(self) -> list[CandidatePost]: ...
```

**Bug fix contract**: `fetch()` MUST return `deduped[:final_count]` after title normalization dedupe, not `combined[:final_count]`.

## Relevance helpers

```python
def is_relevant(title: str, summary: str, keywords: list[str]) -> bool: ...

def matches_topic(title: str, summary: str, topic: str) -> bool: ...
```

Used by HN filter, article pick, and review pre-check.
