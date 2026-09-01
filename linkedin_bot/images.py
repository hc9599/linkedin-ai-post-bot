"""
Optional picture for the post.

Two renderers:
  1. PillowInfographicRenderer — programmatic 1080x1350 (4:5) infographic that
     visualises the LOGIC of the post: hook → take → reason → closer, with
     arrows so the argument chain is visible at a glance.
  2. PollinationsImageRenderer — free image site. Used as fallback.

Layout flow:
  final post ─► ImageService.extract_layout (LLM JSON, no inventing)
            ─► PillowInfographicRenderer.render (bytes)
            ─► LinkedIn publish.

Risk guards:
  - LLM hallucination: prompt forces verbatim phrasing; post-extract validator
    rejects layouts whose zones have no word-overlap with the post.
  - Missing fonts: explicit TTF paths across Windows / macOS / Linux; PIL bitmap
    is the last-resort fallback (pixelated but renders).
  - File size: cap enforced before return; > 1MB logs a warning, > 4MB returns
    None so the caller falls back to Pollinations. LinkedIn's own limit is 5MB.
"""
import json
import re
import urllib.parse
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from linkedin_bot.http import get_with_retry
from linkedin_bot.llm import LLMClient


class ImageRenderer(Protocol):
    """Anything that can turn an English prompt into image bytes (Pollinations path)."""
    def render(self, prompt: str) -> bytes | None: ...


# ---------------------------------------------------------------
# Infographic constants — LinkedIn 4:5 portrait, dev-friendly palette
# ---------------------------------------------------------------
INFOGRAPHIC_W = 1080
INFOGRAPHIC_H = 1350
BG_COLOR = (13, 17, 23)            # GitHub dark
FG_COLOR = (240, 246, 252)         # near-white
MUTED_COLOR = (139, 148, 158)      # dim grey
DIVIDER_COLOR = (48, 54, 61)
ACCENT_DEFAULT = (88, 166, 255)    # GitHub blue

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


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    """Parse '#RRGGBB' or 'RRGGBB' to an RGB tuple. None on garbage."""
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", (value or "").strip())
    if not match:
        return None
    n = int(match.group(1), 16)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


def _try_load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Try common bold TTFs across Windows, macOS, and Linux runners (incl. Inter
    / DejaVu / Liberation / Arial / Segoe). On a barebones CI runner with none of
    these installed, fall back to the PIL default bitmap font — text still
    renders, just smaller and pixelated. Better than crashing.

    First call logs which path (if any) was picked so CI failures are debuggable.
    """
    candidates = [
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/inter-bold.ttf",
        # Linux — common distro paths
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
        "/usr/share/fonts/truetype/Inter-Bold.ttf",
        "/usr/share/fonts/inter/Inter-Bold.ttf",
        "/usr/local/share/fonts/Inter-Bold.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttd",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # DejaVu fallback (very widely available on Linux)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            _log_font_once(f"loaded {path} (size {size})")
            return font
        except OSError:
            continue
    default = ImageFont.load_default(size=size)
    _log_font_once(f"no TTF found, using PIL default bitmap (size {size})")
    return default


_FONT_LOGGED = False


def _log_font_once(message: str) -> None:
    """First font-pick logs the source. Spammy if we logged every call."""
    global _FONT_LOGGED
    if _FONT_LOGGED:
        return
    print(f"Font: {message}")
    _FONT_LOGGED = True


def _overlap_tokens(text: str) -> set[str]:
    """Alphanumeric tokens, lowercased, stopwords removed — used for grounding."""
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in raw if t not in _OVERLAP_STOPWORDS and len(t) > 2}


def _zones_grounded(zones: list[str], post_content: str, min_hits: int = 3) -> bool:
    """
    Hallucination guard for the 4-zone argument-chain layout. At least
    `min_hits` of the zones must share >=1 token with the post.
    """
    post_tokens = _overlap_tokens(post_content)
    if not post_tokens:
        return False
    hits = 0
    for zone in zones:
        if zone and _overlap_tokens(zone) & post_tokens:
            hits += 1
    return hits >= min_hits


def _text_width(text: str, font) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _wrap(text: str, max_chars: int, font, max_width_px: int) -> list[str]:
    """Word-wrap by char count AND measured pixel width."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars or _text_width(candidate, font) > max_width_px:
            if current:
                lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_lightning(draw, cx: int, cy: int, size: int, fill) -> None:
    """Draw a lightning-bolt polygon centered on (cx, cy)."""
    s = size
    pts = [
        (cx - s * 0.20, cy - s * 0.50),
        (cx + s * 0.10, cy - s * 0.50),
        (cx - s * 0.05, cy - s * 0.05),
        (cx + s * 0.30, cy - s * 0.05),
        (cx - s * 0.10, cy + s * 0.50),
        (cx + s * 0.05, cy + s * 0.10),
        (cx - s * 0.30, cy + s * 0.10),
    ]
    draw.polygon(pts, fill=fill)


def _draw_arrow_right(draw, cx: int, cy: int, size: int, fill) -> None:
    """Draw a right-arrow (rectangle stem + triangle head)."""
    s = size
    # Stem
    draw.rectangle(
        [(cx - s * 0.50, cy - s * 0.12), (cx + s * 0.20, cy + s * 0.12)],
        fill=fill,
    )
    # Head
    pts = [
        (cx + s * 0.10, cy - s * 0.35),
        (cx + s * 0.55, cy),
        (cx + s * 0.10, cy + s * 0.35),
    ]
    draw.polygon(pts, fill=fill)


def _draw_check(draw, cx: int, cy: int, size: int, fill) -> None:
    """Draw a checkmark as a thick polyline (two strokes)."""
    s = size
    # Short stroke from upper-left to mid.
    draw.line(
        [(cx - s * 0.45, cy + s * 0.05), (cx - s * 0.10, cy + s * 0.40)],
        fill=fill,
        width=int(s * 0.18),
    )
    # Long stroke from mid to upper-right.
    draw.line(
        [(cx - s * 0.10, cy + s * 0.40), (cx + s * 0.50, cy - s * 0.40)],
        fill=fill,
        width=int(s * 0.18),
    )


def _draw_question(draw, cx: int, cy: int, size: int, font_q, fill) -> None:
    """Draw a '?' glyph centered on (cx, cy). ASCII works in every font."""
    glyph = "?"
    bbox = font_q.getbbox(glyph)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = cx - w // 2 - bbox[0]
    y = cy - h // 2 - bbox[1]
    draw.text((x, y), glyph, fill=fill, font=font_q)


class PillowInfographicRenderer:
    """Render a 1080x1350 infographic that visualises the post's argument chain."""

    def render(self, layout: dict) -> bytes | None:
        try:
            return self._render(layout)
        except Exception as e:
            print(f"Pillow infographic render failed: {e}")
            return None

    def _render(self, layout: dict) -> bytes:
        img = Image.new("RGB", (INFOGRAPHIC_W, INFOGRAPHIC_H), BG_COLOR)
        draw = ImageDraw.Draw(img)

        accent_rgb = _hex_to_rgb(layout.get("accent", "")) or ACCENT_DEFAULT

        font_subtitle = _try_load_font(22)
        font_label = _try_load_font(20)
        font_q = _try_load_font(72)         # '?' glyph
        font_text = _try_load_font(34)
        font_footer = _try_load_font(20)

        # ---- Top strip: brand + section label ----
        draw.rectangle([(80, 70), (200, 78)], fill=accent_rgb)
        draw.text(
            (80, 90),
            "C# / .NET  ·  logic flow",
            fill=MUTED_COLOR,
            font=font_subtitle,
        )

        # ---- Zones (4) — vertical argument chain with shape-icon + concise label ----
        # Each zone is a CONCEPT (≤5 words), not a sentence from the post.
        # Icons drawn as Pillow shapes (font-independent, always render).
        zones = [
            ("SPARK",   "lightning", layout.get("hook", "")),
            ("TAKE",    "arrow",     layout.get("take", "")),
            ("WHY",     "question",  layout.get("reason", "")),
            ("SO WHAT", "check",     layout.get("closer", "")),
        ]
        content_left = 80
        content_right = INFOGRAPHIC_W - 80

        zone_top = 150
        zone_h = 200
        gap = 36
        for index, (label, icon_kind, text) in enumerate(zones):
            zone_y = zone_top + index * (zone_h + gap)
            # Background panel
            draw.rectangle(
                [(content_left, zone_y), (content_right, zone_y + zone_h)],
                fill=(22, 27, 34),
            )
            # Accent left bar
            draw.rectangle(
                [(content_left, zone_y), (content_left + 8, zone_y + zone_h)],
                fill=accent_rgb,
            )
            # Icon frame
            icon_box_size = 110
            icon_x = content_left + 32
            icon_y = zone_y + (zone_h - icon_box_size) // 2
            draw.rectangle(
                [
                    (icon_x, icon_y),
                    (icon_x + icon_box_size, icon_y + icon_box_size),
                ],
                outline=accent_rgb,
                width=3,
            )
            # Draw the icon centered in its frame
            cx = icon_x + icon_box_size // 2
            cy = icon_y + icon_box_size // 2
            icon_size = 70
            if icon_kind == "lightning":
                _draw_lightning(draw, cx, cy, icon_size, accent_rgb)
            elif icon_kind == "arrow":
                _draw_arrow_right(draw, cx, cy, icon_size, accent_rgb)
            elif icon_kind == "question":
                _draw_question(draw, cx, cy, icon_size, font_q, accent_rgb)
            elif icon_kind == "check":
                _draw_check(draw, cx, cy, icon_size, accent_rgb)

            # Label tag (top-right of icon)
            draw.text(
                (icon_x + icon_box_size + 24, zone_y + 22),
                label,
                fill=MUTED_COLOR,
                font=font_label,
            )

            # Body — ULTRA concise, ≤5 words. Enforce cap.
            body = (text or "").strip() or "(missing)"
            words = body.split()
            if len(words) > 6:
                words = words[:6]
            body = " ".join(words)
            body_lines = _wrap(
                body,
                max_chars=22,
                font=font_text,
                max_width_px=INFOGRAPHIC_W - (icon_x + icon_box_size + 60),
            )
            tx = icon_x + icon_box_size + 24
            ty = zone_y + 60
            for line in body_lines:
                draw.text((tx, ty), line, fill=FG_COLOR, font=font_text)
                ty += 48

            # Arrow below (except after last zone) — drawn as stem + triangle.
            if index < len(zones) - 1:
                arrow_y = zone_y + zone_h + 8
                cx_a = INFOGRAPHIC_W // 2
                draw.line(
                    [(cx_a, arrow_y), (cx_a, arrow_y + 18)],
                    fill=accent_rgb,
                    width=3,
                )
                draw.polygon(
                    [
                        (cx_a - 8, arrow_y + 18),
                        (cx_a + 8, arrow_y + 18),
                        (cx_a, arrow_y + 30),
                    ],
                    fill=accent_rgb,
                )

        # ---- Footer ----
        source = (layout.get("source") or "").strip()
        footer_y = INFOGRAPHIC_H - 90
        if source:
            short = source if len(source) <= 56 else source[:53] + "..."
            draw.text(
                (80, footer_y),
                f"source: {short}",
                fill=MUTED_COLOR,
                font=font_footer,
            )
        draw.text(
            (80, footer_y + 30),
            "linkedin post  ·  human take",
            fill=MUTED_COLOR,
            font=font_footer,
        )

        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()

        # File-size guard. LinkedIn rejects >5MB; force fallback well below.
        if len(data) >= IMG_HARD_BYTES:
            print(
                f"Infographic too large ({len(data) // 1024}KB >= "
                f"{IMG_HARD_BYTES // 1024}KB) - caller will fall back."
            )
            return None
        if len(data) >= IMG_WARN_BYTES:
            print(f"WARNING: infographic large - {len(data) // 1024}KB")

        return data


class PollinationsImageRenderer:
    """Free image site. No API key. Can be slow or fail; that is OK as a fallback."""

    def render(self, prompt: str) -> bytes | None:
        encoded = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1200&height=627&nologo=true&enhance=true&model=flux"
        )

        print(f"Generating image with prompt: {prompt}")
        print("Waiting for image generation (this can take 15-30s)...")

        response = get_with_retry(url, timeout=60, attempts=4)
        if (
            response is not None
            and response.status_code == 200
            and response.headers.get("content-type", "").startswith("image")
        ):
            print(f"Image generated — {len(response.content) // 1024}KB")
            return response.content
        status = response.status_code if response is not None else "no response"
        print(f"Image generation failed: {status}")
        return None


class ImageService:
    """Owns layout extraction + render dispatch. Pillow primary, Pollinations fallback."""

    def __init__(self, llm: LLMClient, fallback_renderer: ImageRenderer):
        self._llm = llm
        self._fallback = fallback_renderer
        self._infographic = PillowInfographicRenderer()

    def generate_prompt(self, post_content: str) -> str | None:
        """Legacy path — kept for the Pollinations fallback."""
        system = (
            "You generate image prompts for LinkedIn tech posts. "
            "Output only the image prompt — no explanation, no preamble, no quotes. "
            "Style: clean flat illustration, dark background, subtle code or tech motif. "
            "No people, no faces, no text in the image. "
            "Keep it abstract and professional — suitable for a developer's LinkedIn post."
        )
        user = (
            f"Based on this LinkedIn post, write a short image generation prompt (max 30 words):\n\n"
            f"{post_content}"
        )
        return self._llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            max_tokens=80,
        )

    def extract_layout(self, post_content: str, source_title: str | None = None) -> dict | None:
        """
        Pull a 4-zone argument-chain layout from the post.

        Schema (each field grounded in the post):
          hook   — the article-side detail (number, gotcha, named tool) the post reacts to
          take   — the author's central claim / hot take
          reason — the supporting reasoning, parallel, or "why I think so"
          closer — the closing line / what to do next
          accent — #RRGGBB
          source — article title (added in code)

        Hallucination guard: at least 3 of the 4 zones must share >=1 token with the
        post. If the LLM fabricates, we reject and the caller falls back to Pollinations.
        """
        system = (
            "You extract layout data for a developer-focused LinkedIn infographic. "
            "The infographic shows the post's argument chain as four concise concept "
            "labels — NOT sentences from the post. Hard rules:\n"
            "1. Each zone is a SHORT CONCEPT LABEL — max 5 words. Examples of good "
            "labels: 'parent flag propagates', 'recorded flag flipped silently', "
            "'silent breaking change risk', 'document the sampling contract'. "
            "Bad labels are full sentences copied from the post.\n"
            "2. Every word must be drawn from the post. Do NOT invent any idea, "
            "claim, number, tool name, or detail that is not already in the post.\n"
            "3. If the post does not clearly contain a hook / take / reason / closer, "
            "return an empty string for the missing zone(s). Do NOT make them up.\n"
            "4. Reply with JSON only. No commentary. No markdown fences."
        )
        user = (
            "Extract this argument-chain layout from the post. Ultra-concise labels (max 5 words each):\n"
            "{\n"
            '  "hook":   "concept label, max 5 words, words drawn from the post",\n'
            '  "take":   "concept label, max 5 words, words drawn from the post",\n'
            '  "reason": "concept label, max 5 words, words drawn from the post",\n'
            '  "closer": "concept label, max 5 words, words drawn from the post",\n'
            '  "accent": "#RRGGBB hex that fits a dark-mode dev post"\n'
            "}\n\n"
            f"POST:\n{post_content}"
        )
        raw = self._llm.complete(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=200,
        )
        if not raw:
            return None
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except Exception as e:
            print(f"extract_layout: JSON parse failed: {e} — raw: {cleaned[:200]}")
            return None

        hook = str(data.get("hook", "")).strip()[:100]
        take = str(data.get("take", "")).strip()[:100]
        reason = str(data.get("reason", "")).strip()[:100]
        closer = str(data.get("closer", "")).strip()[:100]
        accent = str(data.get("accent", "")).strip()
        layout = {
            "hook": hook,
            "take": take,
            "reason": reason,
            "closer": closer,
            "accent": accent,
        }
        if source_title:
            layout["source"] = source_title.strip()[:120]

        # Grounding: at least 3 of 4 zones must share a token with the post.
        zones = [hook, take, reason, closer]
        if not _zones_grounded(zones, post_content, min_hits=3):
            print(
                "extract_layout: rejected — fewer than 3 zones grounded in post "
                f"(zones={zones})"
            )
            return None

        return layout

    def generate(self, post_content: str, source_title: str | None = None) -> bytes | None:
        """Render the post as an infographic. Falls back to Pollinations on any failure."""
        layout = self.extract_layout(post_content, source_title=source_title)
        # Require at least the take (central claim). Other zones optional but
        # the renderer fills missing ones with "(missing)" so the chain still flows.
        if layout and (layout.get("take") or layout.get("hook")):
            print(f"Infographic layout: {layout}")
            data = self._infographic.render(layout)
            if data:
                print(f"Infographic rendered — {len(data) // 1024}KB")
                return data
            print("Pillow render failed — falling back to Pollinations.")
        # Fallback path — keep the post going as text-with-banner if anything fails.
        image_prompt = self.generate_prompt(post_content)
        if not image_prompt:
            print("Could not generate image prompt — skipping image.")
            return None
        print(f"Image prompt (fallback): {image_prompt}")
        return self._fallback.render(image_prompt)
