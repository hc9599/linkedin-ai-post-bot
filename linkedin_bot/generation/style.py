# Niche-agnostic generation constants.
# Niche-specific persona, angles, and hashtags live in profiles/*.yaml.

PASS3_REJECT = [
    "game-changer",
    "game changer",
    "unlock",
    "in today's world",
    "i'm thrilled",
    "i am thrilled",
    "let's dive in",
    "lets dive in",
    "thoughts?",
    "i shipped",
    "i shipped this",
    "i built this",
    "i built it",
    "i implemented this",
    "i deployed this",
    "i migrated to",
    "i tried this",
    "i tested this",
    "we shipped",
    "we shipped this",
    "we built this",
    "we migrated to",
    "we deployed",
    "my team built",
    "my team shipped",
]

OPENER_STYLES = [
    "Open mid-thought, like you already started talking. Not a question. Do not start with So,",
    "Open with a hot take in one short sentence. Not a question. Do not start with So,",
    "Open on one concrete gotcha or number from the facts. Not a question.",
    "Open like this class of bug burned you before. One line. Not a question.",
    "Open with two short contrast lines. X looks small. It is not.",
]

TONES = {
    "serious": "serious, slightly weary, one dry joke max",
    "witty": "witty, can be a bit unhinged, 1 joke minimum",
    "confident": "confident, mild sarcasm about people who don't do it right",
}

MAX_POST_WORDS = 220
