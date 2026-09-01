"""
Hand-authored HTML infographic pipeline.

Public API:
    render_infographic(plan, source) -> bytes | None

The LLM picks layout + fills structured content (code blocks, flow steps,
titles). Templates stay deterministic — design is not improvised per post.
"""
from __future__ import annotations

from .renderer import PlaywrightHtmlRenderer, get_renderer

_VALID_LAYOUT_IDS = ("code_compare", "process_flow", "code_tip")
_DEFAULT_LAYOUT_ID = "process_flow"


def valid_layout_ids() -> list[str]:
    """Layout IDs the LLM is allowed to pick."""
    return list(_VALID_LAYOUT_IDS)


def render_infographic(plan: dict, source: str = "") -> bytes | None:
    """
    Render a 1080x1350 PNG infographic from a structured plan dict.

    plan keys vary by layout_id — see ImageService.classify_post().
    Returns PNG bytes or None if anything in the pipeline failed.
    """
    layout_id = str(plan.get("layout_id") or _DEFAULT_LAYOUT_ID).strip()
    if layout_id not in _VALID_LAYOUT_IDS:
        layout_id = _DEFAULT_LAYOUT_ID
    plan = {**plan, "layout_id": layout_id}
    return get_renderer().render(plan, source_title=source)


__all__ = [
    "render_infographic",
    "valid_layout_ids",
    "PlaywrightHtmlRenderer",
    "get_renderer",
]
