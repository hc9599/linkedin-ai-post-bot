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
    WIT_MODES,
    WORD_COUNTS,
)
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost


class PostGenerator:
    """Asks Groq to write, then asks Groq to fact-check the vibe of the draft."""

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._wit_mode = WIT_MODES[0]

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
        # straight / dry / witty — witty a bit more often so the feed has a hook
        chosen_wit = random.choices(WIT_MODES, weights=[2, 3, 4], k=1)[0]
        self._wit_mode = chosen_wit
        print(f"Voice: {chosen_wit['name']}")

        banned_phrases_str = "\n".join(f"- {p}" for p in BANNED_PHRASES)
        banned_openers_str = "\n".join(f"- {p}" for p in BANNED_OPENERS)

        prompt = f"""Today is {today}. Ghostwrite a LinkedIn post as if YOU are a senior C#/.NET \
developer posting from your own account. 5+ years backend.

JOB: take inspiration from ONE article, then post YOUR viewpoint. \
You did not write the article. You did not ship their product. \
Do not rewrite their blog as if it is your content.

Ratio: about 20% spark (one concrete detail so a reader knows what nudged you), \
80% your take — agree, push back, what you'd try, what you'd skip.

The finished post must pass the coworker test: they should think you typed a reaction, \
not that you pasted a summary or claimed the work.

VOICE:
- First person: I, we, our CI. No fake war stories.
- Contractions: don't, it's, I've, we're.
- Uneven sentence length. Short paragraphs. Blank lines.
- Name APIs, tools, failure modes. Skip TED framing.
- Straight ASCII quotes and hyphens. No em-dashes. No curly quotes.
- You may nod at the source in one short clause ("Microsoft's post", "this writeup"). \
Do not say "the article highlights".

HUMOR TODAY ({chosen_wit['name']}):
{chosen_wit['instruction']}

BAD (you rewriting their post / pretending you built it):
"There's a VS Code analyzer that parses MSBuild binary logs, surfaces the failing task, \
suggests a fix, and diffs successive builds. This turns a week-long mystery into minutes."

BAD (press-release):
"Enterprise .NET builds generate binary logs that hide root cause behind gigabytes of data. \
Most teams treat these as black boxes."

GOOD (your view, sparked by it, a little bite):
"Binlogs have been sitting on our agents for years. We keep them the same way we keep \
old USB cables - theoretically useful, never touched.

Microsoft put Copilot on the failing MSBuild task and a build diff. If it actually points \
at the restore that died, I'll use it. If it just narrates the same XML in a friendly voice, I'm out."

TODAY'S ANGLE:
{angle['focus']}

{angle['audience_signal']}

{angle['avoid']}

---

ARTICLE SELECTION:
Choose ONE article from the list below that is clearly about C# or .NET \
(language, runtime, libraries, tooling, or the .NET ecosystem). \
If an article is only loosely related, skip it. \
Read the summary. Steal ONE specific technical detail as proof you read it. \
Do not walk through the rest of the piece.

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

POINT OF VIEW — this is the post. The article is the excuse.
BAD: "This is a good reminder that security should be top of mind."
BAD: restating the article's feature list in your own words.
GOOD: "I'll read the changelog on this one. That's where the silent break usually hides."
GOOD: "Collection expressions look small. They kill allocations I still see in reviews."

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
            temperature=0.88 if chosen_wit["name"] == "witty" else 0.80,
            max_tokens=1000,
        )

        if not result:
            raise Exception("generate_linkedin_post: all Groq attempts failed")

        return result

    def critique(self, draft: str) -> str:
        """Second pass: fix generic openers, filler, fake stats. Keep draft if AI chokes."""
        wit = self._wit_mode
        critique_prompt = f"""You are editing a LinkedIn post so it sounds like a real senior \
C#/.NET developer reacting to something they read — not rewriting the article, \
not a press release, not ChatGPT.

Rewrite anything that fails. If a section already sounds human and is their view, keep it.

HUMOR MODE ({wit['name']}): {wit['instruction']}

DRAFT:
{draft}

---

CHECK IN ORDER:

1. OPENER — Generic ("Most teams...", "Have you ever wondered...", Wikipedia definition)? \
Rewrite: named tool/API, annoyance, or a witty hook. No industry preamble.

2. REPETITION — Same point twice, or sentences that all start the same way? Cut the second.

3. FILLER / GPT TELLS — Cut or rewrite: "in practice", "the result is", "black box", \
"good reminder", "it's worth noting", "the importance of", "cannot be overstated", \
"highlights the importance", "valuable insights", "data-driven", "seamlessly", \
"underscores", "leverage", "unlock", "here's the thing", "when it comes to", \
"reliable and compliant", "guided investigation", "incident resolution", \
"what are your thoughts", "curious to hear", "it's not just", "more than just", \
"allows you to", "enables you to". Replace with a concrete statement or delete.

4. NOT A BLOG REWRITE — If this reads like the author explaining the article's product \
(feature list, how it works, benefits) as if they wrote it, cut the recap to ONE sentence \
and make the rest their viewpoint (try / skip / argue). \
Keep ONE concrete detail as spark. Do not add more summary.

5. POINT OF VIEW — Is ~80% their take? If not, add it. First person. Not a slogan. \
Do not claim they built the thing in the article.

6. INVENTED STATISTICS — Numbers that were not in the source? Delete them. Do not invent new ones.

7. SOURCE NOD — OK: one short clause ("Microsoft's post", "this writeup"). \
Fail: "the article highlights", "the post explains", "according to the source" — rewrite those.

8. HUMAN VOICE — ChatGPT tells: em-dashes, curly quotes, even sentence length, paired \
adjectives, lecture tone. Fix: contractions, short paragraphs, uneven rhythm, ASCII punctuation.

9. WIT — If mode is witty or dry, there should be one line a .NET person might smirk at. \
If missing, add one. If mode is straight, do not add jokes. Never add "who's with me" energy.

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
