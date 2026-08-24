"""
Reddit articles about C# and .NET.

Reddit often blocks GitHub's cloud IPs. We try, in order:
  1. Official RSS (looks like a browser)
  2. The old.reddit HTML page
  3. Arctic Shift (a public copy of Reddit posts, not behind Reddit's wall)

Empty result from one path is fine — we try the next.
"""
from datetime import datetime
import html as html_lib
import os
import re
import time

from linkedin_bot.http import fetch_feed_entries, fetch_json, get_with_retry
from linkedin_bot.models import CandidatePost

# Official Reddit 403s GHA IPs. Retrying 403 only makes 429 worse.
_REDDIT_RETRY = {429, 500, 502, 503, 504}

REDDIT_SKIP_KEYWORDS = [
    "beginner", "portfolio projects", "how do i", "help me",
    "what should i", "which is better", "should i learn",
    "career advice", "just started", "new to", "getting started",
    "roast my", "review my code", "first project",
]

THING_OPEN_RE = re.compile(r'<div[^>]*\bclass="[^"]*\bthing\b[^"]*"[^>]*>', re.IGNORECASE)
PERMALINK_RE = re.compile(r'data-permalink="([^"]+)"')
SCORE_RE = re.compile(r'data-score="(\d+)"')
TITLE_RE = re.compile(
    r'<a[^>]*\bclass="[^"]*\btitle\b[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def is_quality_reddit_post(title: str) -> bool:
    title_lower = title.lower()
    return not any(kw in title_lower for kw in REDDIT_SKIP_KEYWORDS)


def _rss_urls(subreddit: str, sort: str) -> list[str]:
    return [
        f"https://www.reddit.com/r/{subreddit}/{sort}.rss?limit=25",
        f"https://www.reddit.com/r/{subreddit}/{sort}/.rss?limit=25",
        f"https://old.reddit.com/r/{subreddit}/{sort}.rss?limit=25",
    ]


def _html_urls(subreddit: str, sort: str) -> list[str]:
    urls = [f"https://old.reddit.com/r/{subreddit}/{sort}/?limit=25"]
    if sort == "top":
        urls.append(f"https://old.reddit.com/r/{subreddit}/top/?sort=top&t=week&limit=25")
    return urls


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


def _parse_old_reddit_html(page: str, subreddit: str, seen: set[str]) -> list[CandidatePost]:
    posts: list[CandidatePost] = []
    for match in THING_OPEN_RE.finditer(page):
        tag = match.group(0)
        permalink = PERMALINK_RE.search(tag)
        if not permalink:
            continue
        score_m = SCORE_RE.search(tag)
        chunk = page[match.start(): match.start() + 3000]
        title_m = TITLE_RE.search(chunk)
        if not title_m:
            continue
        title = html_lib.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
        if len(title) < 20 or title in seen:
            continue
        if not is_quality_reddit_post(title):
            print(f"    Skipping low-quality: {title[:70]}")
            continue
        href = permalink.group(1)
        link = href if href.startswith("http") else f"https://old.reddit.com{href}"
        seen.add(title)
        posts.append(CandidatePost(
            title=title,
            link=link,
            summary=title,
            reactions=int(score_m.group(1)) if score_m else 0,
            source=f"r/{subreddit}",
        ))
    return posts


def _in_github_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


def _row_to_post(row: dict, subreddit: str, seen: set[str]) -> CandidatePost | None:
    title = (row.get("title") or "").strip()
    if len(title) < 20 or title in seen:
        return None
    if not is_quality_reddit_post(title):
        print(f"    Skipping low-quality: {title[:70]}")
        return None
    permalink = row.get("permalink") or ""
    link = row.get("url") or ""
    if permalink and (not link or "reddit.com" not in str(link)):
        link = f"https://www.reddit.com{permalink}"
    selftext = (row.get("selftext") or "").strip()
    seen.add(title)
    return CandidatePost(
        title=title,
        link=link or f"https://www.reddit.com/r/{subreddit}",
        summary=(selftext[:500] if selftext else title),
        reactions=int(row.get("score") or 0),
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
    posts: list[CandidatePost] = []
    for row in payload.get("data") or []:
        if isinstance(row, dict):
            post = _row_to_post(row, subreddit, seen)
            if post is not None:
                posts.append(post)
    return posts


def _fetch_pullpush(subreddit: str, seen: set[str]) -> list[CandidatePost]:
    """Public Reddit archive. Another way around the GHA 403 wall."""
    print(f"  trying PullPush API r/{subreddit}")
    payload = fetch_json(
        "https://api.pullpush.io/reddit/search/submission/",
        params={"subreddit": subreddit, "size": 25},
        attempts=3,
    )
    rows: list = []
    if isinstance(payload, dict):
        rows = payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    posts: list[CandidatePost] = []
    for row in rows:
        if isinstance(row, dict):
            post = _row_to_post(row, subreddit, seen)
            if post is not None:
                posts.append(post)
    return posts


def _fetch_official_reddit(subreddit: str, sort: str, seen: set[str]) -> list[CandidatePost]:
    """www/old Reddit. Fine from home. GitHub IPs get 403/429."""
    rss_urls = _rss_urls(subreddit, sort)
    html_urls = _html_urls(subreddit, sort)
    if _in_github_actions():
        rss_urls = rss_urls[:1]
        html_urls = []

    for url in rss_urls:
        print(f"  trying RSS {url}")
        entries = fetch_feed_entries(url, attempts=2, retry_statuses=_REDDIT_RETRY)
        posts = []
        for entry in entries:
            post = _entry_to_post(entry, subreddit, seen)
            if post is not None:
                posts.append(post)
        if posts:
            print(f"  r/{subreddit}: {len(posts)} posts via RSS")
            return posts

    for url in html_urls:
        print(f"  trying HTML {url}")
        response = get_with_retry(
            url,
            attempts=2,
            retry_statuses=_REDDIT_RETRY,
            headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
        )
        if response is None or response.status_code != 200:
            continue
        if "welcome to reddit" in response.text[:800].lower():
            print("  HTML interstitial (Welcome to Reddit) - skipping")
            continue
        posts = _parse_old_reddit_html(response.text, subreddit, seen)
        if posts:
            print(f"  r/{subreddit}: {len(posts)} posts via old.reddit HTML")
            return posts
    return []


def _fetch_subreddit(subreddit: str, sort: str, seen: set[str]) -> list[CandidatePost]:
    print(f"Fetching Reddit r/{subreddit} ({sort})...")

    # GHA: archives first so we do not burn the run on 403/429.
    # Home IP: official RSS still works, try that first.
    if _in_github_actions():
        steps = (
            ("Arctic Shift", lambda: _fetch_arctic_shift(subreddit, seen)),
            ("PullPush", lambda: _fetch_pullpush(subreddit, seen)),
            ("official Reddit", lambda: _fetch_official_reddit(subreddit, sort, seen)),
        )
    else:
        steps = (
            ("official Reddit", lambda: _fetch_official_reddit(subreddit, sort, seen)),
            ("Arctic Shift", lambda: _fetch_arctic_shift(subreddit, seen)),
            ("PullPush", lambda: _fetch_pullpush(subreddit, seen)),
        )

    for label, fetch in steps:
        posts = fetch()
        if posts:
            if label != "official Reddit":
                print(f"  r/{subreddit}: {len(posts)} posts via {label}")
            return posts

    print(f"  r/{subreddit}: all endpoints blocked or empty")
    return []


class RedditSource:
    """
    r/csharp and r/dotnet.

    Reddit often slams the door on GitHub's servers. We knock a few different
    doors (RSS, old HTML, Arctic Shift copy) until one opens.
    """

    def fetch(self) -> list[CandidatePost]:
        subreddits = ["csharp", "dotnet"]
        sort = "top" if datetime.now().weekday() % 2 == 0 else "hot"
        posts: list[CandidatePost] = []
        seen: set[str] = set()

        for index, subreddit in enumerate(subreddits):
            if index > 0:
                time.sleep(5)
            posts.extend(_fetch_subreddit(subreddit, sort, seen))

        print(f"Total Reddit posts collected: {len(posts)}")
        return posts
