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
from linkedin_bot.hooks.world import WorldHookSet
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost


class PostGenerator:
    """Asks Groq to write, then asks Groq to fact-check the vibe of the draft."""

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._wit_mode = WIT_MODES[0]
        self._hooks: WorldHookSet | None = None

    def draft(self, posts: list[CandidatePost], hooks: WorldHookSet | None = None) -> str:
        """First pass: pick one article and write a LinkedIn post in the daily style."""
        today = datetime.now().strftime("%A, %B %d")
        weekday = datetime.now().weekday()
        self._hooks = hooks

        posts_text = "\n\n".join([
            f"[{p.source}] {p.title} ({p.reactions} reactions)\n{p.link}\n{p.summary}"
            for p in posts
        ])
        hooks_text = hooks.prompt_block() if hooks else (
            "TRENDING HOOKS: none fetched. Open on a daily-life scene "
            "(standup, Friday deploy, unread match chat) without inventing a news event."
        )

        angle = TOPIC_ANGLES[weekday]
        chosen_opener = random.choice(OPENERS)
        chosen_ending = random.choice(ENDINGS)
        chosen_format = random.choice(FORMATS)
        chosen_word_count = random.choice(WORD_COUNTS)
        # dry + witty heavier so it does not read like a status report
        chosen_wit = random.choices(WIT_MODES, weights=[1, 4, 5], k=1)[0]
        self._wit_mode = chosen_wit
        print(f"Voice: {chosen_wit['name']}")

        banned_phrases_str = "\n".join(f"- {p}" for p in BANNED_PHRASES)
        banned_openers_str = "\n".join(f"- {p}" for p in BANNED_OPENERS)

        prompt = f"""Today is {today}. Ghostwrite a LinkedIn post as if YOU are a senior C#/.NET \
developer posting from your own account. 5+ years backend.

COWORKER TEST (main job): a teammate should think you typed this on your phone after \
standup. Slack energy, slightly cleaned for LinkedIn. Not a newsletter. \
Not thought leadership. Not ChatGPT.

JOB: open on a trending global topic or a daily-life scene (headline only if the \
analogy is obvious). Then post YOUR viewpoint on ONE .NET article. You did not write \
the article. You did not ship their product. Do not rewrite their blog.

Ratio: hook ~20%, your take ~70%, one article fact ~10%.

VOICE:
- First person: I, we, our CI. Small hedge is OK ("I'll try it", "not sure it helps").
- Contractions required: don't, it's, I've, we're.
- Uneven sentence length. Mix a 4-word line with a longer one. Short paragraphs. Blank lines.
- Casual English. No lecture about a country or "the current climate".
- Name APIs, tools, failure modes. Skip TED framing.
- Straight ASCII quotes and hyphens. No em-dashes. No curly quotes.
- You may nod at the source in one short clause ("Microsoft's post"). \
Do not say "the article highlights".

HUMOR TODAY ({chosen_wit['name']}):
{chosen_wit['instruction']}

{hooks_text}

Never joke about crime, death, disaster, or communal news. If no headline is safe \
or the fit is forced, use a daily-life scene. Do not invent a news event.

BAD (robot / press-release):
"Enterprise .NET builds generate binary logs that hide root cause behind gigabytes of data. \
Most teams treat these as black boxes. In practice this turns a week-long mystery into minutes."

BAD (rewriting their post):
"There's a VS Code analyzer that parses MSBuild binary logs, surfaces the failing task, \
and diffs successive builds."

GOOD (human, trending or daily-life hook, your view):
"Binlogs sit on the agent like that unread group chat about last night's match. We keep them. \
We never open them.

Microsoft put Copilot on the failing MSBuild task. If it points at the dead restore, I'll use it. \
If it just narrates the XML, I'm out.

Anyone else's CI still feel like a Friday deploy?"

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
        hooks_text = (
            self._hooks.prompt_block()
            if self._hooks
            else "No hook list stored. Keep any trending or daily-life opener that is already casual."
        )
        critique_prompt = f"""You are editing a LinkedIn post so a teammate would believe \
a senior C#/.NET developer typed it on their phone - not a model, \
not a press release, not a blog rewrite.

Rewrite anything that fails. If a section already sounds human and is their view, keep it.

HUMOR MODE ({wit['name']}): {wit['instruction']}

{hooks_text}

DRAFT:
{draft}

---

CHECK IN ORDER:

1. OPENER — Generic ("Most teams...", Wikipedia)? Rewrite: daily-life scene, \
or a headline jab only if the analogy is obvious. No industry preamble.

2. REPETITION — Same point twice, or sentences that all start the same way? Cut the second.

3. FILLER / GPT TELLS — Cut or rewrite: "in practice", "the result is", "black box", \
"good reminder", "it's worth noting", "the importance of", "cannot be overstated", \
"highlights the importance", "valuable insights", "data-driven", "seamlessly", \
"underscores", "leverage", "unlock", "here's the thing", "when it comes to", \
"reliable and compliant", "guided investigation", "incident resolution", \
"what are your thoughts", "curious to hear", "it's not just", "more than just", \
"allows you to", "enables you to", "in the current climate", "in today's climate". \
Replace with a concrete statement or delete.

4. NOT A BLOG REWRITE — Feature list / how-it-works / benefits as if they wrote it? \
Cut recap to ONE sentence. Rest is their viewpoint (try / skip / argue).

5. HOOK BALANCE — If there is no trending or daily-life hook, add one from the list \
(routine if no headline fits). If the post is only a news recap and has no C#/.NET \
point, cut the news and land the .NET take. Never joke about crime, death, disaster, \
or communal news. Do not invent a headline.

6. POINT OF VIEW — Is ~70% their take? First person. Not a slogan. \
Do not claim they built the thing in the article.

7. INVENTED STATISTICS — Numbers that were not in the source? Delete them.

8. SOURCE NOD — OK: one short clause ("Microsoft's post"). \
Fail: "the article highlights", "the post explains" - rewrite those.

9. HUMAN VOICE — Must pass the coworker test. ChatGPT tells: em-dashes, curly quotes, \
even sentence length, paired adjectives, lecture tone, recap-then-moral, TED closer. \
Fix: contractions, short paragraphs, uneven rhythm, ASCII punctuation. \
Write like Slack cleaned for LinkedIn. If a teammate would smell ChatGPT, rewrite.

10. WIT — If mode is witty or dry, one line a .NET person might smirk at. \
If mode is straight, do not add jokes. Never add "who's with me" energy.

11. CLOSER — Prefer a specific conversation starter ("Anyone else's CI still feel like \
a Friday deploy?"). Ban "what are your thoughts" and "curious to hear".

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
