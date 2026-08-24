"""
Trending-world hooks for the opener. Not LinkedIn source articles.

Live headlines when a feed answers and the topic is safe to joke about.
Daily-life scenes are the fallback if news is empty or nothing analogizes.
"""
from dataclasses import dataclass
import random
import re

from linkedin_bot.http import fetch_feed_entries

FEED_URLS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "http://feeds.bbci.co.uk/sport/rss.xml",
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
]

# Never joke about these. Drop the headline entirely.
_UNSAFE = (
    "killed", "killing", "dead", "death", "deaths", "died", "murder",
    "rape", "raped", "suicide", "terror", "terrorist", "blast", "bomb",
    "communal", "riot", "riots", "massacre", "assault", "lynch",
    "molest", "abuse", "genocide", "casualty", "casualties", "funeral",
    "tragedy", "stampede", "earthquake", "flood", "cyclone", "landslide",
    "war", "missile", "shooting", "gunfire", "hostage", "abduct",
    "accident", "crash victims", "bodies recovered",
    "wildfire", "evacuate", "evacuation", "uncontained",
    "taliban", "child privacy", "under the age of 13",
    "children under", "minors",
)

DAILY_LIFE = [
    "Monday standup that should have been a message.",
    "Coffee going cold while the build sits on 'restore'.",
    "Unread group chat about last night's match. You keep it. You never open it.",
    "Friday deploy energy. Everyone knows better. Someone still clicks.",
    "Airport Wi-Fi deciding your VPN is a suggestion.",
    "Power flicker right as the build hits 99%.",
    "Hybrid day: badge in, sit down, VPN dies.",
    "Office microwave queue longer than the PR review.",
    "Weekend plan cancelled by a 'quick prod check' that is never quick.",
    "Slack huddle with IPL or the Premier League muted in another tab.",
    "Commute stretching a 20-minute hop into a standup from the cab.",
    "Calendar saying 'focus time' while pings keep landing.",
    "That one test that only fails on the pipeline.",
    "Leaving on time and still hitting the same traffic light twice.",
]


@dataclass(frozen=True)
class WorldHeadline:
    title: str
    summary: str


@dataclass(frozen=True)
class WorldHookSet:
    headlines: list[WorldHeadline]
    routines: list[str]

    def prompt_block(self) -> str:
        """Text the writer sees. Headlines optional. Routines always there."""
        lines = ["TRENDING HOOKS (opener material, not the post topic):"]
        if self.headlines:
            lines.append("Today's usable headlines (use ONE only if the analogy is obvious):")
            for item in self.headlines:
                extra = f" - {item.summary}" if item.summary else ""
                lines.append(f"- {item.title}{extra}")
        else:
            lines.append("No usable headlines today. Open on a daily-life scene instead.")

        lines.append("Daily-life scenes (pick one if no headline fits):")
        for scene in self.routines:
            lines.append(f"- {scene}")
        return "\n".join(lines)


def _plain(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _is_unsafe(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _UNSAFE)


def _headlines_from_feed(url: str, limit: int) -> list[WorldHeadline]:
    print(f"  World feed: {url}")
    entries = fetch_feed_entries(url)
    if not entries:
        return []

    picked: list[WorldHeadline] = []
    seen: set[str] = set()
    for entry in entries:
        title = _plain(entry.get("title", ""))
        if len(title) < 20:
            continue
        summary = _plain(entry.get("summary", ""))[:180]
        blob = f"{title} {summary}"
        if _is_unsafe(blob):
            continue
        key = re.sub(r"[^a-z0-9]+", "", title.lower())
        if key in seen:
            continue
        seen.add(key)
        picked.append(WorldHeadline(title=title, summary=summary))
        if len(picked) >= limit:
            break
    return picked


def fetch_world_hooks(*, headline_limit: int = 6, routine_count: int = 2) -> WorldHookSet:
    """
    Live world/tech/sport headlines if a feed works and topics are safe.
    Always include a couple of daily-life scenes as fallback.
    """
    print("Fetching trending hooks (headlines + daily life)...")
    collected: list[WorldHeadline] = []
    seen: set[str] = set()
    per_feed = max(2, headline_limit // 2)

    for url in FEED_URLS:
        for item in _headlines_from_feed(url, per_feed):
            key = re.sub(r"[^a-z0-9]+", "", item.title.lower())
            if key in seen:
                continue
            seen.add(key)
            collected.append(item)
        if len(collected) >= headline_limit:
            break

    headlines = collected[:headline_limit]
    if headlines:
        print(f"  Headlines kept: {len(headlines)}")
    else:
        print("  Headlines: none usable (feeds empty or all filtered)")

    routines = random.sample(DAILY_LIFE, k=min(routine_count, len(DAILY_LIFE)))
    print("  Daily-life scenes:")
    for scene in routines:
        print(f"    - {scene}")
    for item in headlines:
        print(f"    - headline: {item.title}")

    return WorldHookSet(headlines=headlines, routines=routines)
