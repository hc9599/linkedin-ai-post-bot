"""
Talking to the internet, the careful way.

GitHub Actions runs on shared cloud machines. Many sites treat those as bots
and return 403, 429, or a "please wait" page. This file:
  1. Sends a browser-looking User-Agent
  2. Retries a few times with a wait
  3. Gives up so the caller can try a backup URL
"""
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from linkedin_bot.config import USER_AGENT

try:
    import feedparser
except ImportError:
    feedparser = None

RETRYABLE_GET = {403, 408, 425, 429, 500, 502, 503, 504}
RETRYABLE_WRITE = {408, 425, 429, 500, 502, 503, 504}

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

_SESSION: requests.Session | None = None


def http_session() -> requests.Session:
    """One shared connection pool so we reuse settings (timeouts, retries, headers)."""
    global _SESSION
    if _SESSION is None:
        session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD", "POST", "PUT"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(DEFAULT_HEADERS)
        _SESSION = session
    return _SESSION


def _is_challenge_page(content: bytes) -> bool:
    """True if the site sent a captcha / "just a moment" wall instead of real data."""
    head = content[:2500].decode("utf-8", errors="ignore").lower()
    markers = (
        "just a moment",
        "cf-browser-verification",
        "please wait for verification",
        "attention required",
        "_incapsula_resource",
    )
    return any(marker in head for marker in markers)


def is_feed_payload(content: bytes) -> bool:
    """True if the bytes look like an RSS/Atom feed, not an HTML block page."""
    head = content.lstrip()[:2000].lower()
    return (
        b"<rss" in head
        or b"<feed" in head
        or b"<?xml" in head
        or b"<rdf:rdf" in head
    )


def get_with_retry(
    url: str,
    *,
    timeout: int = 20,
    attempts: int = 5,
    headers: dict | None = None,
    params: dict | None = None,
    retry_statuses: set[int] | None = None,
) -> requests.Response | None:
    """
    Download a web page/API and try again if the site is busy or blocking us.

    Returns the response if it looks usable. Returns None if every try failed
    so the caller can switch to a backup website.
    """
    retry_on = retry_statuses if retry_statuses is not None else RETRYABLE_GET
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    last_error = "no attempt"
    for attempt in range(attempts):
        try:
            response = http_session().get(
                url,
                headers=merged_headers,
                params=params,
                timeout=timeout,
            )
            if response.status_code in retry_on or _is_challenge_page(response.content):
                last_error = f"HTTP {response.status_code}"
                print(f"  retry {attempt + 1}/{attempts} {url} -> {last_error}")
            else:
                return response
        except requests.RequestException as e:
            last_error = str(e)
            print(f"  retry {attempt + 1}/{attempts} {url} -> {last_error}")

        time.sleep(min(2 ** attempt, 16))

    print(f"  giving up {url} ({last_error})")
    return None


def fetch_json(
    url: str,
    *,
    timeout: int = 20,
    attempts: int = 5,
    params: dict | None = None,
) -> object | None:
    """GET JSON (Hacker News, dev.to). None if the site refused or sent garbage."""
    response = get_with_retry(url, timeout=timeout, attempts=attempts, params=params)
    if response is None:
        return None
    if response.status_code != 200:
        print(f"  JSON {url}: HTTP {response.status_code}")
        return None
    try:
        return response.json()
    except ValueError as e:
        print(f"  JSON parse failed {url}: {e}")
        return None


def fetch_feed_entries(
    url: str,
    *,
    timeout: int = 20,
    attempts: int = 3,
    retry_statuses: set[int] | None = None,
) -> list:
    """
    Download an RSS feed ourselves, then parse it.

    We do not let feedparser fetch the URL. It announces itself as a bot and
    GitHub Actions IPs get blocked. We fetch with a browser-looking header,
    then only parse the bytes.
    """
    if feedparser is None:
        print("feedparser not installed — cannot parse RSS")
        return []

    response = get_with_retry(
        url,
        timeout=timeout,
        attempts=attempts,
        headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
        retry_statuses=retry_statuses,
    )
    if response is None:
        return []
    if response.status_code != 200:
        print(f"  feed {url}: HTTP {response.status_code}")
        return []
    if _is_challenge_page(response.content) or not is_feed_payload(response.content):
        print(f"  feed {url}: not RSS/Atom (blocked or HTML challenge)")
        return []

    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        print(f"  feed {url}: parse error — {feed.bozo_exception}")
        return []
    return list(feed.entries)


def request_write_with_retry(
    method: str,
    url: str,
    *,
    timeout: int = 30,
    attempts: int = 3,
    **kwargs,
) -> requests.Response:
    """Send data (LinkedIn post/upload). Retry if the network blipped. Raise if still failing."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            response = http_session().request(method, url, timeout=timeout, **kwargs)
            if response.status_code in RETRYABLE_WRITE:
                print(
                    f"  {method} retry {attempt + 1}/{attempts} {url} -> HTTP {response.status_code}"
                )
                time.sleep(min(2 ** attempt, 16))
                continue
            return response
        except requests.RequestException as e:
            last_exc = e
            print(f"  {method} retry {attempt + 1}/{attempts} {url} -> {e}")
            time.sleep(min(2 ** attempt, 16))

    if last_exc is not None:
        raise last_exc
    raise Exception(f"{method} {url} failed after {attempts} attempts")
