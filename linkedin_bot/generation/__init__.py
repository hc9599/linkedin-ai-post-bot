"""
Turn a pile of articles into a LinkedIn draft, then a second-pass edit.

draft()   = creative write
critique() = "did this fail any of our quality checks?" rewrite
"""
from datetime import datetime
import random
import re

from linkedin_bot.cleaning import strip_think_blocks, strip_topic_line
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
from linkedin_bot.history import PostHistory, first_line, opener_overlap
from linkedin_bot.hooks.world import WorldHookSet, current_day_context
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost

SAMPLE_COUNT = 5
_WINNER_RE = re.compile(r"WINNER:\s*(\d+)", re.IGNORECASE)
_SAMPLE_RE = re.compile(r"\b(?:sample|winner)\s*[:#-]?\s*(\d+)\b", re.IGNORECASE)
_WEEKDAY_NAMES = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)
_CLOCK_RE = re.compile(
    r"\b(?:1[0-2]|[1-9])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE,
)
_VIBE_HINTS = {
    0: ("inbox", "weekend", "standup", "monday", "fire drill", "week already"),
    1: ("tuesday", "already behind", "leftover", "flaky"),
    2: ("wednesday", "midweek", "hump", "red build", "coding block"),
    3: ("thursday", "ship tomorrow", "almost friday", "review pile"),
    4: ("friday", "deploy", "mentally gone"),
    5: ("saturday", "prod check", "weekend laptop"),
    6: ("sunday", "sunday scaries", "work laptop", "tomorrow's standup"),
}


def _topic_line(text: str) -> str:
    match = re.search(r"^TOPIC:\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _title_tokens(title: str) -> set[str]:
    return {tok.lower() for tok in re.findall(r"[A-Za-z][A-Za-z0-9.]+", title) if len(tok) >= 5}


def _score_sample(
    text: str,
    titles: list[str],
    token_sets: list[set[str]],
    index: int,
    today_name: str,
    weekday: int,
    history: PostHistory | None = None,
    sibling_openers: list[str] | None = None,
) -> int:
    """Local backup when Groq does not return WINNER."""
    if not text.strip():
        return -10_000
    body = strip_topic_line(text).lower()
    score = 0
    today_l = today_name.lower()
    if today_l in body:
        score += 3
    for day in _WEEKDAY_NAMES:
        if day != today_l and re.search(rf"\b{day}\b", body):
            score -= 6
    if weekday != 4 and ("friday deploy" in body or "friday roulette" in body):
        score -= 8
    if any(hint in body for hint in _VIBE_HINTS.get(weekday, ())):
        score += 3
    if "?" in text:
        score += 2
    words = len(text.split())
    if 50 <= words <= 110:
        score += 1
    elif words > 140:
        score -= 2
    mine = token_sets[index]
    foreign: set[str] = set()
    for other_index, tokens in enumerate(token_sets):
        if other_index != index:
            foreign |= tokens
    leaked = foreign - mine
    own_title = titles[index].lower()
    if any(tok in body and tok not in own_title for tok in leaked):
        score -= 4
    if "one dry aside" in body or "on the menu" in body:
        score -= 2
    if _CLOCK_RE.search(text):
        score -= 4
    if history and history.reused_opener(text):
        score -= 5
    if history and history.reused_topic(_topic_line(text)):
        score -= 2
    for other in sibling_openers or []:
        if other and opener_overlap(text, other) >= 0.55:
            score -= 2
            break
    return score


def _heuristic_pick(
    samples: list[str],
    today_name: str,
    weekday: int,
    history: PostHistory | None = None,
) -> int:
    titles = [_topic_line(sample) for sample in samples]
    token_sets = [_title_tokens(title) for title in titles]
    openers = [first_line(sample) for sample in samples]
    best_index = 0
    best_score = -10_000
    for index, text in enumerate(samples):
        siblings = [line for i, line in enumerate(openers) if i != index]
        score = _score_sample(
            text, titles, token_sets, index, today_name, weekday, history, siblings,
        )
        print(f"  heuristic sample {index + 1}: {score}")
        if score > best_score:
            best_score = score
            best_index = index
    print(f"pick_best heuristic: sample {best_index + 1} (score {best_score})")
    return best_index


class PostGenerator:
    """Asks Groq to write, then asks Groq to fact-check the vibe of the draft."""

    def __init__(self, llm: LLMClient, history: PostHistory | None = None):
        self._llm = llm
        self._wit_mode = WIT_MODES[0]
        self._hooks: WorldHookSet | None = None
        self._history = history

    def draft(
        self,
        posts: list[CandidatePost],
        hooks: WorldHookSet | None = None,
        *,
        preferred_scene: str | None = None,
        avoid_openers: list[str] | None = None,
    ) -> str:
        """First pass: pick one article and write a LinkedIn post in the daily style."""
        today = datetime.now().strftime("%A, %B %d")
        today_name, day_vibe, weekday = current_day_context()
        self._hooks = hooks

        posts_text = "\n\n".join([
            f"[{p.source}] {p.title} ({p.reactions} reactions)\n{p.link}\n{p.summary}"
            for p in posts
        ])
        hooks_text = hooks.prompt_block() if hooks else (
            f"TODAY IS {today_name}. DAY VIBE: {day_vibe} "
            f"If you name a weekday, it must be {today_name}. "
            "Friday-deploy language is ONLY allowed on Friday. "
            "TRENDING HOOKS: none fetched. Open on a scene that feels like "
            f"{today_name}, not generic coffee that works any day."
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
        history_text = (
            self._history.prompt_block(avoid_openers)
            if self._history
            else "RECENT POSTS: none stored. Still write a fresh first line."
        )
        scene_text = (
            f"ASSIGNED OPENER SCENE (riff, do not copy word-for-word): {preferred_scene}"
            if preferred_scene
            else "Pick one unused daily-life scene. Do not default to standup + inbox + coffee."
        )

        prompt = f"""Today is {today}. Ghostwrite a LinkedIn post as if YOU are a senior C#/.NET \
developer posting from your own account. 5+ years backend.

TARGET SCORES (hit these, nothing else):
- HUMAN 10/10: a coworker would swear you typed this on your phone. Not a PR. \
Not a template hook. Not ChatGPT. Not a recipe.
- LAYMAN 5/10: keep the C# name (State.Message, binlog, dotnet tool exec). \
Add ONE short gloss in normal words, then move on. Do not rewrite the whole post \
for a non-developer. Do not lecture. 5/10 = gist is guessable, still a dev post.

HUMAN 10 rules:
- 3 short paragraphs, blank lines. First line can be a fragment.
- Closer must be a real question to the feed.
- Do not copy a hook line word-for-word. Riff on it.
- No fake work inventory ("I'm adding a contract test", "my parsing scripts"). \
Opinion only: I'll try it / I'll skip it / this annoyed me.
- Ban PR-speak: downstream consumers, verify the shape, contract test, parsing scripts.
- Ban teaching: "so my X can", "this means that".

LAYMAN 5 rules:
- One clause max, like "State.Message - the extra copy of the same log line".
- Then keep talking like a .NET person. Do not explain JSON, CI, or logging from scratch.

JOB: open on TODAY'S weekday vibe ({today_name}: {day_vibe}) or a trending \
headline if the analogy is obvious. Then post YOUR viewpoint on ONE .NET article. \
You did not write the article. You did not ship their product. Do not rewrite their blog.

DAY VIBE IS REQUIRED:
- The first paragraph must feel like {today_name}, using the assigned scene if given.
- Do not default to standup + inbox + coffee. That combo is worn.
- Do not open on generic microwave / cold coffee unless you tie it to {today_name}.
- If a coworker could paste the hook on Friday unchanged, rewrite it.

NO CLOCK TIMES:
- Do not write 10 am, 9:30, before noon, or any clock stamp.
- This post is not announcing when you sat down. "Already late" is fine.

{scene_text}

{history_text}

ONE ARTICLE ONLY:
- Every API, type, or tool name must come from the chosen TOPIC article.
- Do not mix leftovers from the other articles (fail: State.Message inside an \
xUnit ParallelMode post).

Ratio: hook ~20%, your take ~70%, one article fact ~10%.

VOICE:
- First person: I, we, our CI. Small hedge is OK ("I'll try it", "not sure it helps").
- Contractions required: don't, it's, I've, we're.
- Uneven sentence length. Mix a 4-word line with a longer one. Short paragraphs. Blank lines.
- Casual English. No lecture about a country or "the current climate".
- Name the API once. One gloss. Then the take. Skip TED framing.
- Straight ASCII quotes and hyphens. No em-dashes. No curly quotes.
- You may nod at the source in one short clause ("Microsoft's post"). \
Do not say "the article highlights".

HUMOR TODAY ({chosen_wit['name']}):
{chosen_wit['instruction']}

{hooks_text}

Never joke about crime, death, disaster, or communal news. If no headline is safe \
or the fit is forced, use a daily-life scene. Do not invent a news event.
Today is {today_name}. Do not say Monday/Tuesday/Wednesday/Thursday/Friday/Saturday/Sunday \
unless that word is {today_name}. No Friday-deploy jokes unless today is Friday.

BAD (robot / press-release):
"Enterprise .NET builds generate binary logs that hide root cause behind gigabytes of data. \
Most teams treat these as black boxes. In practice this turns a week-long mystery into minutes."

BAD (recipe / how-to, even if casual words):
"I've been pinning my tools for a while, but the SDK still defaults to the latest feed. \
My new recipe: lock the version on the command line and tack on --add-source to every CI step. \
Need an upgrade? Bump the version manually."

BAD (PR note + insider dump, last dry-run):
"The new JSON console logger in .NET 10 finally stopped echoing the formatted message in \
State.Message. Now the log only contains the top-level text, so my parsing scripts can drop \
the extra field. I'm adding a quick contract test for downstream consumers."

GOOD (human 10, layman 5):
"Coffee's cold. That unread chat can wait.

.NET 10 stopped stuffing the same log line into State.Message - the leftover copy of the text. \
I'll take it. Less junk in the JSON.

Anyone else still scraping console logs and regretting it?"

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

    def draft_samples(
        self,
        posts: list[CandidatePost],
        hooks: WorldHookSet | None = None,
        count: int = SAMPLE_COUNT,
        history: PostHistory | None = None,
    ) -> tuple[list[str], list[dict]]:
        """Write several drafts. Each call gets its own scene so first lines differ."""
        if history is not None:
            self._history = history
        samples: list[str] = []
        wits: list[dict] = []
        used_openers: list[str] = []
        scenes = list(hooks.routines) if hooks else []
        for index in range(count):
            print(f"\n--- Sample {index + 1}/{count} ---")
            scene = scenes[index] if index < len(scenes) else None
            text = strip_think_blocks(
                self.draft(
                    posts,
                    hooks,
                    preferred_scene=scene,
                    avoid_openers=used_openers,
                )
            )
            samples.append(text)
            wits.append(self._wit_mode)
            used_openers.append(first_line(text))
            print(text)
        return samples, wits

    def pick_best(self, samples: list[str]) -> int:
        """
        Ask Groq which sample sounds most like a human phone post.

        Returns a 0-based index. If Groq is silent, score locally.
        """
        usable = [(i, text) for i, text in enumerate(samples) if text.strip()]
        if not usable:
            raise Exception("pick_best: no drafts to choose from")
        if len(usable) == 1:
            return usable[0][0]

        today_name, day_vibe, weekday = current_day_context()
        packed = "\n\n".join(
            f"SAMPLE {i + 1}:\n{text}" for i, text in enumerate(samples)
        )
        prompt = f"""Pick the ONE LinkedIn draft we should publish.

Today is {today_name}.
DAY VIBE: {day_vibe}

Score in this order:
1. DAY VIBE: hook feels like {today_name}. Reject generic coffee/microwave that works any day.
2. HUMAN 10: sounds typed on a phone. Not a PR, recipe, or copied hook line.
3. ONE ARTICLE: reject drafts that mix a fact from a different article than their TOPIC line.
4. LAYMAN 5: keeps a C# name plus one short gloss. Not a beginner lecture.
5. Viewpoint, not an article rewrite. Real question at the end.
6. Weekday names must be {today_name} or none. No Friday-deploy unless Friday.
7. FRESH OPENER: reject first lines that remix recent posts (standup + inbox + coffee again).
8. NO CLOCK TIMES: reject 10 am / 9:30 / any clock stamp.

Drafts:
{packed}

Reply with exactly two lines and nothing else:
WINNER: <number 1-{len(samples)}>
REASON: <one short line>
"""
        result = self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )
        fallback = _heuristic_pick(samples, today_name, weekday, self._history)
        if not result:
            print("pick_best: Groq silent — using heuristic")
            return fallback

        cleaned = strip_think_blocks(result)
        print(f"pick_best: {cleaned.strip()}")
        match = _WINNER_RE.search(cleaned) or _SAMPLE_RE.search(cleaned)
        if not match:
            print("pick_best: could not parse WINNER — using heuristic")
            return fallback

        choice = int(match.group(1)) - 1
        if choice < 0 or choice >= len(samples) or not samples[choice].strip():
            print("pick_best: WINNER out of range — using heuristic")
            return fallback
        return choice

    def critique(self, draft: str) -> str:
        """Second pass: fix generic openers, filler, fake stats. Keep draft if AI chokes."""
        wit = self._wit_mode
        today_name, day_vibe, _weekday = current_day_context()
        hooks_text = (
            self._hooks.prompt_block()
            if self._hooks
            else (
                f"TODAY IS {today_name}. DAY VIBE: {day_vibe} "
                "Keep any opener that already feels like today. "
                "Rewrite generic coffee/microwave that works any day."
            )
        )
        history_text = (
            self._history.prompt_block()
            if self._history
            else "RECENT POSTS: none stored."
        )
        critique_prompt = f"""You are editing a LinkedIn post so a teammate would believe \
a senior C#/.NET developer typed it on their phone - not a model, \
not a press release, not a blog rewrite.

Rewrite anything that fails. If a section already sounds human and is their view, keep it.

HUMOR MODE ({wit['name']}): {wit['instruction']}

{hooks_text}

{history_text}

DRAFT:
{draft}

---

CHECK IN ORDER:

1. HUMAN 10 — Phone post or fail. Cut PR-speak (downstream consumers, contract test, \
verify the shape, parsing scripts). Cut copied hook lines. Cut fake "I'm adding a test". \
Force 3 short paragraphs + a real question at the end. Fragments OK.

1b. LAYMAN 5 — Keep the C# name. Add one short gloss if there is none. \
If the draft explains logging/JSON/CI from scratch, cut the lecture. 5/10 only.

2. OPENER — Generic ("Most teams...", Wikipedia)? Rewrite: daily-life scene, \
or a headline jab only if the analogy is obvious. No industry preamble.

3. REPETITION — Same point twice, or sentences that all start the same way? Cut the second.

4. FILLER / GPT TELLS — Cut or rewrite: "in practice", "the result is", "black box", \
"good reminder", "it's worth noting", "the importance of", "cannot be overstated", \
"highlights the importance", "valuable insights", "data-driven", "seamlessly", \
"underscores", "leverage", "unlock", "here's the thing", "when it comes to", \
"reliable and compliant", "guided investigation", "incident resolution", \
"what are your thoughts", "curious to hear", "it's not just", "more than just", \
"allows you to", "enables you to", "in the current climate", "in today's climate", \
"my new recipe", "pro tip", "silently hijack". \
Replace with a concrete statement or delete.

5. NOT A BLOG REWRITE — Feature list / how-it-works / benefits as if they wrote it? \
Cut recap to ONE sentence. Rest is their viewpoint (try / skip / argue).

6. HOOK BALANCE — If there is no trending or daily-life hook, add one from the list \
(routine if no headline fits). If the post is only a news recap and has no C#/.NET \
point, cut the news and land the .NET take. Never joke about crime, death, disaster, \
or communal news. Do not invent a headline.

7. POINT OF VIEW — Is ~70% their take? First person. Not a slogan. \
Do not claim they built the thing in the article.

8. INVENTED STATISTICS — Numbers that were not in the source? Delete them.

9. SOURCE NOD — OK: one short clause ("Microsoft's post"). \
Fail: "the article highlights", "the post explains" - rewrite those.

10. HUMAN VOICE — Still pass the coworker test after the casual rewrite. \
Em-dashes, curly quotes, even sentence length, paired adjectives, TED closer: fix. \
Contractions. Short paragraphs. ASCII punctuation.

11. WIT — If mode is witty or dry, one line a .NET person might smirk at. \
If mode is straight, do not add jokes. Never add "who's with me" energy.

12. CLOSER — Prefer a specific conversation starter. Ban "what are your thoughts" \
and "curious to hear".

13. WEEKDAY / DAY VIBE — Today is {today_name}. Mood: {day_vibe} \
If the draft names another weekday (especially Friday-deploy on a non-Friday), \
rewrite it to {today_name} or drop the day name. If the opener is generic \
microwave/coffee that works any day, rewrite it to a {today_name} scene. \
Do not write the words "dry aside".

14. ONE ARTICLE — If the draft mixes a fact from a different article than the \
TOPIC line (State.Message inside an xUnit post, ParallelMode inside an auth-metrics \
post), drop the leftover fact.

15. NO CLOCK TIMES — Cut 10 am, 9:30, before noon, or any clock stamp. \
"Already late" is fine. Do not imply when this post goes live.

16. FRESH OPENER — If the first line remixed standup + inbox + coffee or matches \
a recent opener, rewrite the first line to a new {today_name} scene.

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
