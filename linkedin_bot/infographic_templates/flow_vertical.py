"""
flow_vertical — vertical argument chain. 4 panels stacked, accent left bar,
triangle arrows between. Designer polish: drop shadow, dot grid bg, brand mark.

Default safe layout. Works for any post.
"""
from linkedin_bot.infographic_templates import (
    WIDTH, HEIGHT, PANEL_BG, PANEL_BORDER, FG, MUTED, FONT_STACK,
    SPACE, _svg_open, _defs, _background, _brand_mark, _footer,
    _wrap_lines, _escape, _font,
)


def _panel(accent: str, label: str, text: str, body_size: int,
           panel_x: int, panel_y: int, panel_w: int, panel_h: int,
           is_hero: bool = False) -> str:
    """One rounded panel: accent left bar, label, body text."""
    # Panel body
    panel = (
        f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" '
        f'rx="14" ry="14" fill="{PANEL_BG}" stroke="{PANEL_BORDER}" stroke-width="1.5" '
        f'filter="url(#shadow)"/>'
    )
    # Accent left bar
    bar = (
        f'<rect x="{panel_x}" y="{panel_y + 8}" width="6" height="{panel_h - 16}" '
        f'rx="3" ry="3" fill="{accent}"/>'
    )
    # Label (eyebrow)
    label_text = (
        f'<text x="{panel_x + 32}" y="{panel_y + 36}" fill="{accent}" '
        f'font-family="{_font()}" font-size="16" font-weight="700" '
        f'letter-spacing="2">{_escape(label)}</text>'
    )
    # Body — wrap into 2-3 lines, anchored at the panel's left padding.
    lines = _wrap_lines(text, max_chars=28)[:3]
    body_y = panel_y + 88 if not is_hero else panel_y + 110
    body_x = panel_x + 32
    body = ""
    line_h = body_size + 12
    for i, line in enumerate(lines):
        y = body_y + i * line_h
        body += (
            f'<text x="{body_x}" y="{y}" fill="{FG}" font-family="{_font()}" '
            f'font-size="{body_size}" font-weight="600">{_escape(line)}</text>'
        )
    return panel + bar + label_text + body


def _arrow_down(accent: str, cx: int, top_y: int) -> str:
    """Stem + triangle head pointing down. 36px tall total."""
    stem = (
        f'<line x1="{cx}" y1="{top_y}" x2="{cx}" y2="{top_y + 18}" '
        f'stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
    )
    head = (
        f'<polygon points="{cx - 9},{top_y + 18} {cx + 9},{top_y + 18} '
        f'{cx},{top_y + 32}" fill="{accent}"/>'
    )
    return stem + head


def render(zones: dict, accent: str, source: str) -> str:
    parts = [_svg_open(), _defs(accent), _background(), _brand_mark(accent)]

    panel_x = 60
    panel_w = WIDTH - 120
    panel_h = 180
    panel_top = 170
    gap_with_arrow = 70
    labels = ["SPARK", "TAKE", "WHY", "SO WHAT"]
    keys = ["hook", "take", "reason", "closer"]

    cx = WIDTH // 2
    for i, (label, key) in enumerate(zip(labels, keys)):
        y = panel_top + i * (panel_h + gap_with_arrow)
        body = (zones.get(key) or "").strip() or "(missing)"
        is_hero = (label == "TAKE")  # The central claim gets slightly bigger type
        body_size = 38 if is_hero else 32
        # Slightly taller hero panel.
        ph = panel_h + 24 if is_hero else panel_h
        parts.append(_panel(
            accent, label, body, body_size,
            panel_x, y, panel_w, ph, is_hero=is_hero,
        ))
        if i < len(labels) - 1:
            arrow_top = y + ph + 12
            parts.append(_arrow_down(accent, cx, arrow_top))

    parts.append(_footer(source, accent))
    parts.append("</svg>")
    return "".join(parts)
