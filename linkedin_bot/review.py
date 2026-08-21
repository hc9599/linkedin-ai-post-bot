"""
Last look before LinkedIn.

Two jobs:
  1. Name the article we are talking about (title + link) on the post.
  2. Stop the send if the post is not really about C# / .NET.

Better to skip a day than publish a random off-topic take.
"""
import re

from linkedin_bot.config import HASHTAGS
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost
from linkedin_bot.sources.relevance import is_dotnet_relevant


def extract_topic_title(text: str) -> str | None:
    """Read the TOPIC: line the writer puts at the top. That is which article it picked."""
    match = re.search(r"^TOPIC:\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", value.lower()).strip()


_STOP_WORDS = {
    "a", "an", "the", "for", "with", "and", "of", "to", "in", "on",
    "from", "into", "how", "why", "what", "that", "this", "your",
}


def _tokens(value: str) -> set[str]:
    return {t for t in _norm(value).split() if len(t) > 2 and t not in _STOP_WORDS}


def _overlap_score(left: str, right: str) -> float:
    """Share of the shorter title that also appears in the longer one. 1.0 = same words."""
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def match_source(topic_title: str | None, posts: list[CandidatePost], body: str) -> CandidatePost | None:
    """
    Find the article the AI used.

    Models often rewrite the headline. We still match if enough words overlap
    (so "Meet the MSBuild Binlog Analyzer..." maps to "Analyze MSBuild Binary Logs...").
    """
    best: CandidatePost | None = None
    best_score = 0.0

    def consider(text: str, post: CandidatePost, bonus: float = 0.0) -> None:
        nonlocal best, best_score
        score = _overlap_score(text, post.title) + bonus
        if score > best_score:
            best = post
            best_score = score

    if topic_title:
        want = _norm(topic_title)
        for post in posts:
            got = _norm(post.title)
            if not got:
                continue
            if want == got or want in got or got in want:
                print(f"Review: exact source match -> {post.title}")
                return post
            consider(topic_title, post)

    for post in posts:
        consider(body, post)

    # Need a real overlap, not one shared word like "code".
    if best is not None and best_score >= 0.4:
        print(f"Review: fuzzy source match ({best_score:.2f}) -> {best.title}")
        return best
    return None


def _body_without_hashtags(text: str) -> str:
    body = text
    for tag in HASHTAGS:
        body = body.replace(tag, "")
    return body.strip()


def attach_source_credit(text: str, source: CandidatePost) -> str:
    """
    Stick the article name and URL on the post, just above the hashtags.

    We do this in code so the AI cannot "forget" to credit the piece.
    """
    lines = text.strip().splitlines()
    hashtag_line = ""
    if lines and lines[-1].strip().startswith("#"):
        hashtag_line = lines[-1].strip()
        body = "\n".join(lines[:-1]).strip()
    else:
        body = text.strip()

    credit = f"Source: {source.title} ({source.source})\n{source.link}"
    if hashtag_line:
        return f"{body}\n\n{credit}\n\n{hashtag_line}"
    return f"{body}\n\n{credit}"


def llm_dotnet_source_check(
    llm: LLMClient,
    post_text: str,
    source: CandidatePost,
) -> tuple[bool, str]:
    """
    Ask Groq: is this post actually C#/.NET, and is it about this article?

    Answer must start with PASS or FAIL. If Groq is silent, we do not publish.
    """
    prompt = f"""You are a last-chance checker before a LinkedIn post goes live.

The post MUST be about C# and/or .NET (the language, runtime, libraries, tooling, or ecosystem).
The views in the post MUST relate to the source article below. Not a random tech rant.

SOURCE SITE: {source.source}
SOURCE TITLE: {source.title}
SOURCE LINK: {source.link}
SOURCE SUMMARY:
{source.summary}

LINKEDIN POST:
{post_text}

Reply with exactly one line:
PASS
or
FAIL: <short reason in plain English>

PASS only if all are true:
1. A C# or .NET developer would recognise this as their world.
2. A reader can tell the take was sparked by that source article (a riff/opinion is enough; \
it does not need to summarise the article).
3. The post does not claim the author built or wrote the thing described in the source.
"""
    result = llm.complete(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=80,
    )
    if not result:
        return False, "checker did not answer — not publishing"

    line = result.strip().splitlines()[0].strip()
    if line.upper().startswith("PASS"):
        return True, line
    return False, line


def review_before_publish(
    llm: LLMClient,
    draft_with_topic: str,
    cleaned_post: str,
    candidates: list[CandidatePost],
) -> tuple[CandidatePost | None, str | None]:
    """
    Double-check before LinkedIn.

    Returns (source article, None) if OK to post.
    Returns (None, reason) if we should skip publishing.
    """
    topic = extract_topic_title(draft_with_topic)
    source = match_source(topic, candidates, cleaned_post)
    if source is None:
        return None, "could not match the post to a source article — not publishing"

    body = _body_without_hashtags(cleaned_post)
    keyword_ok = is_dotnet_relevant(body, source.title + " " + source.summary)
    if not keyword_ok:
        print(
            "Review: post body has no obvious C#/.NET words. "
            "Still asking the AI checker."
        )

    ok, detail = llm_dotnet_source_check(llm, cleaned_post, source)
    print(f"Review checker: {detail}")
    if not ok:
        return None, f"C#/.NET or source check failed: {detail}"

    return source, None
