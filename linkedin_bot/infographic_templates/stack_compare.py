"""
stack_compare — layered concept build-up. Four cards overlapping with a
slight rotation each, right-most on top (the post's TAKE).

Best for posts about features / layers / build-up of ideas.
"""
import math

from linkedin_bot.infographic_templates import (
    WIDTH, HEIGHT, PANEL_BG, PANEL_BORDER, FG, MUTED, FONT_STACK,
    _svg_open, _defs, _background, _brand_mark, _footer,
    _wrap_lines, _escape, _font,
)


def _card(accent: str, label: str, body: str,
          cx: int, cy: int, w: int, h: int, rot_deg: float,
          is_hero: bool) -> str:
    """One rotated card centered on (cx, cy). Hero card has accent border."""
    stroke = accent if is_hero else PANEL_BORDER
    stroke_w = 3 if is_hero else 1.5
    body_size = 30 if is_hero else 26
    label_size = 16 if is_hero else 14
    # We rotate around the card's own centre using a nested transform.
    inner_x = -w // 2
    inner_y = -h // 2
    rect = (
        f'<rect x="{inner_x}" y="{inner_y}" width="{w}" height="{h}" '
        f'rx="14" ry="14" fill="{PANEL_BG}" stroke="{stroke}" '
        f'stroke-width="{stroke_w}" filter="url(#shadow)"/>'
    )
    eyebrow_color = accent if is_hero else MUTED
    eyebrow = (
        f'<text x="{inner_x + 24}" y="{inner_y + 36}" fill="{eyebrow_color}" '
        f'font-family="{_font()}" font-size="{label_size}" font-weight="700" '
        f'letter-spacing="2">{_escape(label)}</text>'
    )
    lines = _wrap_lines(body, max_chars=14)[:3]
    body_markup = ""
    body_y = inner_y + 90
    for i, line in enumerate(lines):
        body_markup += (
            f'<text x="{inner_x + 24}" y="{body_y + i * (body_size + 10)}" '
            f'fill="{FG}" font-family="{_font()}" font-size="{body_size}" '
            f'font-weight="600">{_escape(line)}</text>'
        )
    return (
        f'<g transform="translate({cx} {cy}) rotate({rot_deg:.2f})">'
        f'{rect}{eyebrow}{body_markup}'
        f'</g>'
    )


def render(zones: dict, accent: str, source: str) -> str:
    parts = [_svg_open(), _defs(accent), _background(), _brand_mark(accent)]

    # Eyebrow header
    parts.append(
        f'<text x="{WIDTH // 2}" y="180" text-anchor="middle" fill="{MUTED}" '
        f'font-family="{_font()}" font-size="18" font-weight="600" '
        f'letter-spacing="4">LAYERED BUILD-UP</text>'
    )

    # Four cards, fanned left-to-right, right-most on top.
    labels = ["STEP 1", "STEP 2", "STEP 3", "TAKE"]
    keys = ["hook", "reason", "closer", "take"]
    card_w, card_h = 320, 520
    cy = 760
    # Total span = 3*stride + card_w. Want that <= WIDTH - 120.
    # WIDTH=1080 → 960 → stride <= (960-card_w)/3 = 213. Use 215 stride and shrink card to fit.
    stride = 220
    # Centre the whole fan under WIDTH.
    total_span = 3 * stride + card_w
    leftmost_cx = (WIDTH - total_span) // 2 + card_w // 2

    # Render right-to-left so the TAKE (right-most) paints last → on top.
    for i in range(3, -1, -1):
        cx_i = leftmost_cx + i * stride
        # Small rotation for fan feel. Range -6..+6 degrees.
        rot = (-6 + i * 4)
        is_hero = (labels[i] == "TAKE")
        # Slight extra height for hero.
        h = card_h + 40 if is_hero else card_h
        parts.append(_card(accent, labels[i],
                           zones.get(keys[i], ""),
                           cx_i, cy, card_w, h, rot, is_hero))

    parts.append(_footer(source, accent))
    parts.append("</svg>")
    return "".join(parts)