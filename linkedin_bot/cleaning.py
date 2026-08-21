from collections.abc import Callable
import re

from linkedin_bot.config import HASHTAGS, REQUIRED_HASHTAGS


def strip_think_blocks(text: str) -> str:
    """
    Remove <think>...</think> reasoning blocks emitted by Qwen3.
    Also handles unclosed blocks where model hit token limit mid-reasoning.
    """
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<think>[\s\S]*$', '', text, flags=re.IGNORECASE)
    return text.strip()


def clean_markdown(text):
    # Safety net — strip any think blocks that survived earlier passes
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<think>[\s\S]*$', '', text, flags=re.IGNORECASE)

    # Remove bold **text** or __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)

    # Remove italic *text* or _text_ (word-boundary guard to protect hashtags)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.*?)_(?!\w)', r'\1', text)

    # Remove headers ### ## # — only at start of line AND followed by a space
    text = re.sub(r'^(#{1,6})\s+', '', text, flags=re.MULTILINE)

    # Remove bullet points - or * at start of line
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)

    # Remove numbered lists 1. 2. 3.
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Remove horizontal rules ---
    text = re.sub(r'---+', '', text)

    # Remove backticks for inline code
    text = re.sub(r'`(.*?)`', r'\1', text)

    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove emojis and unicode symbols — preserve plain ASCII (including # in C#)
    text = re.sub(
        r'[\U0001F600-\U0001F64F'
        r'\U0001F300-\U0001F5FF'
        r'\U0001F680-\U0001F6FF'
        r'\U0001F700-\U0001F77F'
        r'\U0001F780-\U0001F7FF'
        r'\U0001F800-\U0001F8FF'
        r'\U0001F900-\U0001F9FF'
        r'\U0001FA00-\U0001FA6F'
        r'\U0001FA70-\U0001FAFF'
        r'\U00002702-\U000027B0'
        r'\U000024C2-\U0001F251'
        r']+',
        '',
        text
    )

    # Strip "hashtag#" that some models write before # signs
    text = re.sub(r'\bhashtag#', '#', text, flags=re.IGNORECASE)

    # Clean up extra blank lines (more than 2 in a row)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def strip_topic_line(text: str) -> str:
    """
    Removes the 'TOPIC: ...' debug line the model outputs at the top.
    Runs after the critique pass so the critique prompt can reference it.
    """
    return re.sub(r'^TOPIC:.*\n?', '', text, flags=re.IGNORECASE).strip()


def enforce_hashtags(text: str) -> str:
    """
    Strips any existing hashtag block from the post body, then appends
    the canonical hashtag line. Handles hashtags on their own line OR
    appended inline to the last sentence.
    """
    for tag in HASHTAGS:
        text = text.replace(tag, "")

    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    return text + "\n\n" + REQUIRED_HASHTAGS


def truncate_for_linkedin(text: str, limit: int = 2900) -> str:
    """
    Hard cap at 2900 chars (100 char buffer under LinkedIn's 3000 limit).
    Truncates at the last full sentence before the limit, reattaches hashtags.
    Should never trigger in normal operation — purely a safety net.
    """
    if len(text) <= limit:
        return text

    lines = text.strip().splitlines()
    hashtag_line = ""
    if lines and lines[-1].strip().startswith("#"):
        hashtag_line = "\n\n" + lines[-1]
        text = "\n".join(lines[:-1]).strip()

    cap = limit - len(hashtag_line)
    truncated = text[:cap]
    last_stop = max(truncated.rfind(". "), truncated.rfind(".\n"))
    if last_stop != -1:
        truncated = truncated[:last_stop + 1]

    result = truncated.strip() + hashtag_line
    print(f"WARNING: Post truncated from {len(text)} to {len(result)} characters.")
    return result


class CleaningPipeline:
    """Chain of Responsibility: each step transforms the post text in order."""

    def __init__(self, steps: list[Callable[[str], str]]):
        self._steps = steps

    def apply(self, text: str) -> str:
        for step in self._steps:
            text = step(text)
        return text


def default_cleaning_pipeline() -> CleaningPipeline:
    return CleaningPipeline([
        strip_think_blocks,
        strip_topic_line,
        clean_markdown,
        enforce_hashtags,
        truncate_for_linkedin,
    ])
