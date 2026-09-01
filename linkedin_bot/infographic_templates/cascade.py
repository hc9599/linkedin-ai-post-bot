"""
cascade — one trigger → many effects. Hero panel on top, three satellite
panels below with thin connector lines emanating from the hero.

Best when the post describes ripple effects / propagation / fan-out.
"""
from linkedin_bot.infographic_templates import (
    WIDTH, HEIGHT, PANEL_BG, PANEL_BORDER, FG, MUTED, FONT_STACK, BG,
    _svg_open, _defs, _background, _brand_mark, _footer,
    _wrap_lines, _escape, _font,
)


def _hero_panel(accent: str, body: str, x: int, y: int, w: int, h: int) -> str:
    label = (
        f'<text x="{x + 28}" y="{y + 38}" fill="{accent}" font-family="{_font()}" '
        f'font-size="18" font-weight="700" letter-spacing="3">TRIGGER</text>'
    )
    rect = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" ry="16" '
        f'fill="{PANEL_BG}" stroke="{accent}" stroke-width="2" '
        f'filter="url(#shadow)"/>'
    )
    lines = _wrap_lines(body, max_chars=30)[:3]
    body_markup = ""
    body_y = y + 96
    for i, line in enumerate(lines):
        body_markup += (
            f'<text x="{x + 28}" y="{body_y + i * 56}" fill="{FG}" '
            f'font-family="{_font()}" font-size="44" font-weight="700">'
            f'{_escape(line)}</text>'
        )
    return rect + label + body_markup


def _satellite(index: int, label: str, body: str, accent: str,
               x: int, y: int, w: int, h: int) -> str:
    """Small satellite panel + tiny accent dot."""
    rect = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" ry="12" '
        f'fill="{PANEL_BG}" stroke="{PANEL_BORDER}" stroke-width="1.5" '
        f'filter="url(#shadow)"/>'
    )
    # Tiny numbered badge (top-left)
    badge = (
        f'<circle cx="{x + 24}" cy="{y + 24}" r="11" fill="{accent}"/>'
        f'<text x="{x + 24}" y="{y + 30}" text-anchor="middle" fill="{BG}" '
        f'font-family="{_font()}" font-size="16" font-weight="700">'
        f'{index}</text>'
    )
    # Label
    eyebrow = (
        f'<text x="{x + 50}" y="{y + 30}" fill="{accent}" '
        f'font-family="{_font()}" font-size="14" font-weight="700" '
        f'letter-spacing="2">{_escape(label)}</text>'
    )
    lines = _wrap_lines(body, max_chars=16)[:2]
    body_markup = ""
    body_y = y + 70
    for i, line in enumerate(lines):
        body_markup += (
            f'<text x="{x + 24}" y="{body_y + i * 38}" fill="{FG}" '
            f'font-family="{_font()}" font-size="28" font-weight="600">'
            f'{_escape(line)}</text>'
        )
    return rect + badge + eyebrow + body_markup


def _connector(x1: int, y1: int, x2: int, y2: int, accent: str) -> str:
    """Thin dashed line from hero bottom to satellite top."""
    return (
        f'<path d="M{x1} {y1} C{x1} {y1 + 40}, {x2} {y2 - 40}, {x2} {y2}" '
        f'stroke="{accent}" stroke-width="2" fill="none" '
        f'stroke-dasharray="3 5" opacity="0.7"/>'
    )


BG_HEX = "#0d1117"  # kept for back-compat with any external refs


def render(zones: dict, accent: str, source: str) -> str:
    parts = [_svg_open(), _defs(accent), _background(), _brand_mark(accent)]

    # Hero panel
    hero_x, hero_y = 60, 160
    hero_w, hero_h = WIDTH - 120, 220
    parts.append(_hero_panel(accent, zones.get("hook", ""),
                              hero_x, hero_y, hero_w, hero_h))

    # Connector anchor — bottom of hero, three points
    cx = WIDTH // 2
    hero_bottom_y = hero_y + hero_h

    # Three satellites
    sat_y = hero_bottom_y + 160
    sat_w = (WIDTH - 180) // 3
    sat_h = 260
    sat_labels = ["EFFECT 1", "EFFECT 2", "EFFECT 3"]
    sat_keys = ["take", "reason", "closer"]
    satellite_centers_x = []
    for i in range(3):
        x = 60 + i * (sat_w + 30)
        cx_sat = x + sat_w // 2
        satellite_centers_x.append(cx_sat)
        # Connector from hero anchor to this satellite's top-center
        parts.append(_connector(cx, hero_bottom_y + 10, cx_sat, sat_y - 4, accent))
        parts.append(_satellite(i + 1, sat_labels[i],
                                zones.get(sat_keys[i], ""),
                                accent, x, sat_y, sat_w, sat_h))

    # Tiny headline above satellites
    parts.append(
        f'<text x="{cx}" y="{hero_bottom_y + 110}" text-anchor="middle" '
        f'fill="{MUTED}" font-family="{_font()}" font-size="20" '
        f'font-weight="600" letter-spacing="3">RIPPLE EFFECTS</text>'
    )

    parts.append(_footer(source, accent))
    parts.append("</svg>")
    return "".join(parts)