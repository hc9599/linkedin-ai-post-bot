"""
Pass 4 — variance injection.

Last 5 openers live in a small JSON file. If the new first line clones a
recent shape (question, So,, same first words), re-roll Pass 1.
"""
from dataclasses import dataclass
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


@dataclass
class LoopState:
    openers: list[dict]

    @classmethod
    def load(cls, path: Path = STATE_PATH) -> "LoopState":
        if not path.exists():
            return cls(openers=[])
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(openers=list(raw.get("openers") or []))

    def save(self, path: Path = STATE_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"openers": self.openers[-_KEEP:]}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Pass 4 — wrote {len(self.openers[-_KEEP:])} opener(s) to {path}")

    def recent_shapes(self) -> list[str]:
        return [row.get("shape", "") for row in self.openers[-_KEEP:]]

    def recent_hashes(self) -> set[str]:
        return {row.get("hash", "") for row in self.openers[-_KEEP:]}

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

    def next_style(self) -> str:
        index = len(self.openers) % len(OPENER_STYLES)
        return OPENER_STYLES[index]

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
