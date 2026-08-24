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

# Safe any day. Life, not the office. No weekday names so we do not say Friday on a Monday.
DAILY_LIFE_ANYDAY = [
    "Same traffic light twice. You were not even rushing.",
    "Neighbor drilling through a wall that did nothing to them.",
    "Rain starting the second you leave the building.",
    "Series paused on the 'are you still watching' screen.",
    "Delivery guy calling from a gate that has no nameplate.",
    "Power flicker right as the kettle clicks.",
    "Keys not on the hook. They never are.",
    "Plant leaning like it wants a lawyer.",
    "Elevator skipped your floor for sport.",
    "Shoes by the door still wet.",
    "Bus you just missed, still visible.",
    "Same song stuck from yesterday.",
    "Tea bag still in last night's mug.",
    "Umbrella in the bag. Sun out.",
    "Fridge making a new noise. You pretend not to hear it.",
    "Parcel photo that is not your door.",
    "Bookmark on a recipe you will not cook.",
    "Neighbor's Wi-Fi name you keep almost joining.",
]

# Mood of the calendar day. Life energy, not office furniture.
DAY_VIBES = {
    0: (
        "Monday life hangover. Weekend still in your head. Alarm lost. "
        "A bit late, a bit behind. Casual home or commute life. "
        "Not an office tour. No standup, inbox, Slack, badge, or meeting. "
        "No clock times. Do not reuse a scene noun from recent posts."
    ),
    1: (
        "Tuesday already-tired. Same leftovers. How is it Tuesday already. "
        "Week started for real. Still life, not a desk tour. "
        "No standup or inbox dump. Not Friday-deploy."
    ),
    2: (
        "Wednesday midweek slump. Forgot what day it is. Weather doing too much. "
        "Halfway, not a restart and not a wind-down. Life scene, not a calendar."
    ),
    3: (
        "Thursday almost-weekend itch. Plans starting to form. Not Friday yet. "
        "Do not write Friday-deploy jokes. Keep it outside the office."
    ),
    4: (
        "Friday brain already at dinner plans. People mentally gone. "
        "Friday-deploy language is allowed today only, and only if it fits. "
        "Prefer weekend-eve life over a war room."
    ),
    5: (
        "Saturday should-be-off. Errands. A laptop you promised not to open. "
        "Slightly annoyed you peeked anyway."
    ),
    6: (
        "Sunday scaries on the couch. Tomorrow already lurking. "
        "Quiet dread, not a Monday fire drill. No standup."
    ),
}

# Only mix these in on that weekday. Life scenes so the hook can sound like today.
DAILY_LIFE_BY_WEEKDAY = {
    0: [
        "Alarm lost the argument. Weekend is still in the room.",
        "Keys not on the hook. Monday already winning.",
        "Plant leaning like it paid rent and you did not.",
        "Bus you just missed. You watch it leave.",
        "Tea bag still in last night's mug.",
        "Shoes by the door still wet from who-knows-when.",
    ],
    1: [
        "Same leftovers. Tuesday already feels used.",
        "You blinked and Monday was gone.",
        "That one sock from the weekend wash is still missing.",
    ],
    2: [
        "Hump-day weather cannot pick a side.",
        "Forgot it was Wednesday until someone said it.",
        "Midweek and the quiet hour never showed up.",
    ],
    3: [
        "Thursday and weekend plans are still a group-chat maybe.",
        "Almost Friday. Nobody say it out loud.",
        "You can taste Friday. It is not here.",
    ],
    4: [
        "Friday brain already picking a place to eat.",
        "Half your friends already mentally gone.",
        "Weekend bag by the door. You are still here.",
    ],
    5: [
        "Saturday errands eating the only free block.",
        "You promised the laptop would stay shut. It did not.",
    ],
    6: [
        "Sunday couch, tomorrow already tapping your shoulder.",
        "Sunday scaries: you are mentally packing for a day that is not here yet.",
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
                f"The opener MUST feel like {self.weekday_name} in real life "
                "(home, commute, food, sport, phone) — not the office. "
                f"You do not have to say the word {self.weekday_name}. "
                "No standup, inbox, Slack, badge, calendar invite, or PR review. "
                "If the hook could be pasted on any other weekday unchanged, rewrite it."
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


def _fresh_scenes(pool: list[str], history, limit: int) -> list[str]:
    """Pick scenes that do not remix a recent opener or used vibe noun."""
    if history is None:
        chosen = list(pool)
    else:
        chosen = [scene for scene in pool if not history.scene_blocked(scene)]
        blocked = len(pool) - len(chosen)
        if blocked:
            print(f"  Vibe filter: dropped {blocked} worn scene(s), {len(chosen)} left")
        if len(chosen) < limit:
            leftover = [scene for scene in pool if scene not in chosen]
            chosen.extend(leftover)
    random.shuffle(chosen)
    return chosen[:limit]


def fetch_world_hooks(*, headline_limit: int = 6, routine_count: int = 2, history=None) -> WorldHookSet:
    """
    Live world/tech/sport headlines if a feed works and topics are safe.
    Mix today's weekday life scenes with any-day life scenes. Shuffle so hooks stay random.
    """
    print("Fetching daily-life hooks...")
    collected: list[WorldHeadline] = []
    seen: set[str] = set()
    headlines: list[WorldHeadline] = []
    if headline_limit <= 0:
        print("  Headlines: skipped")
    else:
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
    weekday_pool = list(DAILY_LIFE_BY_WEEKDAY.get(weekday, []))
    weekday_scenes = _fresh_scenes(weekday_pool, history, max(1, routine_count))
    extra = _fresh_scenes(DAILY_LIFE_ANYDAY, history, max(1, routine_count))
    routines = (weekday_scenes + extra)[: max(1, routine_count)]
    random.shuffle(routines)
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
