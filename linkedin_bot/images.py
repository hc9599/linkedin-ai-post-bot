"""
Optional picture for the post.

Render path: AI-extracted 4-zone layout + designer-grade HTML/CSS template
+ Playwright headless Chromium → 1080x1350 PNG. Single path, single fallback
(silent text-only post).

Risk guards kept from the greenfield rebuild:
  - LLM hallucination: `_zones_grounded()` rejects any plan where fewer than
    3 of the 4 zones share >=1 token with the post. Belt-and-braces — the
    system prompt already forbids invented details.
  - File size: cap enforced before return; > 1MB logs a warning, > 4MB
    returns None so the caller falls back to text-only. LinkedIn's own
    limit is 5MB.
"""
from __future__ import annotations

import json
import re

from linkedin_bot.infographic import render_infographic, valid_layout_ids
from linkedin_bot.llm import LLMClient


# Canvas — matches LinkedIn 4:5 portrait and all HTML templates.
INFOGRAPHIC_W = 1080
INFOGRAPHIC_H = 1350

# File-size guard. LinkedIn rejects uploads over 5MB; we sit well below.
IMG_WARN_BYTES = 1_000_000         # 1MB — log a warning
IMG_HARD_BYTES = 4_000_000         # 4MB — return None so the caller falls back

# Tokens stripped before overlap check (very common English / code words).
_OVERLAP_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "from", "by", "is", "are", "was", "were", "be", "been",
    "being", "as", "it", "this", "that", "these", "those", "i", "you",
    "we", "they", "he", "she", "he", "his", "her", "their", "our", "my",
    "your", "its", "not", "no", "do", "does", "did", "have", "has", "had",
    "will", "would", "could", "should", "may", "can", "just", "only",
    "so", "than", "then", "too", "very", "more", "most", "some", "any",
})


def _overlap_tokens(text: str) -> set[str]:
    """Alphanumeric tokens, lowercased, stopwords removed — used for grounding."""
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in raw if t not in _OVERLAP_STOPWORDS and len(t) > 2}


def _zones_grounded(zones: list[str], post_content: str, min_hits: int = 3) -> bool:
    """
    Hallucination guard for the 4-zone layout. At least `min_hits` of the zones
    must share >=1 token with the post. Reject LLM-fabricated detail.
    """
    post_tokens = _overlap_tokens(post_content)
    if not post_tokens:
        return False
    hits = 0
    for zone in zones:
        if zone and _overlap_tokens(zone) & post_tokens:
            hits += 1
    return hits >= min_hits


class ImageService:
    """
    Owns layout extraction + HTML render dispatch.

    Single-path: AI picks a layout + fills zones → PlaywrightHtmlRenderer →
    PNG. On any failure returns None; the bot then posts text-only.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def classify_post(self, post_content: str) -> dict | None:
        """
        AI picks the best layout template + fills the 4 zone labels.

        Returns {layout_id, zones, accent} on success, None on any failure.
        The HTML template registry decides what `layout_id` values are
        valid; the LLM is told the exact list, so it cannot drift.
        """
        allowed = valid_layout_ids()
        allowed_csv = ", ".join(allowed)
        system = (
            "You pick a layout template and fill it for a designer-grade "
            "developer LinkedIn infographic. Hard rules:\n"
            "1. Output ONLY JSON. No commentary. No markdown fences.\n"
            f"2. layout_id MUST be one of: {allowed_csv}. If unsure, use flow_vertical.\n"
            "3. Each zone is a SHORT CONCEPT LABEL — max 6 words. Words must "
            "be drawn from the post. Examples: 'parent flag propagates', "
            "'silent breaking change', 'document the sampling contract'.\n"
            "4. accent MUST be #RRGGBB hex.\n"
            "5. If the post lacks a given zone, return empty string — never invent."
        )
        user = (
            "Pick a layout and fill the zones:\n"
            "{\n"
            f'  "layout_id": "one of {allowed_csv}",\n'
            '  "zones": {\n'
            '    "hook":   "concept label, max 6 words, words drawn from the post",\n'
            '    "take":   "concept label, max 6 words, words drawn from the post",\n'
            '    "reason": "concept label, max 6 words, words drawn from the post",\n'
            '    "closer": "concept label, max 6 words, words drawn from the post"\n'
            "  },\n"
            '  "accent": "#RRGGBB hex"\n'
            "}\n\n"
            f"POST:\n{post_content}"
        )
        raw = self._llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        if not raw:
            return None
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except Exception as e:
            print(f"classify_post: JSON parse failed: {e} — raw: {cleaned[:200]}")
            return None

        layout_id = str(data.get("layout_id", "")).strip()
        if layout_id not in allowed:
            print(f"classify_post: bad layout_id {layout_id!r}, using flow_vertical")
            layout_id = "flow_vertical"
        zones_raw = data.get("zones") or {}
        zones = {
            "hook":   str(zones_raw.get("hook", "")).strip()[:100],
            "take":   str(zones_raw.get("take", "")).strip()[:100],
            "reason": str(zones_raw.get("reason", "")).strip()[:100],
            "closer": str(zones_raw.get("closer", "")).strip()[:100],
        }
        accent = str(data.get("accent", "")).strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            accent = "#3fb950"  # dev-friendly green default

        # Grounding guard: at least 3 zones must share >=1 token with the post.
        zone_list = [zones["hook"], zones["take"], zones["reason"], zones["closer"]]
        if not _zones_grounded(zone_list, post_content, min_hits=3):
            print(
                "classify_post: rejected — fewer than 3 zones grounded in post "
                f"(zones={zone_list})"
            )
            return None
        return {"layout_id": layout_id, "zones": zones, "accent": accent}

    def generate(
        self, post_content: str, source_title: str | None = None
    ) -> bytes | None:
        """
        Render the post as an infographic PNG. Returns None on any failure.

        A None return is the documented signal to the caller (the bot) to
        post text-only — that's how the existing publishing flow behaves.
        """
        try:
            plan = self.classify_post(post_content)
        except Exception as e:
            print(f"classify_post raised: {e}")
            plan = None
        if not plan:
            return None

        try:
            png = render_infographic(
                plan["layout_id"],
                plan["zones"],
                plan["accent"],
                source=source_title or "",
            )
        except Exception as e:
            print(f"HTML render raised: {e}")
            return None

        if not png:
            print("HTML render returned no bytes — falling back to text-only post.")
            return None

        if len(png) >= IMG_HARD_BYTES:
            print(
                f"Infographic too large ({len(png) // 1024}KB >= "
                f"{IMG_HARD_BYTES // 1024}KB) — falling back to text-only post."
            )
            return None
        if len(png) >= IMG_WARN_BYTES:
            print(f"WARNING: infographic large — {len(png) // 1024}KB")
        print(
            f"Infographic rendered ({plan['layout_id']}, HTML) — "
            f"{len(png) // 1024}KB"
        )
        return png
