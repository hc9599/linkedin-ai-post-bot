"""
Optional picture for the post.

Render path: AI plans a pictorial infographic (code compare, code tip, or
process flow) + HTML/CSS template + Playwright → 1080x1350 PNG.
"""
from __future__ import annotations

import json
import re

from linkedin_bot.infographic import render_infographic, valid_layout_ids
from linkedin_bot.llm import LLMClient

IMG_WARN_BYTES = 1_000_000
IMG_HARD_BYTES = 4_000_000

_OVERLAP_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "from", "by", "is", "are", "was", "were", "be", "been",
    "being", "as", "it", "this", "that", "these", "those", "i", "you",
    "we", "they", "he", "she", "his", "her", "their", "our", "my",
    "your", "its", "not", "no", "do", "does", "did", "have", "has", "had",
    "will", "would", "could", "should", "may", "can", "just", "only",
    "so", "than", "then", "too", "very", "more", "most", "some", "any",
    "net", "csharp", "dotnet", "code", "using", "new", "class",
})


def _overlap_tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in raw if t not in _OVERLAP_STOPWORDS and len(t) > 2}


def _text_grounded(text: str, post_content: str) -> bool:
    zone_tokens = _overlap_tokens(text)
    post_tokens = _overlap_tokens(post_content)
    if not zone_tokens or not post_tokens:
        return False
    return bool(zone_tokens & post_tokens)


def _plan_grounded(plan: dict, post_content: str) -> bool:
    """Reject plans whose headline or body drift from the post topic."""
    title = str(plan.get("title") or "")
    if not _text_grounded(title, post_content):
        return False

    layout_id = plan.get("layout_id")
    if layout_id == "code_compare":
        before = str(plan.get("before_label") or "")
        after = str(plan.get("after_label") or "")
        return _text_grounded(before, post_content) or _text_grounded(after, post_content)

    if layout_id == "code_tip":
        caption = str(plan.get("caption") or "")
        subtitle = str(plan.get("subtitle") or "")
        return _text_grounded(caption, post_content) or _text_grounded(subtitle, post_content)

    if layout_id == "process_flow":
        steps = plan.get("steps") or []
        hits = 0
        for step in steps:
            if not isinstance(step, dict):
                continue
            blob = " ".join(
                str(step.get(k) or "") for k in ("label", "text", "detail")
            )
            if _text_grounded(blob, post_content):
                hits += 1
        return hits >= 2

    return False


def _parse_json(raw: str) -> dict | None:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        print(f"classify_post: JSON parse failed: {e} — raw: {cleaned[:200]}")
        return None
    return data if isinstance(data, dict) else None


def _normalize_plan(data: dict, allowed: set[str]) -> dict | None:
    layout_id = str(data.get("layout_id") or "process_flow").strip()
    if layout_id not in allowed:
        print(f"classify_post: bad layout_id {layout_id!r}, using process_flow")
        layout_id = "process_flow"

    accent = str(data.get("accent") or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = "#FFC107"

    plan: dict = {
        "layout_id": layout_id,
        "title": str(data.get("title") or "").strip()[:80],
        "accent": accent,
        "subtitle": str(data.get("subtitle") or "").strip()[:100],
    }

    if layout_id == "code_compare":
        plan["before_label"] = str(data.get("before_label") or "Traditional Approach").strip()[:60]
        plan["after_label"] = str(data.get("after_label") or "Modern Approach").strip()[:60]
        plan["before_code"] = str(data.get("before_code") or "").strip()[:900]
        plan["after_code"] = str(data.get("after_code") or "").strip()[:900]
        if not plan["before_code"] or not plan["after_code"]:
            return None

    elif layout_id == "code_tip":
        plan["code"] = str(data.get("code") or "").strip()[:900]
        plan["caption"] = str(data.get("caption") or "").strip()[:140]
        if not plan["code"]:
            return None

    elif layout_id == "process_flow":
        steps_raw = data.get("steps") or []
        steps = []
        for step in steps_raw[:4]:
            if not isinstance(step, dict):
                continue
            text = str(step.get("text") or "").strip()[:100]
            if not text:
                continue
            steps.append({
                "label": str(step.get("label") or "").strip()[:30],
                "text": text,
                "detail": str(step.get("detail") or "").strip()[:80],
            })
        if len(steps) < 3:
            return None
        plan["steps"] = steps

    if not plan.get("title"):
        return None
    return plan


class ImageService:
    """Plans and renders pictorial infographics from the final post."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def classify_post(self, post_content: str) -> dict | None:
        allowed = valid_layout_ids()
        allowed_csv = ", ".join(allowed)
        system = (
            "You create LinkedIn infographic content from a C#/.NET developer post. "
            "Output ONLY JSON — no markdown fences, no commentary.\n\n"
            f"layout_id MUST be one of: {allowed_csv}\n\n"
            "Pick the best pictorial layout:\n"
            "- code_compare: post contrasts an OLD pattern vs a NEW/BETTER one "
            "(syntax change, API migration, refactor). Provide two short C# blocks "
            "(max 10 lines each) that illustrate the contrast. Use \\n for newlines.\n"
            "- code_tip: post highlights one API, snippet, or technique. Provide "
            "one C# block (max 14 lines) plus a caption explaining why it matters.\n"
            "- process_flow: post explains architecture, debugging steps, rollout, "
            "or a concept chain without a before/after code pair. Provide 3–4 numbered "
            "steps with label + one-line text (+ optional detail).\n\n"
            "Rules:\n"
            "1. title = short headline from the post topic (max 8 words).\n"
            "2. Code must be minimal, compilable-looking C# that matches the post topic.\n"
            "3. Steps/text must use words and ideas from the post — do not invent facts.\n"
            "4. accent = #RRGGBB hex (prefer gold #FFC107 for code layouts).\n"
            "5. before_label / after_label should read like 'Traditional Approach' / "
            "'Modern Approach' when using code_compare."
        )
        user = (
            "Return JSON for ONE layout:\n"
            "{\n"
            f'  "layout_id": "{allowed[0]}" | "{allowed[1]}" | "{allowed[2]}",\n'
            '  "title": "headline from post topic",\n'
            '  "subtitle": "optional one-line context",\n'
            '  "accent": "#FFC107",\n'
            '  "before_label": "for code_compare only",\n'
            '  "after_label": "for code_compare only",\n'
            '  "before_code": "for code_compare — C# with \\\\n newlines",\n'
            '  "after_code": "for code_compare — C# with \\\\n newlines",\n'
            '  "code": "for code_tip — C# with \\\\n newlines",\n'
            '  "caption": "for code_tip — why this matters",\n'
            '  "steps": [\n'
            '    {"label": "STEP", "text": "one line from post", "detail": "optional"}\n'
            "  ]\n"
            "}\n\n"
            f"POST:\n{post_content}"
        )
        raw = self._llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.25,
            max_tokens=900,
        )
        if not raw:
            return None

        data = _parse_json(raw)
        if not data:
            return None

        plan = _normalize_plan(data, set(allowed))
        if not plan:
            print("classify_post: plan missing required fields")
            return None

        if not _plan_grounded(plan, post_content):
            print(f"classify_post: rejected — plan not grounded in post ({plan.get('layout_id')})")
            return None

        return plan

    def generate(
        self, post_content: str, source_title: str | None = None
    ) -> bytes | None:
        try:
            plan = self.classify_post(post_content)
        except Exception as e:
            print(f"classify_post raised: {e}")
            plan = None
        if not plan:
            return None

        try:
            png = render_infographic(plan, source=source_title or "")
        except Exception as e:
            print(f"HTML render raised: {e}")
            return None

        if not png:
            print("HTML render returned no bytes — falling back to text-only post.")
            return None

        if len(png) >= IMG_HARD_BYTES:
            print(
                f"Infographic too large ({len(png) // 1024}KB) — "
                "falling back to text-only post."
            )
            return None
        if len(png) >= IMG_WARN_BYTES:
            print(f"WARNING: infographic large — {len(png) // 1024}KB")
        print(
            f"Infographic rendered ({plan['layout_id']}, HTML) — "
            f"{len(png) // 1024}KB"
        )
        return png
