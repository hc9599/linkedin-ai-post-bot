"""
Niche relevance and topic matching for article candidates.
"""
import re

_STOP_WORDS = {
    "a", "an", "the", "for", "with", "and", "of", "to", "in", "on",
    "from", "into", "how", "why", "what", "that", "this", "your",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", value.lower()).strip()


def _tokens(value: str) -> set[str]:
    return {t for t in _norm(value).split() if len(t) > 2 and t not in _STOP_WORDS}


def is_relevant(title: str, summary: str, keywords: list[str]) -> bool:
    """True if title or summary mentions any niche keyword."""
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in keywords)


def matches_topic(title: str, summary: str, topic: str) -> bool:
    """True if topic tokens overlap title/summary."""
    if not topic.strip():
        return False
    topic_tokens = _tokens(topic)
    if not topic_tokens:
        return False
    text_tokens = _tokens(title + " " + summary)
    return bool(topic_tokens & text_tokens)


def topic_overlap_score(title: str, summary: str, topic: str) -> float:
    """Share of topic tokens found in title/summary. 0.0–1.0."""
    topic_tokens = _tokens(topic)
    if not topic_tokens:
        return 0.0
    text_tokens = _tokens(title + " " + summary)
    if not text_tokens:
        return 0.0
    return len(topic_tokens & text_tokens) / len(topic_tokens)
