"""
Extra C# / .NET RSS sources.

These sites do not block GitHub Actions the way Reddit does.
Each class is one site. Same CandidatePost shape as the rest.
"""
import re

from linkedin_bot.http import fetch_feed_entries
from linkedin_bot.models import CandidatePost
from linkedin_bot.sources.relevance import is_dotnet_relevant


def _plain(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _posts_from_feeds(
    label: str,
    urls: list[str],
    source: str,
    *,
    require_dotnet: bool = False,
    limit: int = 15,
) -> list[CandidatePost]:
    print(f"Fetching {label}...")
    entries = []
    for url in urls:
        print(f"  trying {url}")
        entries = fetch_feed_entries(url)
        if entries:
            print(f"  {label}: {len(entries)} entries fetched")
            break
    else:
        print(f"  {label}: all feed URLs failed")
        return []

    posts: list[CandidatePost] = []
    seen: set[str] = set()
    for entry in entries[:limit]:
        title = _plain(entry.get("title", ""))
        if len(title) < 20 or title in seen:
            continue
        summary = _plain(entry.get("summary", ""))[:500]
        if require_dotnet and not is_dotnet_relevant(title, summary):
            print(f"    Skipping off-topic: {title[:70]}")
            continue
        seen.add(title)
        posts.append(CandidatePost(
            title=title,
            link=entry.get("link", "") or "",
            summary=summary or title,
            reactions=0,
            source=source,
        ))
    print(f"Total {label} posts collected: {len(posts)}")
    return posts


class LobstersSource:
    """Lobste.rs tagged csharp / dotnet. Small, high-signal, RSS works from GHA."""

    def fetch(self) -> list[CandidatePost]:
        return _posts_from_feeds(
            "Lobsters",
            [
                "https://lobste.rs/t/dotnet.rss",
                "https://lobste.rs/t/csharp.rss",
            ],
            "Lobsters",
        )


class InfoQDotNetSource:
    """InfoQ .NET channel. Architecture and platform pieces."""

    def fetch(self) -> list[CandidatePost]:
        return _posts_from_feeds(
            "InfoQ .NET",
            ["https://feed.infoq.com/dotnet/"],
            "InfoQ",
        )


class JetBrainsDotNetSource:
    """JetBrains .NET / Rider blog."""

    def fetch(self) -> list[CandidatePost]:
        return _posts_from_feeds(
            "JetBrains .NET",
            ["https://blog.jetbrains.com/dotnet/feed/"],
            "JetBrains .NET",
        )
