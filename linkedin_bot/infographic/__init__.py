"""
Hand-authored HTML infographic pipeline.

Public API:
    render_infographic(layout_id, zones, accent, source) -> bytes | None

The LLM only picks `layout_id` and fills the four content zones; the look
stays deterministic because every layout is a fixed Jinja2 template.
"""
from __future__ import annotations

from .renderer import PlaywrightHtmlRenderer, get_renderer

_VALID_LAYOUT_IDS = ("flow_vertical", "split_contrast", "cascade", "stack_compare")
_DEFAULT_LAYOUT_ID = "flow_vertical"


def valid_layout_ids() -> list[str]:
    """Layout IDs the LLM is allowed to pick."""
    return list(_VALID_LAYOUT_IDS)


def render_infographic(
    layout_id: str,
    zones: dict,
    accent: str,
    source: str = "",
) -> bytes | None:
    """
    Render a 1080x1350 PNG infographic from structured content.

    Args:
        layout_id: one of valid_layout_ids(); unknown IDs fall back to flow_vertical.
        zones: dict with keys "hook", "take", "reason", "closer".
        accent: "#RRGGBB" hex color used as the layout's accent.
        source: article title for the footer (may be empty).

    Returns PNG bytes or None if anything in the pipeline failed.
    """
    chosen = layout_id if layout_id in _VALID_LAYOUT_IDS else _DEFAULT_LAYOUT_ID
    plan = {
        "layout_id": chosen,
        "zones": zones,
        "accent": accent,
    }
    return get_renderer().render(plan, source_title=source)


__all__ = [
    "render_infographic",
    "valid_layout_ids",
    "PlaywrightHtmlRenderer",
    "get_renderer",
]