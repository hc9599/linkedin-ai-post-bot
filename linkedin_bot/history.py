"""
Remember recent LinkedIn drafts so the next run does not reuse the same opener or article.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import re

from linkedin_bot.cleaning import strip_topic_line

MAX_POSTS = 24
_VIBE_MARKERS = {
    "phone", "charger", "pizza", "leftover", "leftovers", "microwave",
    "standup", "inbox", "laundry", "groceries", "airport", "commute",
    "coffee", "toast", "gym", "sushi", "match", "highlights",
}

_STOP = {
    "a", "an", "the", "and", "or", "to", "of", "in", "on", "my", "i", "im",
    "is", "are", "from", "that", "this", "with", "while", "still", "just",
    "already", "gone", "full", "got",
}


@dataclass
class HistoricPost:
    date: str
    weekday: str
    topic: str
    opener: str
    source_link: str
    dry_run: bool


def first_line(text: str) -> str:
    """First real sentence of the post. Skips TOPIC and hashtags."""
    body = strip_topic_line(text or "")
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", (text or "").lower())


def opener_tokens(text: str) -> set[str]:
    return {
        tok for tok in _norm(first_line(text)).split()
        if len(tok) > 3 and tok not in _STOP
    }


def _marker_hits(tokens: set[str]) -> set[str]:
    """Match coffee's / coffees to coffee, leftovers to leftover."""
    hits: set[str] = set()
    for tok in tokens:
        for mark in _VIBE_MARKERS:
            if tok == mark or tok.startswith(mark) or mark.startswith(tok):
                hits.add(mark)
    return hits


def opener_overlap(left: str, right: str) -> float:
    """Share of the shorter opener that also appears in the longer one."""
    a = opener_tokens(left)
    b = opener_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def default_history_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "post_history.json"


class PostHistory:
    """JSON file of recent finals. Lives in the repo so Actions can commit it back."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_history_path()
        self.posts: list[HistoricPost] = []

    def load(self) -> PostHistory:
        if not self.path.exists():
            print(f"Post history: none yet ({self.path})")
            return self
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.posts = [HistoricPost(**item) for item in raw.get("posts", [])]
        print(f"Post history: {len(self.posts)} prior post(s)")
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"posts": [asdict(post) for post in self.posts[-MAX_POSTS:]]}
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Post history: wrote {len(self.posts[-MAX_POSTS:])} post(s) to {self.path}")

    def record(
        self,
        *,
        topic: str,
        body: str,
        source_link: str,
        dry_run: bool,
    ) -> None:
        now = datetime.now()
        self.posts.append(
            HistoricPost(
                date=now.strftime("%Y-%m-%d"),
                weekday=now.strftime("%A"),
                topic=(topic or "").strip(),
                opener=first_line(body),
                source_link=source_link or "",
                dry_run=dry_run,
            )
        )
        if len(self.posts) > MAX_POSTS:
            self.posts = self.posts[-MAX_POSTS:]

    def recent_openers(self, limit: int = 12) -> list[str]:
        return [post.opener for post in self.posts[-limit:] if post.opener]

    def recent_topics(self, limit: int = 12) -> list[str]:
        return [post.topic for post in self.posts[-limit:] if post.topic]

    def reused_opener(self, text: str, threshold: float = 0.55) -> bool:
        return any(opener_overlap(text, old) >= threshold for old in self.recent_openers())

    def reused_topic(self, topic: str) -> bool:
        want = _norm(topic)
        if not want:
            return False
        return any(_norm(old) == want or want in _norm(old) or _norm(old) in want for old in self.recent_topics())

    def unused_articles(self, posts: list) -> list:
        """Articles we have not already written about."""
        return [post for post in posts if not self.reused_topic(getattr(post, "title", ""))]

    def drop_used_articles(self, posts: list) -> list:
        """Drop articles we already wrote about, if enough unused ones remain."""
        unused = [post for post in posts if not self.reused_topic(getattr(post, "title", ""))]
        dropped = len(posts) - len(unused)
        if dropped and len(unused) >= 3:
            print(f"History: dropped {dropped} already-used article(s), {len(unused)} left")
            return unused
        if dropped:
            print(f"History: {dropped} reused article(s), but only {len(unused)} unused — keeping full list")
        return posts

    def used_vibe_markers(self) -> set[str]:
        """Concrete scene nouns already used. Next hook cannot reuse these."""
        used: set[str] = set()
        for opener in self.recent_openers():
            used |= _marker_hits(opener_tokens(opener))
        return used

    def scene_blocked(self, scene: str) -> bool:
        """True if this scene remixed a recent opener or a used vibe noun."""
        if self.reused_opener(scene, threshold=0.40):
            return True
        return bool(_marker_hits(opener_tokens(scene)) & self.used_vibe_markers())

    def worn_opener_words(self) -> list[str]:
        """Words that showed up in 2+ recent first lines. Do not open with these again."""
        counts: dict[str, int] = {}
        for opener in self.recent_openers(8):
            for tok in opener_tokens(opener):
                counts[tok] = counts.get(tok, 0) + 1
        worn = sorted(word for word, count in counts.items() if count >= 2)
        return worn[:12]

    def prompt_block(self, extra_openers: list[str] | None = None) -> str:
        openers = self.recent_openers() + [line for line in (extra_openers or []) if line]
        topics = self.recent_topics()
        worn = self.worn_opener_words()
        for extra in extra_openers or []:
            worn.extend(sorted(opener_tokens(extra)))
        worn = sorted(set(worn))
        if not openers and not topics:
            return "RECENT POSTS: none stored. Still write a fresh first line."

        lines = [
            "RECENT POSTS — do not repeat these.",
            "First line must be a new life scene with new words. Not the office.",
            "Do not reuse a vibe noun we already used (phone, charger, leftover, pizza, commute, etc.).",
        ]
        if topics:
            lines.append("Topics already used (pick a different article if the list has one):")
            for topic in topics:
                lines.append(f"- {topic}")
        if openers:
            lines.append("Opening lines already used:")
            for opener in openers:
                lines.append(f"- {opener}")
        if worn:
            lines.append("Do not open with these worn words: " + ", ".join(worn))
        markers = self.used_vibe_markers()
        if markers:
            lines.append("Banned vibe nouns this run: " + ", ".join(sorted(markers)))
        return "\n".join(lines)
