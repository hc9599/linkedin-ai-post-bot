"""
Pass 4 — variance injection.

Last 5 openers and closers live in a small JSON file. If the new first line
clones a recent shape, re-roll Pass 1.
"""
from collections.abc import Sequence
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re

from linkedin_bot.cleaning import strip_topic_line
from linkedin_bot.generation.style import OPENER_STYLES

STATE_PATH = Path("data/loop_state.json")
_KEEP = 5


def first_line(text: str) -> str:
    body = strip_topic_line(text)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def last_content_line(text: str) -> str:
    body = strip_topic_line(text)
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines[-1] if lines else ""


def opener_shape(text: str) -> str:
    """Coarse structure so 'So, X' and 'So, Y' count as the same bot pattern."""
    line = first_line(text)
    lowered = line.lower().lstrip()
    if not lowered:
        return "empty"
    if lowered.endswith("?") or lowered.startswith(("how ", "why ", "what ", "ever ", "anyone ")):
        return "question"
    if lowered.startswith("so ") or lowered.startswith("so,"):
        return "so"
    words = re.findall(r"[a-z0-9']+", lowered)
    return "words:" + " ".join(words[:5])


def opener_hash(text: str) -> str:
    line = first_line(text).lower()
    return hashlib.sha1(line.encode("utf-8")).hexdigest()[:12]


def closer_hash(text: str) -> str:
    line = last_content_line(text).lower()
    return hashlib.sha1(line.encode("utf-8")).hexdigest()[:12]


@dataclass
class LoopState:
    openers: list[dict]
    closers: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = STATE_PATH) -> "LoopState":
        if not path.exists():
            return cls(openers=[], closers=[])
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            openers=list(raw.get("openers") or []),
            closers=list(raw.get("closers") or []),
        )

    def save(self, path: Path = STATE_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "openers": self.openers[-_KEEP:],
            "closers": self.closers[-_KEEP:],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(
            f"Pass 4 — wrote {len(payload['openers'])} opener(s), "
            f"{len(payload['closers'])} closer(s) to {path}"
        )

    def recent_shapes(self) -> list[str]:
        return [row.get("shape", "") for row in self.openers[-_KEEP:]]

    def recent_hashes(self) -> set[str]:
        return {row.get("hash", "") for row in self.openers[-_KEEP:]}

    def recent_closer_hashes(self) -> set[str]:
        return {row.get("hash", "") for row in self.closers[-_KEEP:]}

    def clashes(self, draft: str) -> bool:
        shape = opener_shape(draft)
        digest = opener_hash(draft)
        if digest in self.recent_hashes():
            print(f"Pass 4 — opener hash repeats ({digest})")
            return True
        if shape in self.recent_shapes():
            print(f"Pass 4 — opener shape repeats ({shape})")
            return True
        return False

    def closer_clashes(self, draft: str) -> bool:
        digest = closer_hash(draft)
        if digest in self.recent_closer_hashes():
            print(f"Pass 4 — closer hash repeats ({digest})")
            return True
        return False

    def next_style(self) -> str:
        index = len(self.openers) % len(OPENER_STYLES)
        return OPENER_STYLES[index]

    def next_closer(self, styles: Sequence[str]) -> str:
        if not styles:
            return "End with one specific developer question tied to the article."
        index = len(self.closers) % len(styles)
        return styles[index]

    def avoid_instruction(self, draft: str) -> str:
        shape = opener_shape(draft)
        extras = []
        if shape == "question":
            extras.append("avoid opening with a question")
        if shape == "so":
            extras.append("avoid opening with So,")
        extras.append("do not reuse the previous first line")
        return "Avoid these opener patterns: " + "; ".join(extras)

    def record(self, draft: str) -> None:
        self.openers.append({
            "text": first_line(draft),
            "shape": opener_shape(draft),
            "hash": opener_hash(draft),
        })
        self.openers = self.openers[-_KEEP:]
        self.save()

    def record_closer(self, draft: str) -> None:
        line = last_content_line(draft)
        if not line:
            return
        self.closers.append({
            "text": line,
            "hash": closer_hash(draft),
        })
        self.closers = self.closers[-_KEEP:]
        self.save()
