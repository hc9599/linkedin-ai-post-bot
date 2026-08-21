"""
Turn a pile of articles into a LinkedIn draft, then a second-pass edit.

draft()   = creative write
critique() = "did this fail any of our quality checks?" rewrite
"""
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
    """Asks Groq to write, then asks Groq to fact-check the vibe of the draft."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def draft(self, posts: list[CandidatePost]) -> str:
        """First pass: pick one article and write a LinkedIn post in the daily style."""
        today = datetime.now().strftime("%A, %B %d")
        weekday = datetime.now().weekday()

        posts_text = "\n\n".join([
            f"[{p.source}] {p.title} ({p.reactions} reactions)\n{p.link}\n{p.summary}"
            for p in posts
        ])

        angle = TOPIC_ANGLES[weekday]
        chosen_opener = random.choice(OPENERS)
        chosen_ending = random.choice(ENDINGS)
        chosen_format = random.choice(FORMATS)
        chosen_word_count = random.choice(WORD_COUNTS)

        banned_phrases_str = "\n".join(f"- {p}" for p in BANNED_PHRASES)
        banned_openers_str = "\n".join(f"- {p}" for p in BANNED_OPENERS)

        prompt = f"""Today is {today}. Ghostwrite a LinkedIn post as if YOU are a senior C#/.NET \
developer posting from your own account after reading one article. 5+ years backend. \
Not a content intern. Not a thought-leadership ghostwriter. Not ChatGPT.

The finished post must pass the coworker test: if someone on your team saw it, they should \
think you typed it, not that a model summarised a blog.

VOICE (this is the main job):
- First person is fine: I, we, our CI, our solutions. No fake war stories.
- Contractions: don't, it's, I've, we're.
- Uneven sentence length. One short. Then a longer one. Not a drumbeat of similar clauses.
- Short paragraphs. Blank lines. How people actually post on LinkedIn.
- Name APIs, tools, and failure modes. Skip the TED framing.
- Straight ASCII quotes and hyphens. No em-dashes. No curly quotes.
- Do not write for recruiters. Do not explain software to a general audience.

BAD (AI / press-release — never do this):
"Enterprise .NET builds generate binary logs that hide the root cause of intermittent failures \
behind gigabytes of serialized data. Most teams treat these logs as black boxes. In practice this \
turns a week-long mystery into a few minutes of guided investigation, keeping pipelines reliable \
and compliant."

GOOD (human):
"Binlogs are already sitting on the agent after most of our CI runs. Almost nobody opens them \
because they're huge and the viewer is a chore.

There's a VS Code analyzer now that points Copilot at the failing MSBuild task and diffs two \
builds. That's the actual job — the flaky restore, not a demo.

I'll try it the next time the pipeline says failed and the console is useless."

TODAY'S ANGLE:
{angle['focus']}

{angle['audience_signal']}

{angle['avoid']}

---

ARTICLE SELECTION:
Choose ONE article from the list below that is clearly about C# or .NET \
(language, runtime, libraries, tooling, or the .NET ecosystem). \
If an article is only loosely related, skip it. \
Read the summary carefully. \
The post MUST reference at least one specific technical detail or concrete fact from the summary — \
not just the title. A post that could have been written from the title alone fails this test.

Keep the TOPIC line exact — we use it later to attach the source link to the LinkedIn post.

{posts_text}

---

FIRST LINE: Write exactly: TOPIC: then paste the chosen article title character-for-character \
from the list. Do not rewrite, market, or summarise the title.
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

POINT OF VIEW — take one, in human words:
BAD: "This is a good reminder that security should be top of mind."
BAD: "This feature is worth paying attention to."
BAD: "Most teams apply these updates without reading the changelog."
GOOD: "I'll read the changelog on this one. That's where the silent break usually hides."
GOOD: "Collection expressions look small. They kill a bunch of the allocations I still see in reviews."

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
            temperature=0.82,
            max_tokens=1000,
        )

        if not result:
            raise Exception("generate_linkedin_post: all Groq attempts failed")

        return result

    def critique(self, draft: str) -> str:
        """Second pass: fix generic openers, filler, fake stats. Keep draft if AI chokes."""
        critique_prompt = f"""You are editing a LinkedIn post so it sounds like a real senior \
C#/.NET developer typed it — not a language model, not a press release.

Rewrite anything that fails. If a section already sounds human and specific, keep it.

DRAFT:
{draft}

---

CHECK IN ORDER:

1. OPENER — Generic ("Most teams...", "Have you ever wondered...", Wikipedia definition of the \
problem)? Rewrite: named tool/API, or a concrete annoyance. No industry preamble.

2. REPETITION — Same point twice, or sentences that all start the same way? Cut the second.

3. FILLER / GPT TELLS — Cut or rewrite: "in practice", "the result is", "black box", \
"good reminder", "it's worth noting", "the importance of", "cannot be overstated", \
"highlights the importance", "valuable insights", "data-driven", "seamlessly", \
"underscores", "leverage", "unlock", "here's the thing", "when it comes to", \
"reliable and compliant", "guided investigation", "incident resolution", \
"what are your thoughts", "curious to hear", "it's not just", "more than just". \
Replace with a concrete statement or delete.

4. ARTICLE SUMMARY TEST — Could this have been written from the title alone? If yes, \
anchor on one specific technical detail from the content.

5. POINT OF VIEW — Is there a human take (try it, skip it, wait, this is the part that \
matters)? If not, add one short sentence in first person. Not a slogan.

6. INVENTED STATISTICS — Numbers that were not in the source? Delete them. Do not invent new ones.

7. PERSONA BREAK — "the article highlights", "the post explains", "according to the source"? \
Rewrite as the author's own words.

8. HUMAN VOICE — Does it still sound like ChatGPT?
Signs: em-dashes, curly quotes, every sentence the same length, paired adjectives \
("reliable and compliant"), "injects X into the Y loop", lecture tone, recap-then-moral.
Fix: contractions, short paragraphs with blank lines, uneven rhythm, straight ASCII \
punctuation, stop when the point is made. Coworker-test: would a teammate believe you wrote this?

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
