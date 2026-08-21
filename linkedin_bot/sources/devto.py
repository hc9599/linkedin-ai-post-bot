import re
import time

from linkedin_bot.http import fetch_json
from linkedin_bot.models import CandidatePost


def _clean_body(body: str) -> str:
    body = re.sub(r"```[\s\S]*?```", "", body)
    body = re.sub(r"`[^`]+`", "", body)
    body = re.sub(r"^#{1,6}\s.*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", body)
    body = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", body)
    body = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:800]


def fetch_devto_article_body(url: str) -> str:
    """
    Fetches the full body_markdown of a dev.to article via the articles API.
    Returns up to 800 chars of cleaned prose.
    Falls back to empty string on any error.
    """
    if not url:
        return ""

    path = url.replace("https://dev.to/", "").rstrip("/")
    if not path or "/" not in path:
        return ""

    payload = fetch_json(f"https://dev.to/api/articles/{path}", attempts=3, timeout=15)
    if not isinstance(payload, dict):
        return ""

    body = payload.get("body_markdown", "")
    if not body:
        return ""
    return _clean_body(body)


class DevToSource:
    """Pulls recent articles from dev.to tagged 'dotnet' and 'csharp'."""

    def fetch(self) -> list[CandidatePost]:
        tags = ["dotnet", "csharp"]
        posts: list[CandidatePost] = []

        for tag in tags:
            url = f"https://dev.to/api/articles?tag={tag}&per_page=20&top=7"
            print(f"Fetching dev.to tag: #{tag}...")
            payload = fetch_json(url, timeout=20, attempts=5)
            if not isinstance(payload, list):
                print(f"  dev.to #{tag}: no article list — skipping")
                continue

            print(f"  dev.to #{tag}: {len(payload)} articles fetched")

            for article in payload:
                title = article.get("title", "")
                if len(title) < 20:
                    continue

                article_url = article.get("url", "")
                description = article.get("description", "")[:300].strip()
                body = fetch_devto_article_body(article_url)
                time.sleep(0.3)

                if body:
                    summary = (description + " " + body).strip()[:800]
                else:
                    summary = description or title

                posts.append(CandidatePost(
                    title=title,
                    link=article_url,
                    summary=summary,
                    reactions=article.get("positive_reactions_count", 0),
                    source=f"dev.to/#{tag}",
                ))

        seen: set[str] = set()
        deduped: list[CandidatePost] = []
        for p in posts:
            if p.title not in seen:
                seen.add(p.title)
                deduped.append(p)

        print(f"Total dev.to posts collected: {len(deduped)}")
        return deduped
