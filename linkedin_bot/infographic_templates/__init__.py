"""
Curated designer-grade SVG templates for LinkedIn infographics.

Each template is hand-authored — fixed composition, typography, accents.
LLM only picks which template fits a post + fills in the content. The look
is consistent because the look is hand-authored, not improvised.

Template contract:
    def render(zones: dict, accent: str, source: str) -> str:
        zones: {"hook": str, "take": str, "reason": str, "closer": str}
        accent: "#RRGGBB"
        source: article title (may be empty)
        returns: complete <svg>...</svg> string at 1080x1350
"""
from __future__ import annotations

import html as _html
import re

# Canvas
WIDTH = 1080
HEIGHT = 1350

# Palette
BG = "#0d1117"
PANEL_BG = "#161b22"
PANEL_BORDER = "#30363d"
FG = "#f0f6fc"
MUTED = "#8b949e"
DOT = "#1c2128"

# Type chain — Inter preferred, falls back through Helvetica Neue, Arial.
FONT_STACK = 'Inter, "Helvetica Neue", Arial, sans-serif'


def _font(family: str = FONT_STACK) -> str:
    """Safe font-family value for SVG attributes (escapes inner double quotes)."""
    return family.replace('"', "&quot;")

# Spacing scale (px)
SPACE = {"xs": 8, "sm": 16, "md": 24, "lg": 32, "xl": 48, "xxl": 64}


def _escape(text: str) -> str:
    """Escape text for SVG. Preserve straight quotes (LinkedIn-safe)."""
    if text is None:
        return ""
    return _html.escape(str(text), quote=False)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Strict #RRGGBB → (r,g,b). Caller must pass valid hex."""
    v = (value or "").strip().lstrip("#")
    n = int(v, 16)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


def _defs(accent: str) -> str:
    """Shared <defs>: drop shadow, dot grid pattern."""
    r, g, b = _hex_to_rgb(accent)
    return f"""<defs>
  <pattern id="dotgrid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
    <circle cx="1" cy="1" r="1" fill="{DOT}"/>
  </pattern>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="6"/>
    <feOffset dx="0" dy="2"/>
    <feComponentTransfer><feFuncA type="linear" slope="0.55"/></feComponentTransfer>
    <feMerge>
      <feMergeNode/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
  <linearGradient id="accFade" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{accent}" stop-opacity="1"/>
    <stop offset="100%" stop-color="{accent}" stop-opacity="0.4"/>
  </linearGradient>
</defs>"""


def _background() -> str:
    return f"""<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#dotgrid)"/>"""


def _brand_mark(accent: str) -> str:
    """Top-left brand chip + eyebrow text."""
    fs = _font()
    return (
        f'<rect x="60" y="60" width="6" height="36" fill="{accent}"/>'
        f'<text x="80" y="78" fill="{MUTED}" font-family="{fs}" '
        f'font-size="14" font-weight="600" letter-spacing="2">C# / .NET</text>'
        f'<text x="80" y="98" fill="{MUTED}" font-family="{fs}" '
        f'font-size="14" font-weight="400" opacity="0.7">logic flow</text>'
    )


def _footer(source: str, accent: str) -> str:
    """Bottom 90px: source article + post handle."""
    short = source if len(source) <= 56 else source[:53] + "..."
    src_y = HEIGHT - 70
    handle_y = HEIGHT - 40
    fs = _font()
    src_block = ""
    if short:
        src_block = (
            f'<rect x="60" y="{src_y - 14}" width="3" height="20" fill="{accent}"/>'
            f'<text x="76" y="{src_y}" fill="{MUTED}" font-family="{fs}" '
            f'font-size="16">source: {_escape(short)}</text>'
        )
    handle = (
        f'<text x="60" y="{handle_y}" fill="{MUTED}" font-family="{fs}" '
        f'font-size="16" opacity="0.7">linkedin post  ·  human take</text>'
    )
    return src_block + handle


def _svg_open() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}">'
    )


def _wrap_lines(text: str, max_chars: int) -> list[str]:
    """Word-wrap by char count. No pixel measurement (SVG handles its own flow)."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars:
            if current:
                lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


# Registry — one entry per template. Lazy-imported to keep module-level
# imports cheap and to allow templates to fail independently.
def _load_templates() -> dict:
    from linkedin_bot.infographic_templates import (
        flow_vertical,
        split_contrast,
        cascade,
        stack_compare,
    )
    return {
        "flow_vertical":   flow_vertical.render,
        "split_contrast":  split_contrast.render,
        "cascade":         cascade.render,
        "stack_compare":   stack_compare.render,
    }


_REGISTRY = _load_templates()
_VALID_IDS = set(_REGISTRY.keys())
_DEFAULT_ID = "flow_vertical"


def render_template(layout_id: str, zones: dict, accent: str, source: str) -> str:
    """
    Look up the template by ID and render it with the supplied content.

    Unknown IDs fall back to flow_vertical (safe default).
    """
    chosen = layout_id if layout_id in _REGISTRY else _DEFAULT_ID
    return _REGISTRY[chosen](zones, accent, source)


def valid_layout_ids() -> list[str]:
    """Used by the LLM prompt — list the IDs the model may pick."""
    return sorted(_VALID_IDS)