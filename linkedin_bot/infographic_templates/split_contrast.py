"""
split_contrast — Before/After 2x2 grid with diagonal accent stripe.
Top: PROBLEM (left) vs OUTCOME (right). Bottom: WHY (left) vs HOW (right).
Best when the post pivots from a current way to a new way.
"""
from linkedin_bot.infographic_templates import (
    WIDTH, HEIGHT, PANEL_BG, PANEL_BORDER, FG, MUTED, FONT_STACK,
    _svg_open, _defs, _background, _brand_mark, _footer,
    _wrap_lines, _escape, _font,
)


def _cell(label: str, body: str, x: int, y: int, w: int, h: int,
          accent: str, align: str = "left") -> str:
    label_anchor = "start" if align == "left" else "end"
    text_anchor = "start" if align == "left" else "end"
    text_x = x + 28 if align == "left" else x + w - 28
    label_x = x + 28 if align == "left" else x + w - 28

    panel = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" ry="14" '
        f'fill="{PANEL_BG}" stroke="{PANEL_BORDER}" stroke-width="1.5" '
        f'filter="url(#shadow)"/>'
    )
    eyebrow = (
        f'<text x="{label_x}" y="{y + 36}" text-anchor="{label_anchor}" '
        f'fill="{accent}" font-family="{_font()}" font-size="16" font-weight="700" '
        f'letter-spacing="2">{_escape(label)}</text>'
    )
    lines = _wrap_lines(body, max_chars=20)[:3]
    body_y = y + 88
    line_h = 38
    body_markup = ""
    for i, line in enumerate(lines):
        body_markup += (
            f'<text x="{text_x}" y="{body_y + i * line_h}" text-anchor="{text_anchor}" '
            f'fill="{FG}" font-family="{_font()}" font-size="32" font-weight="600">'
            f'{_escape(line)}</text>'
        )
    return panel + eyebrow + body_markup


def _diagonal_stripe(accent: str) -> str:
    """Thin accent diagonal stripe between top and bottom rows. Decorative."""
    return (
        f'<line x1="80" y1="755" x2="{WIDTH - 80}" y2="635" '
        f'stroke="{accent}" stroke-width="2" stroke-dasharray="4 6" opacity="0.55"/>'
    )


def _corner_mark(x: int, y: int, accent: str, flip: bool = False) -> str:
    """Small L-shaped corner accent inside a cell."""
    d = "M" if not flip else "L"
    return (
        f'<path d="M{x} {y + 20} {d}{x + 20} {y}" '
        f'stroke="{accent}" stroke-width="2" fill="none" opacity="0.6"/>'
    )


def render(zones: dict, accent: str, source: str) -> str:
    parts = [_svg_open(), _defs(accent), _background(), _brand_mark(accent)]

    # Title strip
    title = zones.get("title", "BEFORE → AFTER")
    parts.append(
        f'<text x="{WIDTH // 2}" y="180" text-anchor="middle" fill="{FG}" '
        f'font-family="{_font()}" font-size="42" font-weight="700" '
        f'letter-spacing="3">{_escape(title)}</text>'
    )

    cell_w = (WIDTH - 180) // 2
    cell_h = 250
    gap = 20
    top_y = 230
    bottom_y = top_y + cell_h + gap + 40

    # Top row: PROBLEM (left) | OUTCOME (right)
    parts.append(_cell("PROBLEM", zones.get("hook", ""),
                       60, top_y, cell_w, cell_h, accent, align="left"))
    parts.append(_cell("OUTCOME", zones.get("take", ""),
                       60 + cell_w + gap, top_y, cell_w, cell_h, accent, align="right"))

    # Diagonal accent
    parts.append(_diagonal_stripe(accent))

    # Bottom row: WHY (left) | HOW (right)
    parts.append(_cell("WHY", zones.get("reason", ""),
                       60, bottom_y, cell_w, cell_h, accent, align="left"))
    parts.append(_cell("SO WHAT", zones.get("closer", ""),
                       60 + cell_w + gap, bottom_y, cell_w, cell_h, accent, align="right"))

    # Corner accents — pushed to outer-top corners, clear of text labels.
    parts.append(_corner_mark(60 + 12, top_y + 12, accent))
    parts.append(_corner_mark(60 + cell_w + gap + cell_w - 12, top_y + 12, accent, flip=True))
    parts.append(_corner_mark(60 + 12, bottom_y + 12, accent))
    parts.append(_corner_mark(60 + cell_w + gap + cell_w - 12, bottom_y + 12, accent, flip=True))

    parts.append(_footer(source, accent))
    parts.append("</svg>")
    return "".join(parts)
