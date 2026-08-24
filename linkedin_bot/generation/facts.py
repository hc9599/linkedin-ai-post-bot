"""
Pull 2-3 key facts from a blurb. Pass 1 gets these, not the full article.
Forces a take instead of a summary rewrite.
"""
import re

from linkedin_bot.models import CandidatePost
from linkedin_bot.sources.relevance import is_dotnet_relevant

_SPLIT = re.compile(r"(?<=[.!?])\s+")
_FACTISH = re.compile(
    r"\d|[\"']|csharp|\.net|nuget|msbuild|\bsdk\b|\bapi\b|preview|breaking",
    re.IGNORECASE,
)


def key_facts(article: CandidatePost, limit: int = 3) -> list[str]:
    """Keep short, specific sentences. Skip empty fluff."""
    raw = (article.summary or "").strip()
    if not raw:
        return []
    sentences = [s.strip() for s in _SPLIT.split(raw) if len(s.strip()) > 20]
    if not sentences:
        clipped = raw[:280].strip()
        return [clipped] if clipped else []
    ranked = sorted(sentences, key=lambda s: (bool(_FACTISH.search(s)), len(s)), reverse=True)
    picked = ranked[:limit]
    return [s[:220] for s in picked]


def pick_article(posts: list[CandidatePost]) -> CandidatePost:
    """
    Lock one article before any Groq call.

    Prefer a clearly C#/.NET title/summary. Then highest reactions.
    """
    relevant = [p for p in posts if is_dotnet_relevant(p.title, p.summary)]
    pool = relevant or list(posts)
    return max(pool, key=lambda p: p.reactions)
