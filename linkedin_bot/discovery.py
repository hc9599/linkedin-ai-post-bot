"""
Topic and trend discovery for niche-focused curation.

Manual mode: operator passes --topic.
Trend mode: Groq picks a hot trend from pulse + niche feed titles.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from linkedin_bot.http import fetch_json
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost
from linkedin_bot.niche import NicheProfile


@dataclass(frozen=True)
class Focus:
    topic: str
    angle: str
    mode: Literal["manual", "trend"]


def fetch_pulse_titles(profile: NicheProfile, *, limit: int = 20) -> list[str]:
    """Fetch broad tech story titles from HN for trend discovery only."""
    titles: list[str] = []
    seen: set[str] = set()
    window_days = 14 if datetime.now().weekday() >= 5 else 7
    created_after = int(time.time()) - window_days * 24 * 3600

    for query in profile.pulse_queries:
        print(f"Fetching pulse: '{query}'...")
        payload = fetch_json(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": query,
                "tags": "story",
                "numericFilters": f"created_at_i>{created_after}",
                "hitsPerPage": 10,
            },
        )
        if not isinstance(payload, dict):
            continue
        for hit in payload.get("hits", []):
            title = (hit.get("title") or "").strip()
            if len(title) < 20 or title in seen:
                continue
            seen.add(title)
            titles.append(title)
            if len(titles) >= limit:
                return titles
        time.sleep(0.3)

    print(f"Pulse titles collected: {len(titles)}")
    return titles


def _top_niche_title(posts: list[CandidatePost]) -> str:
    if not posts:
        return "technology trend"
    ranked = sorted(posts, key=lambda p: p.reactions, reverse=True)
    return ranked[0].title


def _parse_trend_json(raw: str) -> dict[str, str] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    trend = str(data.get("trend") or "").strip()
    angle = str(data.get("niche_angle") or data.get("angle") or "").strip()
    if not trend:
        return None
    return {"trend": trend, "niche_angle": angle}


def resolve_focus(
    llm: LLMClient,
    profile: NicheProfile,
    niche_posts: list[CandidatePost],
    pulse_titles: list[str],
    topic: str | None,
) -> Focus:
    """Resolve manual or trend focus before article pick and generation."""
    if topic and topic.strip():
        manual_topic = topic.strip()
        print(f"Focus: mode=manual topic={manual_topic!r}")
        return Focus(
            topic=manual_topic,
            angle=profile.default_angle,
            mode="manual",
        )

    niche_titles = [
        p.title for p in sorted(niche_posts, key=lambda x: x.reactions, reverse=True)[:8]
    ]
    prompt = f"""You pick today's tech trend and map it to {profile.display_name}.

NICHE FEED TITLES (recent, on-niche):
{chr(10).join(f"- {t}" for t in niche_titles) or "- (none)"}

BROADER TECH PULSE TITLES:
{chr(10).join(f"- {t}" for t in pulse_titles[:12]) or "- (none)"}

Reply with JSON only:
{{"trend": "short trend label", "niche_angle": "how a {profile.display_name} developer should react", "why": "one sentence"}}

Rules:
- trend must come from the pulse or niche titles, not invented
- niche_angle must stay in {profile.display_name} world
- no markdown fences
"""
    result = llm.complete(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    )
    if result:
        parsed = _parse_trend_json(result)
        if parsed:
            angle = parsed.get("niche_angle") or profile.default_angle
            print(f"Focus: mode=trend trend={parsed['trend']!r} angle={angle!r}")
            return Focus(topic=parsed["trend"], angle=angle, mode="trend")

    fallback = _top_niche_title(niche_posts)
    print(f"Focus: mode=trend fallback topic={fallback!r}")
    return Focus(topic=fallback, angle=profile.default_angle, mode="trend")
