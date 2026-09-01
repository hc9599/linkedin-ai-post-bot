"""
Optional picture for the post.

Pipeline: assess post type → LLM plan with layman verbiage + code comments
→ validate grounding → retry until related → Playwright PNG.

Image is always attempted; only Playwright/render hard failures skip it.
"""
from __future__ import annotations

import json
import re

from linkedin_bot.infographic import render_infographic, valid_layout_ids
from linkedin_bot.llm import LLMClient

IMG_WARN_BYTES = 1_000_000
IMG_HARD_BYTES = 4_000_000
MAX_PLAN_ATTEMPTS = 4

_OVERLAP_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "from", "by", "is", "are", "was", "were", "be", "been",
    "being", "as", "it", "this", "that", "these", "those", "i", "you",
    "we", "they", "he", "she", "his", "her", "their", "our", "my",
    "your", "its", "not", "no", "do", "does", "did", "have", "has", "had",
    "will", "would", "could", "should", "may", "can", "just", "only",
    "so", "than", "then", "too", "very", "more", "most", "some", "any",
})

_LAYOUT_FALLBACK_ORDER: dict[str, list[str]] = {
    "code_compare": ["code_compare", "code_tip", "process_flow"],
    "code_tip": ["code_tip", "code_compare", "process_flow"],
    "process_flow": ["process_flow", "code_tip", "code_compare"],
}


def _overlap_tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in raw if t not in _OVERLAP_STOPWORDS and len(t) > 2}


def _text_grounded(text: str, post_content: str) -> bool:
    zone_tokens = _overlap_tokens(text)
    post_tokens = _overlap_tokens(post_content)
    if not zone_tokens or not post_tokens:
        return False
    return bool(zone_tokens & post_tokens)


def _post_keyword_hints(post_content: str, limit: int = 10) -> str:
    """Sample topic tokens from the post for retry prompts."""
    tokens = sorted(_overlap_tokens(post_content), key=len, reverse=True)
    return ", ".join(tokens[:limit]) or "(use exact words from the post)"


def _plan_grounded(plan: dict, post_content: str) -> tuple[bool, str]:
    """Check infographic content overlaps the post topic."""
    title = str(plan.get("title") or "")
    if not _text_grounded(title, post_content):
        return False, "title must reuse words from the post headline/topic"

    layout_id = plan.get("layout_id")

    if layout_id == "code_compare":
        blobs = [
            str(plan.get("before_code") or ""),
            str(plan.get("after_code") or ""),
            str(plan.get("before_verbiage") or ""),
            str(plan.get("after_verbiage") or ""),
        ]
        hits = sum(1 for b in blobs if b and _text_grounded(b, post_content))
        if hits < 2:
            return False, (
                "code_compare needs at least 2 of: before_code, after_code, "
                "before_verbiage, after_verbiage grounded in the post"
            )
        return True, ""

    if layout_id == "code_tip":
        caption = str(plan.get("caption") or "")
        subtitle = str(plan.get("subtitle") or "")
        code = str(plan.get("code") or "")
        if not _text_grounded(caption, post_content):
            return False, "caption must reuse words from the post"
        if not (_text_grounded(subtitle, post_content) or _text_grounded(code, post_content)):
            return False, "code or subtitle must reuse topic words from the post"
        return True, ""

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
        if hits < 2:
            return False, "process_flow needs at least 2 steps grounded in the post"
        return True, ""

    return False, f"unknown layout_id {layout_id!r}"


def _code_has_layman_comment(code: str) -> bool:
    """Require at least one // comment explaining the snippet in plain English."""
    return bool(re.search(r"//(?!\s*$).{4,}", code or ""))


def _plan_quality(plan: dict) -> tuple[bool, str]:
    """Structural quality — layman verbiage and comments, not gibberish shape."""
    layout_id = plan.get("layout_id")

    if layout_id == "code_compare":
        before = str(plan.get("before_code") or "")
        after = str(plan.get("after_code") or "")
        if not before or not after:
            return False, "both before_code and after_code are required"
        if not _code_has_layman_comment(before):
            return False, "before_code needs a // layman comment"
        if not _code_has_layman_comment(after):
            return False, "after_code needs a // layman comment"
        if len(str(plan.get("before_verbiage") or "")) < 12:
            return False, "before_verbiage must explain the old way in plain English"
        if len(str(plan.get("after_verbiage") or "")) < 12:
            return False, "after_verbiage must explain the new way in plain English"
        return True, ""

    if layout_id == "code_tip":
        code = str(plan.get("code") or "")
        if not code:
            return False, "code is required"
        if not _code_has_layman_comment(code):
            return False, "code needs at least one // layman comment"
        if len(str(plan.get("caption") or "")) < 15:
            return False, "caption must explain why this matters (plain English)"
        return True, ""

    if layout_id == "process_flow":
        steps = plan.get("steps") or []
        if len(steps) < 3:
            return False, "process_flow needs 3–4 steps"
        for i, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                return False, f"step {i} is malformed"
            if len(str(step.get("text") or "")) < 8:
                return False, f"step {i} text too short"
            if len(str(step.get("detail") or "")) < 15:
                return False, f"step {i} needs detail (layman verbiage after the step)"
        return True, ""

    return False, f"unknown layout_id {layout_id!r}"


def _validate_plan(plan: dict, post_content: str) -> tuple[bool, str]:
    ok, reason = _plan_quality(plan)
    if not ok:
        return False, reason
    return _plan_grounded(plan, post_content)


def _parse_json(raw: str) -> dict | None:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        print(f"plan JSON parse failed: {e} — raw: {cleaned[:200]}")
        return None
    return data if isinstance(data, dict) else None


def _normalize_plan(data: dict, layout_id: str) -> dict | None:
    allowed = set(valid_layout_ids())
    if layout_id not in allowed:
        layout_id = "process_flow"

    accent = str(data.get("accent") or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = "#FFC107"

    plan: dict = {
        "layout_id": layout_id,
        "title": str(data.get("title") or "").strip()[:80],
        "accent": accent,
        "subtitle": str(data.get("subtitle") or "").strip()[:120],
    }

    if layout_id == "code_compare":
        plan["before_label"] = str(data.get("before_label") or "Before").strip()[:40]
        plan["after_label"] = str(data.get("after_label") or "After").strip()[:40]
        plan["before_code"] = str(data.get("before_code") or "").strip()[:900]
        plan["after_code"] = str(data.get("after_code") or "").strip()[:900]
        plan["before_verbiage"] = str(data.get("before_verbiage") or "").strip()[:160]
        plan["after_verbiage"] = str(data.get("after_verbiage") or "").strip()[:160]
        if not plan["before_code"] or not plan["after_code"]:
            return None

    elif layout_id == "code_tip":
        plan["code"] = str(data.get("code") or "").strip()[:900]
        plan["caption"] = str(data.get("caption") or "").strip()[:160]
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
                "detail": str(step.get("detail") or "").strip()[:140],
            })
        if len(steps) < 3:
            return None
        plan["steps"] = steps

    if not plan.get("title"):
        return None
    return plan


def _deterministic_fallback_plan(post_content: str) -> dict:
    """
    Last-resort process_flow built only from post sentences — always on-topic
    because it copies the post itself.
    """
    chunks: list[str] = []
    for block in post_content.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#") or block.lower().startswith("source:"):
            continue
        chunks.append(block)

    if not chunks:
        chunks = [post_content.strip()[:200] or "C# / .NET developer take"]

    title = chunks[0]
    if len(title) > 70:
        title = title[:67].rsplit(" ", 1)[0] + "..."

    step_sources = chunks[1:] if len(chunks) > 1 else [chunks[0]]
    steps = []
    for i, src in enumerate(step_sources[:4], start=1):
        text = src if len(src) <= 90 else src[:87] + "..."
        detail_src = src if len(src) > 90 else src
        detail = detail_src[:140] if len(detail_src) <= 140 else detail_src[:137] + "..."
        steps.append({
            "label": f"STEP {i}",
            "text": text,
            "detail": detail,
        })
        if len(steps) >= 3:
            break

    while len(steps) < 3:
        steps.append({
            "label": f"STEP {len(steps) + 1}",
            "text": chunks[0][:90],
            "detail": "Key point pulled directly from today's post.",
        })

    return {
        "layout_id": "process_flow",
        "title": title[:80],
        "subtitle": "How the pieces connect",
        "accent": "#58a6ff",
        "steps": steps[:4],
    }


class ImageService:
    """Plans and renders pictorial infographics from the final post."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def _assess_post_type(self, post_content: str) -> str:
        """
        Read the post and pick the best infographic format before generating content.
        """
        allowed = valid_layout_ids()
        system = (
            "You classify a C#/.NET LinkedIn post for infographic layout. "
            'Output ONLY JSON: {"layout_id": "...", "reason": "one sentence"}.\n\n'
            f"layout_id MUST be one of: {', '.join(allowed)}.\n\n"
            "- code_compare: post contrasts old vs new syntax, API, or pattern.\n"
            "- code_tip: post focuses on one snippet, API call, or technique.\n"
            "- process_flow: post explains steps, architecture, rollout, or a chain "
            "of ideas without a clear before/after code pair."
        )
        raw = self._llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Classify this post:\n\n{post_content}"},
            ],
            temperature=0.0,
            max_tokens=120,
        )
        if raw:
            data = _parse_json(raw)
            if data:
                choice = str(data.get("layout_id") or "").strip()
                reason = str(data.get("reason") or "").strip()
                if choice in allowed:
                    print(f"Infographic assessment: {choice} — {reason}")
                    return choice
        print("Infographic assessment: defaulting to process_flow")
        return "process_flow"

    def _request_plan(
        self,
        post_content: str,
        layout_id: str,
        *,
        feedback: str | None = None,
        strict: bool = False,
    ) -> dict | None:
        hints = _post_keyword_hints(post_content)
        system = (
            "You create LinkedIn infographic JSON from a C#/.NET developer post. "
            "Output ONLY JSON — no markdown fences.\n\n"
            f"Use layout_id: {layout_id}\n\n"
            "Global rules:\n"
            "1. title — headline using words from the post (max 8 words).\n"
            "2. Every code block MUST include // comments in plain English (layman terms).\n"
            "3. Never invent facts not implied by the post.\n"
            "4. accent = #RRGGBB (gold #FFC107 for code layouts).\n\n"
            "code_compare fields:\n"
            "  before_label, after_label (short, can be Before/After)\n"
            "  before_code, after_code — minimal C# with // layman comments, \\n for newlines\n"
            "  before_verbiage — plain English sentence under the BEFORE panel\n"
            "  after_verbiage — plain English sentence under the AFTER panel\n\n"
            "code_tip fields:\n"
            "  code — C# with // layman comments\n"
            "  caption — plain English why this matters\n"
            "  subtitle — optional one-line context\n\n"
            "process_flow fields:\n"
            "  steps — 3–4 objects: label, text (headline), detail (layman verbiage AFTER the step)\n"
            "  subtitle — optional flow context\n"
        )
        if strict:
            system += (
                "\nSTRICT MODE: Copy phrases verbatim from the post. "
                "Do not paraphrase with new vocabulary."
            )

        user = f"Topic words from post: {hints}\n\n"
        if feedback:
            user += f"Previous attempt failed: {feedback}\nFix and try again.\n\n"
        user += f"POST:\n{post_content}\n\nReturn the JSON plan."

        raw = self._llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.15 if strict else 0.25,
            max_tokens=1000,
        )
        if not raw:
            return None
        data = _parse_json(raw)
        if not data:
            return None
        data["layout_id"] = layout_id
        return _normalize_plan(data, layout_id)

    def _plan_with_retries(self, post_content: str) -> dict:
        """
        Assess post → generate plan → validate → retry until related.
        Falls back to deterministic post copy if LLM never passes validation.
        """
        primary = self._assess_post_type(post_content)
        layouts_to_try = _LAYOUT_FALLBACK_ORDER.get(primary, valid_layout_ids())

        feedback: str | None = None
        for layout_id in layouts_to_try:
            for attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
                print(f"Infographic plan attempt {attempt}/{MAX_PLAN_ATTEMPTS} ({layout_id})")
                plan = self._request_plan(
                    post_content, layout_id, feedback=feedback, strict=(attempt >= 3)
                )
                if not plan:
                    feedback = "invalid or incomplete JSON — include all required fields"
                    continue
                ok, reason = _validate_plan(plan, post_content)
                if ok:
                    print(f"Infographic plan accepted ({layout_id})")
                    return plan
                print(f"Infographic plan rejected: {reason}")
                feedback = reason

        print("Infographic plan: using deterministic fallback from post text")
        return _deterministic_fallback_plan(post_content)

    def generate(
        self, post_content: str, source_title: str | None = None
    ) -> bytes | None:
        try:
            plan = self._plan_with_retries(post_content)
        except Exception as e:
            print(f"Infographic planning raised: {e}")
            plan = _deterministic_fallback_plan(post_content)

        try:
            png = render_infographic(plan, source=source_title or "")
        except Exception as e:
            print(f"HTML render raised: {e}")
            return None

        if not png:
            print("HTML render returned no bytes.")
            return None

        if len(png) >= IMG_HARD_BYTES:
            print(f"Infographic too large ({len(png) // 1024}KB).")
            return None
        if len(png) >= IMG_WARN_BYTES:
            print(f"WARNING: infographic large — {len(png) // 1024}KB")
        print(
            f"Infographic rendered ({plan['layout_id']}, HTML) — "
            f"{len(png) // 1024}KB"
        )
        return png
