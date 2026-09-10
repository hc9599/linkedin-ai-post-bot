"""
Pull 2-3 key facts from a blurb. Pass 1 gets these, not the full article.
Forces a take instead of a summary rewrite.
"""
import re

from linkedin_bot.discovery import Focus
from linkedin_bot.models import CandidatePost
from linkedin_bot.niche import NicheProfile
from linkedin_bot.sources.relevance import is_relevant, topic_overlap_score

_SPLIT = re.compile(r"(?<=[.!?])\s+")
_FACTISH = re.compile(
    r"\d|[\"']|\bsdk\b|\bapi\b|preview|breaking",
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


def _score_post(post: CandidatePost, profile: NicheProfile, focus: Focus) -> float:
    overlap = topic_overlap_score(post.title, post.summary, focus.topic)
    relevant = 1.0 if is_relevant(post.title, post.summary, profile.relevance_keywords) else 0.0
    reactions = float(post.reactions)
    max_reactions = max(reactions, 1.0)
    normalized = reactions / max_reactions if reactions else 0.0
    return overlap * 3.0 + relevant * 2.0 + normalized


def pick_article(
    posts: list[CandidatePost],
    profile: NicheProfile,
    focus: Focus,
    exclude_titles: tuple[str, ...] = (),
) -> CandidatePost:
    """
    Lock one article before any LLM call.

    Prefer niche-relevant posts that match the focus topic; then reactions.
    `exclude_titles` (case-insensitive, whitespace-collapsed) is used by the
    dedup gate to avoid re-using a recently-published source article.
    Raises ValueError if no candidate remains after exclusion.
    """
    if not posts:
        raise ValueError("No posts to pick from")

    normalized_exclude = {
        " ".join(t.lower().split()) for t in exclude_titles if t
    }

    def _is_excluded(post: CandidatePost) -> bool:
        return " ".join(post.title.lower().split()) in normalized_exclude

    relevant = [
        p for p in posts
        if is_relevant(p.title, p.summary, profile.relevance_keywords)
        and not _is_excluded(p)
    ]
    # If filtering left nothing, fall back to the full pool minus excluded ones
    pool = relevant or [p for p in posts if not _is_excluded(p)]
    if not pool:
        raise ValueError("No posts to pick from after exclude_titles filter")
    scored = sorted(pool, key=lambda p: _score_post(p, profile, focus), reverse=True)
    best = scored[0]

    if focus.topic and topic_overlap_score(best.title, best.summary, focus.topic) == 0.0:
        print(
            f"Pick: no strong topic overlap for {focus.topic!r}; "
            f"using best niche match by reactions: {best.title[:70]}"
        )
    return best
