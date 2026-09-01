"""
HTML → PNG renderer for LinkedIn infographics.

Pipeline:
  layout dict ─► Jinja2 (HTML + base.css) ─► headless Chromium
              ─► 1080×1350 PNG bytes.

The browser is kept on a module-level lazy singleton so a single bot run pays
the launch cost once, not four times. The browser is closed at process exit
via the atexit hook — this is a short-lived CLI run, so an explicit shutdown
per call would dominate wall-clock time.
"""
from __future__ import annotations

import atexit
import base64
import re
import threading
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from linkedin_bot.infographic.highlight import highlight_csharp

# Canvas matches LinkedIn 4:5 portrait. Hard-coded so a layout file cannot
# drift away from the brand standard.
CANVAS_W = 1080
CANVAS_H = 1350

# Layout templates shipped next to this file.
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_ASSETS_FONTS_DIR = Path(__file__).parent / "assets" / "fonts"

# Lazily-initialised Jinja2 environment. The FileSystemLoader caches the
# compiled templates after first use.
_jinja_env: Environment | None = None
_jinja_lock = threading.Lock()


def _get_jinja() -> Environment:
    global _jinja_env
    if _jinja_env is not None:
        return _jinja_env
    with _jinja_lock:
        if _jinja_env is None:
            _jinja_env = Environment(
                loader=FileSystemLoader(str(_TEMPLATES_DIR)),
                autoescape=select_autoescape(["html"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return _jinja_env


def _read_base_css() -> str:
    """
    Inline base.css into each render so the rendered HTML is self-contained.

    We also base64-embed the bundled Inter TTFs and rewrite @font-face URLs to
    data: URLs. That keeps Playwright from issuing file:// fetches that some
    sandboxes block, and avoids the "font lottery" of relying on whichever
    TTF happens to be installed on the runner.
    """
    css_path = _TEMPLATES_DIR / "base.css"
    if not css_path.exists():
        return "/* base.css missing */"
    css = css_path.read_text(encoding="utf-8")

    # Strip the file:// @font-face blocks (we'll add data: URLs below).
    css = _strip_font_face(css)

    # Inject data: URLs for the bundled Inter TTFs.
    inter_regular_b64 = _maybe_base64(_ASSETS_FONTS_DIR / "Inter-Regular.ttf")
    inter_bold_b64 = _maybe_base64(_ASSETS_FONTS_DIR / "Inter-Bold.ttf")
    if inter_regular_b64 or inter_bold_b64:
        injected = "\n/* Bundled Inter via data: URL */\n"
        if inter_regular_b64:
            injected += (
                '@font-face { font-family: "Inter"; '
                f'src: url("data:font/ttf;base64,{inter_regular_b64}") '
                'format("truetype"); font-weight: 400; font-display: swap; }\n'
            )
        if inter_bold_b64:
            injected += (
                '@font-face { font-family: "Inter"; '
                f'src: url("data:font/ttf;base64,{inter_bold_b64}") '
                'format("truetype"); font-weight: 700; font-display: swap; }\n'
            )
        css = injected + css
    return css


def _maybe_base64(path: Path) -> str:
    """Read file → base64 string. Empty string if missing or unreadable."""
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""


def _strip_font_face(css: str) -> str:
    """Drop existing @font-face blocks — we re-inject from bundled TTFs."""
    return re.sub(r"@font-face\s*\{[^}]*\}\s*", "", css, flags=re.DOTALL)


def _sanitize_accent(accent: str, default: str = "#FFC107") -> str:
    """Only allow #RRGGBB — used in CSS custom property and inline SVG."""
    value = (accent or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    return default


def _build_css(accent: str) -> str:
    """Base CSS plus per-render accent token for var(--accent) in templates."""
    safe = _sanitize_accent(accent)
    return f":root {{ --accent: {safe}; }}\n" + _get_base_css()


def _truncate(text: str, max_chars: int = 100) -> str:
    """Defensive cap on LLM-supplied zone text — overflow ruins a layout."""
    if not text:
        return ""
    text = str(text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def _truncate_title(text: str, max_chars: int = 64) -> str:
    if not text:
        return "C# / .NET"
    text = str(text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def _truncate_code(text: str, max_chars: int = 900) -> str:
    if not text:
        return ""
    text = str(text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def _build_context(plan: dict, source_title: str | None) -> dict | None:
    """Map a classified plan dict into Jinja2 template variables."""
    layout_id = (plan.get("layout_id") or "process_flow").strip()
    accent = _sanitize_accent(plan.get("accent") or "#FFC107")
    ctx: dict = {
        "css": _build_css(accent),
        "accent": accent,
        "title": _truncate_title(plan.get("title")),
        "source": _truncate_source(source_title or ""),
    }

    if layout_id == "code_compare":
        ctx.update({
            "before_label": _truncate(plan.get("before_label") or "Before", 40),
            "after_label": _truncate(plan.get("after_label") or "After", 40),
            "before_code_html": highlight_csharp(_truncate_code(plan.get("before_code"))),
            "after_code_html": highlight_csharp(_truncate_code(plan.get("after_code"))),
            "before_verbiage": _truncate(plan.get("before_verbiage") or "", 160),
            "after_verbiage": _truncate(plan.get("after_verbiage") or "", 160),
        })
        if not ctx["before_code_html"] or not ctx["after_code_html"]:
            return None
        return ctx

    if layout_id == "code_tip":
        ctx.update({
            "subtitle": _truncate(plan.get("subtitle") or "", 80),
            "code_html": highlight_csharp(_truncate_code(plan.get("code"))),
            "caption": _truncate(plan.get("caption") or "", 160),
        })
        if not ctx["code_html"]:
            return None
        return ctx

    if layout_id == "process_flow":
        steps_raw = plan.get("steps") or []
        steps = []
        for i, step in enumerate(steps_raw[:4], start=1):
            if not isinstance(step, dict):
                continue
            text = _truncate(step.get("text") or "", 80)
            if not text:
                continue
            steps.append({
                "number": i,
                "label": _truncate(step.get("label") or f"Step {i}", 24),
                "text": text,
                "detail": _truncate(step.get("detail") or "", 140),
            })
        if len(steps) < 3:
            return None
        ctx["subtitle"] = _truncate(plan.get("subtitle") or "", 80)
        ctx["steps"] = steps
        return ctx

    return None


def _truncate_source(text: str, max_chars: int = 56) -> str:
    """Footer source line — short ellipsis for long article titles."""
    if not text:
        return ""
    text = str(text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


# ----------------------- Playwright singleton -----------------------
_browser = None
_browser_lock = threading.Lock()
_browser_failed = False  # If Playwright fails to launch, don't retry per call.


def _get_browser():
    """
    Lazy, process-wide Chromium instance. Reused across all renders in one run.
    Closing per render would dominate wall-clock time and Chromium startup is
    not free (≈1.5s cold, ≈50ms warm).

    Returns None on any launch failure — caller falls back to text-only post.
    """
    global _browser, _browser_failed
    if _browser is not None:
        return _browser
    if _browser_failed:
        return None
    with _browser_lock:
        if _browser is not None:
            return _browser
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            _browser = pw.chromium.launch(args=["--no-sandbox"])
            atexit.register(_shutdown_browser, pw)
            return _browser
        except Exception as e:
            print(f"Playwright launch failed: {e}")
            _browser_failed = True
            return None


def _shutdown_browser(pw) -> None:
    """Best-effort cleanup on process exit."""
    global _browser
    try:
        if _browser is not None:
            _browser.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass
    _browser = None


_base_css_cache: str | None = None
_base_css_lock = threading.Lock()
_renderer_instance: "PlaywrightHtmlRenderer | None" = None
_renderer_lock = threading.Lock()


def _get_base_css() -> str:
    """Process-wide cached base.css (fonts embedded once per run)."""
    global _base_css_cache
    if _base_css_cache is not None:
        return _base_css_cache
    with _base_css_lock:
        if _base_css_cache is None:
            _base_css_cache = _read_base_css()
        return _base_css_cache


def get_renderer() -> "PlaywrightHtmlRenderer":
    """Shared renderer instance — avoids re-reading font files each call."""
    global _renderer_instance
    if _renderer_instance is not None:
        return _renderer_instance
    with _renderer_lock:
        if _renderer_instance is None:
            _renderer_instance = PlaywrightHtmlRenderer()
        return _renderer_instance


class PlaywrightHtmlRenderer:
    """Render an HTML template to PNG bytes via headless Chromium."""

    def render(self, plan: dict, source_title: str | None = None) -> bytes | None:
        """
        Render the plan to PNG bytes. Returns None on any failure.
        """
        layout_id = (plan.get("layout_id") or "process_flow").strip()
        ctx = _build_context(plan, source_title)
        if ctx is None:
            print(f"Could not build template context for {layout_id!r}")
            return None

        try:
            template = _get_jinja().get_template(f"{layout_id}.html")
            html = template.render(**ctx)
        except Exception as e:
            print(f"Template render failed ({layout_id}): {e}")
            return None

        browser = _get_browser()
        if browser is None:
            return None

        try:
            context = browser.new_context(
                viewport={"width": CANVAS_W, "height": CANVAS_H},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.set_content(html, wait_until="load")
            png = page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": CANVAS_W, "height": CANVAS_H},
            )
            context.close()
        except Exception as e:
            print(f"Playwright screenshot failed: {e}")
            return None

        return png
