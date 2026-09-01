"""
Multi-pass generation loop.

Pass 2 classifies tone. Pass 1 drafts. Pass 3 rewrites only cliché lines.
Pass 4 re-rolls the opener if it clones the last few posts.
Pass 5 lives in review.py.
"""
from linkedin_bot.cleaning import strip_think_blocks
from linkedin_bot.config import REQUIRED_HASHTAGS
from linkedin_bot.generation.facts import key_facts, pick_article
from linkedin_bot.generation.reject import reject_hits
from linkedin_bot.generation.style import MAX_POST_WORDS, OPENER_STYLES, PASS3_REJECT
from linkedin_bot.generation.tone import classify_tone, tone_label
from linkedin_bot.generation.variance import LoopState
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost

_PERSONA = """You are a senior software engineer, 8+ yrs, posting on LinkedIn casually between \
meetings. You read an article today and it triggered a thought about your own past \
work. You have shipped things in your career — but you did NOT ship, build, migrate \
to, deploy, or use whatever THIS article is describing. You are reacting from the \
outside, not as a user of the thing. "This reminded me of X from a job years ago" \
is fine. "I shipped this" or "I tried this and" about the article's subject is \
FORBIDDEN. Write like you're texting a dev friend who'll understand the joke, not \
addressing 'my network'. Never start with 'In today's fast-paced world' or 'I'm \
excited to share'. No emoji unless it's one dry 😅 or 💀 max. Contractions always. \
Short sentences mixed with one longer rant sentence. One concrete detail from the \
article (a number, a quote, a gotcha) — used as the SPARK, not turned into a war \
story, and not a summary."""


class PostGenerator:
    """Run the senior-dev loop. Not a single fluff-strip."""

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._article: CandidatePost | None = None

    def compose(self, posts: list[CandidatePost]) -> str:
        """Pass 2 → 1 → 3 → 4. Returns draft with TOPIC line still on top."""
        article = pick_article(posts)
        self._article = article
        facts = key_facts(article)
        print(f"Loop: locked article -> {article.title}")
        if facts:
            print("Loop: key facts (not full article):")
            for fact in facts:
                print(f"  - {fact}")
        else:
            print("Loop: no summary facts — title only")

        tone_key = classify_tone(article.title, facts)
        state = LoopState.load()
        opener_style = state.next_style()
        print(f"Pass 4 — opener style: {opener_style}")

        draft = self._pass1(article, facts, tone_key, opener_style)
        draft = self._pass3(draft)

        if state.clashes(draft):
            avoid = state.avoid_instruction(draft)
            print(f"Pass 4 — re-roll Pass 1 ({avoid})")
            alt_index = (len(state.openers) + 1) % len(OPENER_STYLES)
            next_style = OPENER_STYLES[alt_index]
            draft = self._pass1(
                article,
                facts,
                tone_key,
                f"{next_style}. {avoid}",
            )
            draft = self._pass3(draft)

        return draft

    def _pass1(
        self,
        article: CandidatePost,
        facts: list[str],
        tone_key: str,
        opener_style: str,
    ) -> str:
        print("Pass 1 — draft (persona lock)")
        fact_block = "\n".join(f"- {f}" for f in facts) if facts else "- (none — do not invent facts)"
        user = f"""TONE: {tone_label(tone_key)}

Article title (you did not write this, you did not ship it):
{article.title}

Key facts — steal ONE concrete detail as the SPARK. Do not summarise the list:
{fact_block}

OPENER: {opener_style}

Write a LinkedIn post as that senior engineer.
First line exactly: TOPIC: {article.title}
Then the post. Last line exactly: {REQUIRED_HASHTAGS}
Stay under {MAX_POST_WORDS - 40} words so the gate does not kill it.

Contract — read carefully:
- You DID NOT use, build, ship, migrate to, deploy, or implement the thing in this article. You only READ it today.
- The article is the SPARK. Your post is YOUR take from YOUR career — separate from the article's subject.
- Allowed: "this reminded me of X from years ago", "this kind of thing bit us once on a different stack", "I keep seeing this pattern", "in my experience, the bigger issue is...".
- Forbidden when the object refers to the article's subject: "I shipped this", "I tried this and", "we migrated to this", "my team built this", "I deployed this", "we built this".
- One concrete detail from the article (number / quote / gotcha) is the SPARK in line 1-2, then pivot to your view. Do not turn the article detail into a war story.
- No marketing. No 'my network'. No 'thoughts?' at the end.
- If you mention a date, write it like "28 July 2026" — never ISO (2026-07-28).
"""
        result = self._llm.complete(
            messages=[
                {"role": "system", "content": _PERSONA},
                {"role": "user", "content": user},
            ],
            temperature=0.82,
            max_tokens=500,
        )
        if not result:
            raise Exception("Pass 1: Groq failed")
        return strip_think_blocks(result)

    def _pass3(self, draft: str) -> str:
        print("Pass 3 — self-critique (rewrite cliché lines only)")
        reject = ", ".join(f'"{t}"' for t in PASS3_REJECT)
        prompt = f"""Read this draft. Flag any line that sounds like marketing copy, LinkedIn-guru \
cliché, or something no real engineer would say out loud. Rewrite only those \
lines. Keep everything else untouched. Output ONLY the final post.

Also kill any of these if they appear: {reject}
More than 3 hashtags is too many — keep only this exact last line: {REQUIRED_HASHTAGS}
Preserve the TOPIC: line at the top if present.
If a date appears, use spoken form like "28 July 2026", not ISO.

CRITICAL: flag any sentence that puts the author inside the article's story — \
e.g. "I shipped this", "we migrated to this", "I tried this and got burned", "my \
team built this", "I deployed this", "we built this", "I implemented this". These \
are forbidden when the object refers to the article's subject. The author only \
READ the article today. Rewrite as a take, a separate-life parallel ("this reminds \
me of X from a job years ago"), or cut the sentence. Do not water down the post \
to do this — find a different way to land the point.

DRAFT:
{draft}
"""
        result = self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=500,
        )
        if not result:
            print("Pass 3: Groq failed — keeping Pass 1 draft")
            return draft
        cleaned = strip_think_blocks(result)
        if len(cleaned.split()) < len(draft.split()) * 0.5:
            print("Pass 3: rewrite too short — keeping Pass 1 draft")
            return draft
        leftover = reject_hits(cleaned)
        if leftover:
            print(f"Pass 3: reject-list still present: {leftover}")
        return cleaned
