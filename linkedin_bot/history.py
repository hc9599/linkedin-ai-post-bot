"""
Durable history of published posts.

`PostHistoryStore` reads/writes `data/post_history.json` — keyed by niche_id,
oldest-first per niche, capped at the configured retention. Used by
`linkedin_bot.bot` to (a) record what we just published and (b) compare a
new draft against recent posts in the same niche.

History is an optimization, not a source of truth. A missing or corrupt
file MUST NOT crash the bot — load() returns an empty store and logs a
warning. Writes are atomic via temp file + os.replace.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_HISTORY_PATH = Path("data/post_history.json")
DEFAULT_RETENTION = 30

# Stopwords mirror linkedin_bot/review.py. Anything here is filtered out
# before computing Jaccard similarity so common words ("the", "for", "is")
# don't dominate the score.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "for", "with", "and", "of", "to", "in", "on",
        "from", "into", "how", "why", "what", "that", "this", "your",
        "is", "are", "was", "were", "be", "been", "being", "as", "at",
        "by", "but", "or", "if", "so", "than", "then", "too", "very",
        "can", "will", "just", "do", "does", "did",
    }
)


@dataclass(frozen=True)
class PostRecord:
    """One published post. Persisted as a JSON object per the contracts."""
    date: str  # YYYY-MM-DD in bot's local time
    niche_id: str
    body: str  # post body only — no TOPIC, hashtags, or Source credit
    normalized_text: str  # human-readable normalized form
    token_set: tuple[str, ...]  # JSON serializes frozenset as sorted list
    article_title: str
    article_link: str

    def tokens(self) -> frozenset[str]:
        return frozenset(self.token_set)


# --- normalization ----------------------------------------------------------

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, drop stopwords, collapse whitespace.

    Returns the joined normalized form (human-readable) — what we persist to
    `normalized_text` so operators can inspect the file and read it.
    """
    lowered = text.lower()
    no_punct = _PUNCT_RE.sub(" ", lowered)
    collapsed = _WS_RE.sub(" ", no_punct).strip()
    if not collapsed:
        return ""
    kept = [w for w in collapsed.split(" ") if w and w not in STOPWORDS and len(w) > 2]
    return " ".join(kept)


def token_set(text: str) -> frozenset[str]:
    """Return the frozenset of remaining tokens for `text`.

    Used for Jaccard comparisons and persisted on PostRecord.token_set so
    we never have to re-tokenize on read.
    """
    lowered = text.lower()
    no_punct = _PUNCT_RE.sub(" ", lowered)
    collapsed = _WS_RE.sub(" ", no_punct).strip()
    if not collapsed:
        return frozenset()
    return frozenset(
        w for w in collapsed.split(" ")
        if w and w not in STOPWORDS and len(w) > 2
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity over two token sets. Returns 0.0 if either is empty."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    if intersection == 0:
        return 0.0
    return intersection / float(len(a | b))


# --- store ------------------------------------------------------------------


class PostHistoryStore:
    """In-memory cache backed by `data/post_history.json`.

    Per-niche lists are oldest-first. The store never raises on load —
    missing or corrupt files return an empty store with a logged warning.
    Writes are atomic via a temp file plus os.replace.
    """

    def __init__(self, data: dict[str, list[PostRecord]] | None = None, path: Path = DEFAULT_HISTORY_PATH):
        self._data: dict[str, list[PostRecord]] = data or {}
        self._path = path

    @classmethod
    def load(cls, path: Path = DEFAULT_HISTORY_PATH) -> "PostHistoryStore":
        """Load the store. Never raises. Logs warnings on degraded files."""
        if not path.exists():
            print(f"History: {path} missing — starting empty store")
            return cls(path=path)

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"WARNING: History: cannot read {path} ({exc}) — starting empty store")
            return cls(path=path)

        if not raw.strip():
            print(f"History: {path} is empty — starting empty store")
            return cls(path=path)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"WARNING: History: {path} is corrupt JSON ({exc.msg}) — starting empty store")
            return cls(path=path)

        if not isinstance(parsed, dict):
            print(f"WARNING: History: {path} root is not an object — starting empty store")
            return cls(path=path)

        data: dict[str, list[PostRecord]] = {}
        total = 0
        for niche_id, entries in parsed.items():
            if not isinstance(entries, list):
                print(f"WARNING: History: niche {niche_id!r} value is not a list — dropped")
                continue
            valid: list[PostRecord] = []
            for entry in entries:
                record = _parse_record(niche_id, entry)
                if record is not None:
                    valid.append(record)
            data[niche_id] = valid
            total += len(valid)

        if total == 0:
            print("History: empty store, dedup disabled for this run")
        else:
            print(f"History: loaded {total} records across {len(data)} niches")
        return cls(data=data, path=path)

    def save(self) -> None:
        """Atomic write via temp file + os.replace."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, list[dict]] = {}
        for niche_id, records in self._data.items():
            payload[niche_id] = [
                {
                    "date": r.date,
                    "niche_id": r.niche_id,
                    "body": r.body,
                    "normalized_text": r.normalized_text,
                    "token_set": sorted(r.token_set),
                    "article_title": r.article_title,
                    "article_link": r.article_link,
                }
                for r in records
            ]
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self._path)

    def record(self, post: PostRecord, retention: int) -> None:
        """Append a record, groom to retention, and save."""
        bucket = self._data.setdefault(post.niche_id, [])
        bucket.append(post)
        self._data[post.niche_id] = sorted(bucket, key=_record_sort_key)[-retention:]
        self.save()

    def groom(self, retention: int) -> int:
        """Trim each niche to the most recent `retention` records. Returns count dropped."""
        dropped = 0
        for niche_id, records in list(self._data.items()):
            sorted_records = sorted(records, key=_record_sort_key)
            kept = sorted_records[-retention:]
            dropped += len(records) - len(kept)
            self._data[niche_id] = kept
            if not kept:
                self._data.pop(niche_id, None)
        if dropped:
            self.save()
        return dropped

    def recent_article_titles(self, niche_id: str, k: int = 5) -> list[str]:
        """Return the most recent `k` article titles for `niche_id`."""
        bucket = self._data.get(niche_id, [])
        # bucket is oldest-first; take the last k
        return [r.article_title for r in bucket[-k:]]

    def find_similar(
        self,
        post: PostRecord,
        niche_id: str,
        threshold: float = 0.85,
    ) -> tuple[float, PostRecord | None]:
        """Return (max_jaccard, matched_record). Score 0.0 if no history."""
        bucket = self._data.get(niche_id, [])
        if not bucket:
            return 0.0, None
        candidate_tokens = token_set(post.body)
        if not candidate_tokens:
            return 0.0, None
        best_score = 0.0
        best_match: PostRecord | None = None
        for existing in bucket:
            score = jaccard(candidate_tokens, existing.tokens())
            if score > best_score:
                best_score = score
                best_match = existing
        return best_score, best_match

    def all_records(self) -> list[PostRecord]:
        """Flat list of every record across every niche — used for tests/observability."""
        return [r for records in self._data.values() for r in records]


# --- helpers ---------------------------------------------------------------


def _parse_record(niche_id: str, entry: object) -> PostRecord | None:
    """Parse one JSON entry into a PostRecord, or log+skip on bad shape."""
    if not isinstance(entry, dict):
        print(f"WARNING: History: skipping non-object entry under {niche_id!r}")
        return None
    try:
        date = str(entry["date"]).strip()
        body = str(entry["body"])
        normalized_text = str(entry.get("normalized_text") or "")
        token_list = entry.get("token_set")
        if not isinstance(token_list, list):
            token_list = list(token_set(body))
        article_title = str(entry.get("article_title") or "").strip()
        article_link = str(entry.get("article_link") or "").strip()
    except KeyError as exc:
        print(f"WARNING: History: skipping entry missing field {exc} under {niche_id!r}")
        return None
    return PostRecord(
        date=date,
        niche_id=niche_id,
        body=body,
        normalized_text=normalized_text,
        token_set=tuple(str(t) for t in token_list),
        article_title=article_title,
        article_link=article_link,
    )


def _record_sort_key(record: PostRecord) -> tuple[str, str]:
    """Sort by (date, article_link) so identical dates keep a stable order."""
    return (record.date, record.article_link)


def build_post_record(
    *,
    body: str,
    niche_id: str,
    article_title: str,
    article_link: str,
    date: str | None = None,
) -> PostRecord:
    """Build a PostRecord from a finalized post body. Used by the bot."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    normalized = normalize(body)
    return PostRecord(
        date=date,
        niche_id=niche_id,
        body=body,
        normalized_text=normalized,
        token_set=tuple(sorted(token_set(body))),
        article_title=article_title,
        article_link=article_link,
    )
