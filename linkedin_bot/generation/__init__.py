from datetime import datetime
import random

from linkedin_bot.cleaning import strip_think_blocks
from linkedin_bot.config import REQUIRED_HASHTAGS
from linkedin_bot.generation.style import (
    BANNED_OPENERS,
    BANNED_PHRASES,
    ENDINGS,
    FORMATS,
    OPENERS,
    TOPIC_ANGLES,
    WORD_COUNTS,
)
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost


class PostGenerator:
    """Two-pass generation: draft, then self-critique rewrite."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def draft(self, posts: list[CandidatePost]) -> str:
        today = datetime.now().strftime("%A, %B %d")
        weekday = datetime.now().weekday()

        posts_text = "\n\n".join([
            f"[{p.source}] {p.title} ({p.reactions} reactions)\n{p.summary}"
            for p in posts
        ])

        angle = TOPIC_ANGLES[weekday]
        chosen_opener = random.choice(OPENERS)
        chosen_ending = random.choice(ENDINGS)
        chosen_format = random.choice(FORMATS)
        chosen_word_count = random.choice(WORD_COUNTS)

        banned_phrases_str = "\n".join(f"- {p}" for p in BANNED_PHRASES)
        banned_openers_str = "\n".join(f"- {p}" for p in BANNED_OPENERS)

        prompt = f"""Today is {today}. You are ghostwriting a LinkedIn post for a senior C#/.NET developer \
with 5+ years of backend and enterprise experience.

TARGET AUDIENCE — write so both of these people find value in the post:
1. Recruiting managers: not developers. They assess whether this person thinks clearly, \
communicates well, and has genuine depth. They should come away thinking "this person knows \
what they are doing."
2. Developer community: experienced .NET and C# developers. They should find something \
specific, accurate, and worth engaging with — a real point they can agree with, push back on, \
or learn from.

The post must be descriptive enough that a non-developer can follow the point, and specific \
enough that an experienced developer respects it.

TODAY'S ANGLE:
{angle['focus']}

AUDIENCE SIGNAL FOR TODAY:
{angle['audience_signal']}

{angle['avoid']}

---

ARTICLE SELECTION:
Choose ONE article from the list below that best fits today's angle. Read the summary carefully. \
The post MUST reference at least one specific technical detail or concrete fact from the summary — \
not just the title. A post that could have been written from the title alone fails this test.

{posts_text}

---

FIRST LINE: Write exactly: TOPIC: [article title you chose]
Then write the post on a new line. Nothing else before the post.

---

POST REQUIREMENTS:

OPENER:
{chosen_opener}

Do NOT open with any of these patterns:
{banned_openers_str}

ENDING:
{chosen_ending}

FORMAT:
{chosen_format}

TONE:
- Clear and direct. Confident without being arrogant. Peer-level, not lecture-level.
- Dry wit is welcome. Corporate enthusiasm is not.
- Write like a developer who has seen things and formed opinions, not like someone summarising a press release.

POINT OF VIEW — you must take one:
BAD: "This is a good reminder that security should be top of mind." (no stance, obvious)
BAD: "This feature is worth paying attention to." (vague, non-committal)
GOOD: "Most teams apply these updates without reading the changelog — and that is exactly how \
silent regressions slip in."
GOOD: "The new collection expression syntax looks minor, but it quietly removes one of the most \
common sources of unnecessary allocations in everyday C# code."

NO INVENTED STATISTICS: Do not include any percentages, multipliers, or metrics that are not \
explicitly stated in the source article. Remove them. Do not replace with different numbers.

NO REPETITION: Each sentence must add something new. Do not restate the same point in different words.

NO INVENTED ANECDOTES: Do not write "I recall when..." or fabricated scenarios.
NO EMOJIS. NO MARKDOWN. NO SMILEY FACES.

WORD COUNT: {chosen_word_count}

HASHTAGS: On their own line at the very end, exactly: {REQUIRED_HASHTAGS}

BANNED PHRASES — do not use any of these:
{banned_phrases_str}
"""

        result = self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.90,
            max_tokens=1000,
        )

        if not result:
            raise Exception("generate_linkedin_post: all Groq attempts failed")

        return result

    def critique(self, draft: str) -> str:
        critique_prompt = f"""You are editing a LinkedIn post draft for a senior C#/.NET developer. \
Your job is to check it against the six failure modes below and rewrite only what fails. \
If a section passes, keep it exactly as written.

DRAFT:
{draft}

---

CHECK THESE SIX FAILURE MODES IN ORDER:

1. OPENER — Does it open with a generic observation like "Most teams...", "Have you ever wondered...", \
or "One of the most significant challenges is..."? If yes, rewrite the opener to open with a \
specific behaviour, a direct position, or a named tradeoff. Do not start with a generalisation.

2. REPETITION — Does any point appear more than once in different words? If yes, cut the second \
instance entirely. Every sentence must add something new. Also check for structural echoes: \
consecutive sentences opening with the same phrase pattern \
(e.g. "What stands out... What's underappreciated...") count as repetition even if the content \
differs. Cut or rewrite the second instance.

3. FILLER PHRASES — Does it contain any of these: "this is a good reminder", "it's worth noting", \
"the importance of", "cannot be overstated", "highlights the importance", "valuable insights", \
"data-driven approach", "demonstrates the platform", "underscores the severity", "seamlessly", \
"becoming a crucial component", "adaptability to emerging technologies", "work smarter not harder"? \
If yes, replace with a concrete statement or cut entirely.

4. ARTICLE SUMMARY TEST — Could this post have been written from the article title alone, \
without reading the summary? If yes, rewrite to anchor on one specific technical detail \
or concrete fact from the content that only someone who read the summary would know.

5. POINT OF VIEW — Is there a clear, stated position or take — not just description? \
If not, add one sentence that states what the author actually thinks about this.

6. INVENTED STATISTICS — Does the post contain any specific numbers, percentages, or metrics \
(e.g. "50-70% reduction", "3x faster") that were NOT explicitly stated in the source article? \
If yes, remove them entirely. Do not replace with different numbers. \
Rewrite the sentence to make the same point without fabricated figures.

7. PERSONA BREAK — Does the post contain phrases like "the article highlights", "the post explains", \
"according to the source", or any other phrasing that reveals the author is summarising something \
they read rather than sharing their own view? If yes, rewrite as a direct assertion in the \
author's own voice.

---

Output the rewritten post only.
No preamble. No explanation. No "Here is the rewritten post:".
Preserve the TOPIC: line at the top if present.
Preserve the hashtag line at the bottom exactly as written: {REQUIRED_HASHTAGS}
"""

        result = self._llm.complete(
            messages=[{"role": "user", "content": critique_prompt}],
            temperature=0.40,
            max_tokens=1500,
        )

        if not result:
            print("critique_and_rewrite: Groq failed — returning original draft")
            return draft

        cleaned_result = strip_think_blocks(result)
        draft_word_count = len(draft.split())
        result_word_count = len(cleaned_result.split())

        if result_word_count < (draft_word_count * 0.5):
            print(
                f"critique_and_rewrite: result ({result_word_count} words) is less than 50% of "
                f"draft ({draft_word_count} words) — critique likely failed, keeping draft"
            )
            return draft

        return result
