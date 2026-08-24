"""Shared Pass 3 / Pass 5 reject-list matching."""
import re

from linkedin_bot.generation.style import PASS3_REJECT


def reject_hits(text: str) -> list[str]:
    """Terms from the reject-list that are still in the post."""
    low = text.lower()
    hits: list[str] = []
    for term in PASS3_REJECT:
        if term == "thoughts?":
            pattern = r"\bthoughts\?"
        elif term == "unlock":
            pattern = r"\bunlocks?\b"
        else:
            pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, low) and term not in hits:
            hits.append(term)
    return hits
