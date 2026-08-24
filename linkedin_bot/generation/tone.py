"""
Pass 2 — tone router.

Classify the topic locally from title + facts. No Groq call.
The label goes into Pass 1 as {TONE} before any writing.
"""
from linkedin_bot.generation.style import TONES

_SERIOUS = (
    "breaking", "break", "deprecat", "obsolete", "removed", "removal",
    "migrat", "layoff", "laid off", "cve", "vulnerab", "security",
    "exploit", "patch tuesday", "breaking change", "incompatible",
)
_WITTY = (
    "syntax", "sugar", "tooling", "sdk", "cli", "preview", "benchmark",
    "meme", "drama", "hot reload", "source generator", "collection expression",
    "primary constructor", "fancy", "one-liner",
)
_CONFIDENT = (
    "best practice", "best practices", "design pattern", "pattern",
    "career", "advice", "clean code", "solid", "architecture",
    "how you should", "why you should",
)


def classify_tone(title: str, facts: list[str]) -> str:
    """
    Return a TONES key: serious / witty / confident.

    Keyword buckets match the Pass 2 spec. Ties go serious > witty > confident.
    Unclear topics default witty so the post does not go lecture-mode.
    """
    text = " ".join([title, *facts]).lower()
    scores = {
        "serious": sum(1 for kw in _SERIOUS if kw in text),
        "witty": sum(1 for kw in _WITTY if kw in text),
        "confident": sum(1 for kw in _CONFIDENT if kw in text),
    }
    if scores["serious"]:
        key = "serious"
    elif scores["confident"] > scores["witty"]:
        key = "confident"
    elif scores["witty"]:
        key = "witty"
    else:
        key = "witty"
    print(f"Pass 2 — tone: {key} ({TONES[key]})")
    return key


def tone_label(key: str) -> str:
    return TONES.get(key, TONES["witty"])
