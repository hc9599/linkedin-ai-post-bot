"""
Trending-world hooks for the opener. Not LinkedIn source articles.

Live headlines when a feed answers and the topic is safe to joke about.
Daily-life scenes are the fallback if news is empty or nothing analogizes.
"""
from dataclasses import dataclass
from datetime import datetime
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

# Safe any day. No weekday names so we do not say Friday on a Monday.
DAILY_LIFE_ANYDAY = [
    "Coffee going cold while the build sits on 'restore'.",
    "Unread group chat about last night's match. You keep it. You never open it.",
    "Airport Wi-Fi deciding your VPN is a suggestion.",
    "Power flicker right as the build hits 99%.",
    "Hybrid day: badge in, sit down, VPN dies.",
    "Office microwave queue longer than the PR review.",
    "Slack huddle with IPL or the Premier League muted in another tab.",
    "Commute stretching a 20-minute hop into a standup from the cab.",
    "Calendar saying 'focus time' while pings keep landing.",
    "That one test that only fails on the pipeline.",
    "Leaving on time and still hitting the same traffic light twice.",
]

# Mood of the calendar day. Hook must feel like this, even if the weekday word is omitted.
DAY_VIBES = {
    0: (
        "Monday hectic office. Weekend inbox dump. Standup that should have been "
        "a Slack. Already late before the first real coding hour. "
        "Not relaxed. Not Friday-deploy. No clock times (no 10 am, no 9:30)."
    ),
    1: (
        "Tuesday already-behind. Monday leftovers still open. The flaky test came back. "
        "The week has started for real. Not a fresh-start Monday. Not Friday-deploy."
    ),
    2: (
        "Wednesday midweek grind. Calendar ate the only coding block. This is when "
        "the red build likes to live. Hump day, not a restart and not a wind-down."
    ),
    3: (
        "Thursday almost-Friday pressure. People say ship tomorrow. Tomorrow is not "
        "today. Do not celebrate. Do not write Friday-deploy jokes."
    ),
    4: (
        "Friday deploy nerves. People are already mentally gone. Someone still wants "
        "to click ship. Friday-deploy language is allowed today only."
    ),
    5: (
        "Saturday should-not-be-here. A 'quick prod check' that is never quick. "
        "Slightly annoyed you opened the laptop."
    ),
    6: (
        "Sunday scaries. Work laptop already open. Tomorrow's standup is already "
        "in your head. Quiet dread, not a Monday fire drill yet."
    ),
}

# Only mix these in on that weekday. Always include them so the hook can sound like today.
DAILY_LIFE_BY_WEEKDAY = {
    0: [
        "Monday standup that should have been a message.",
        "Inbox from the weekend pretending it is urgent.",
        "First Slack of the week is already a fire drill.",
        "Badge reader arguing with last week's access.",
        "First calendar block already a 'quick sync'.",
        "Weekend PR comments waiting like they slept there.",
        "Commute cab, laptop on knees, VPN dying.",
        "Desk still has Friday's sticky notes.",
    ],
    1: [
        "Tuesday and the flaky test is already back.",
        "Monday leftovers still sitting in the inbox.",
        "Already behind and it is only Tuesday.",
    ],
    2: [
        "Wednesday midweek CI. This is where the red build likes to live.",
        "Hump-day calendar ate the only coding block.",
        "Halfway through the week and the quiet hour is gone.",
    ],
    3: [
        "Thursday 'ship it tomorrow' pressure. Not tomorrow yet.",
        "Almost Friday. Nobody say it out loud.",
        "Thursday afternoon and the review pile doubled.",
    ],
    4: [
        "Friday deploy energy. Everyone knows better. Someone still clicks.",
        "Friday afternoon CI. Nobody wants to own the red build.",
        "Half the office already mentally gone. Prod is still here.",
    ],
    5: [
        "Saturday and a 'quick prod check' that is never quick.",
        "Weekend laptop. You promised you would not.",
    ],
    6: [
        "Sunday evening already opening the work laptop.",
        "Sunday scaries: tomorrow's standup is already in your head.",
    ],
}


@dataclass(frozen=True)
class WorldHeadline:
    title: str
    summary: str


@dataclass(frozen=True)
class WorldHookSet:
    headlines: list[WorldHeadline]
    routines: list[str]
    weekday_name: str
    day_vibe: str

    def prompt_block(self) -> str:
        """Text the writer sees. Headlines optional. Routines always there."""
        lines = [
            f"TODAY IS {self.weekday_name}.",
            f"DAY VIBE: {self.day_vibe}",
            (
                f"The opener MUST feel like {self.weekday_name}. You do not have to say "
                f"the word {self.weekday_name}, but a coworker should guess the day "
                "from the scene. Prefer a weekday-specific scene over generic coffee "
                "or microwave. If the hook could be pasted on any other weekday "
                "unchanged, rewrite it."
            ),
            f"If you name a weekday, it must be {self.weekday_name}.",
            "Friday-deploy / Friday roulette language is ONLY allowed on Friday.",
            "TRENDING HOOKS (opener material, not the post topic):",
        ]
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


def current_day_context() -> tuple[str, str, int]:
    """(weekday name, vibe text, weekday index). Uses the process timezone."""
    now = datetime.now()
    weekday = now.weekday()
    return now.strftime("%A"), DAY_VIBES[weekday], weekday


def fetch_world_hooks(*, headline_limit: int = 6, routine_count: int = 2) -> WorldHookSet:
    """
    Live world/tech/sport headlines if a feed works and topics are safe.
    Always include today's weekday scenes, plus a couple of any-day fallbacks.
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

    now = datetime.now()
    weekday = now.weekday()
    weekday_name = now.strftime("%A")
    day_vibe = DAY_VIBES[weekday]
    weekday_scenes = list(DAILY_LIFE_BY_WEEKDAY.get(weekday, []))
    extra = random.sample(DAILY_LIFE_ANYDAY, k=min(routine_count, len(DAILY_LIFE_ANYDAY)))
    routines = weekday_scenes + extra
    print(f"  Today is {weekday_name}")
    print(f"  Day vibe: {day_vibe}")
    print("  Daily-life scenes:")
    for scene in routines:
        print(f"    - {scene}")
    for item in headlines:
        print(f"    - headline: {item.title}")

    return WorldHookSet(
        headlines=headlines,
        routines=routines,
        weekday_name=weekday_name,
        day_vibe=day_vibe,
    )
