"""
Reddit articles about C# and .NET.

Reddit often blocks GitHub's cloud IPs (429/403). We use Arctic Shift first —
a public index that CI can reach. One RSS attempt only if Arctic Shift is empty.
"""
from datetime import datetime
import re

from linkedin_bot.http import fetch_feed_entries, fetch_json
from linkedin_bot.models import CandidatePost

REDDIT_SKIP_KEYWORDS = [
    "beginner", "portfolio projects", "how do i", "help me",
    "what should i", "which is better", "should i learn",
    "career advice", "just started", "new to", "getting started",
    "roast my", "review my code", "first project",
]

def is_quality_reddit_post(title: str) -> bool:
    title_lower = title.lower()
    return not any(kw in title_lower for kw in REDDIT_SKIP_KEYWORDS)


def _rss_urls(subreddit: str, sort: str) -> list[str]:
    return [
        f"https://www.reddit.com/r/{subreddit}/{sort}.rss?limit=25",
        f"https://www.reddit.com/r/{subreddit}/{sort}/.rss?limit=25",
        f"https://old.reddit.com/r/{subreddit}/{sort}.rss?limit=25",
    ]


def _entry_to_post(entry: dict, subreddit: str, seen: set[str]) -> CandidatePost | None:
    title = (entry.get("title") or "").strip()
    if len(title) < 20 or title in seen or not is_quality_reddit_post(title):
        if title and not is_quality_reddit_post(title):
            print(f"    Skipping low-quality: {title[:70]}")
        return None

    raw_summary = entry.get("summary", "")
    raw_summary = re.sub(r"<[^>]+>", " ", raw_summary)
    raw_summary = re.sub(r"\s+", " ", raw_summary).strip()

    seen.add(title)
    return CandidatePost(
        title=title,
        link=entry.get("link", ""),
        summary=(raw_summary[:500] if raw_summary else title),
        reactions=0,
        source=f"r/{subreddit}",
    )


def _fetch_arctic_shift(subreddit: str, seen: set[str]) -> list[CandidatePost]:
    """Third-party index — not behind Reddit/Cloudflare WAF, so GitHub Actions can reach it."""
    print(f"  trying Arctic Shift API r/{subreddit}")
    payload = fetch_json(
        "https://arctic-shift.photon-reddit.com/api/posts/search",
        params={"subreddit": subreddit, "limit": 25},
        attempts=4,
    )
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data") or []
    posts: list[CandidatePost] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        if len(title) < 20 or title in seen:
            continue
        if not is_quality_reddit_post(title):
            print(f"    Skipping low-quality: {title[:70]}")
            continue
        permalink = row.get("permalink") or ""
        link = row.get("url") or ""
        if permalink and (not link or "reddit.com" not in link):
            link = f"https://www.reddit.com{permalink}"
        selftext = (row.get("selftext") or "").strip()
        seen.add(title)
        posts.append(CandidatePost(
            title=title,
            link=link or f"https://www.reddit.com/r/{subreddit}",
            summary=(selftext[:500] if selftext else title),
            reactions=int(row.get("score") or 0),
            source=f"r/{subreddit}",
        ))
    return posts


def _posts_from_rss_entries(
    entries: list,
    subreddit: str,
    seen: set[str],
) -> list[CandidatePost]:
    posts: list[CandidatePost] = []
    for entry in entries:
        post = _entry_to_post(entry, subreddit, seen)
        if post is not None:
            posts.append(post)
    return posts


def _fetch_subreddit(subreddit: str, sort: str, seen: set[str]) -> list[CandidatePost]:
    print(f"Fetching Reddit r/{subreddit} ({sort})...")

    arctic_posts = _fetch_arctic_shift(subreddit, seen)
    if arctic_posts:
        print(f"  r/{subreddit}: {len(arctic_posts)} posts via Arctic Shift")
        return arctic_posts

    url = _rss_urls(subreddit, sort)[0]
    print(f"  Arctic Shift empty, trying RSS once {url}")
    entries = fetch_feed_entries(url, attempts=1)
    posts = _posts_from_rss_entries(entries, subreddit, seen)
    if posts:
        print(f"  r/{subreddit}: {len(posts)} posts via RSS")
        return posts

    print(f"  r/{subreddit}: Arctic Shift + RSS empty or blocked")
    return []


class RedditSource:
    """
    r/csharp and r/dotnet.

    GitHub Actions IPs get 429 from Reddit — Arctic Shift is the primary path.
    """

    def fetch(self) -> list[CandidatePost]:
        subreddits = ["csharp", "dotnet"]
        sort = "top" if datetime.now().weekday() % 2 == 0 else "hot"
        posts: list[CandidatePost] = []
        seen: set[str] = set()

        for subreddit in subreddits:
            posts.extend(_fetch_subreddit(subreddit, sort, seen))

        print(f"Total Reddit posts collected: {len(posts)}")
        return posts
