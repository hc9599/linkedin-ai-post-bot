"""
Multi-pass generation loop.

Pass 2 classifies tone. Pass 1 drafts. Pass 3 rewrites only cliché lines.
Pass 4 re-rolls the opener if it clones the last few posts.
Pass 5 lives in review.py.
"""
from datetime import datetime

from linkedin_bot.cleaning import strip_think_blocks
from linkedin_bot.discovery import Focus
from linkedin_bot.generation.facts import key_facts, pick_article
from linkedin_bot.generation.reject import reject_hits
from linkedin_bot.generation.style import (
    ENGAGEMENT_BAIT_REJECT,
    MAX_POST_WORDS,
    OPENER_STYLES,
    PASS3_REJECT,
)
from linkedin_bot.generation.tone import classify_tone, tone_label
from linkedin_bot.generation.variance import LoopState
from linkedin_bot.llm import LLMClient
from linkedin_bot.models import CandidatePost
from linkedin_bot.niche import NicheProfile, WeekdayAngle, active_closers, allows_code_snippet


class PostGenerator:
    """Run the senior-dev loop. Not a single fluff-strip."""

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._article: CandidatePost | None = None

    def compose(
        self,
        posts: list[CandidatePost],
        profile: NicheProfile,
        focus: Focus,
    ) -> str:
        """Pass 2 → 1 → 3 → 4. Returns draft with TOPIC line still on top."""
        article = pick_article(posts, profile, focus)
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
        closer_style = state.next_closer(active_closers(profile))
        print(f"Pass 4 — opener style: {opener_style}")
        closer_preview = (
            closer_style if len(closer_style) <= 80 else closer_style[:80] + "..."
        )
        print(f"Pass 4 — engagement closer: {closer_preview}")

        draft = self._pass1(
            article, facts, tone_key, opener_style, closer_style, profile, focus
        )
        draft = self._pass3(draft, profile)

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
                closer_style,
                profile,
                focus,
            )
            draft = self._pass3(draft, profile)

        return draft

    def _weekday_angle(self, profile: NicheProfile) -> WeekdayAngle | None:
        return profile.weekday_angles.get(datetime.now().weekday())

    def _pass1_audience_block(self, profile: NicheProfile) -> tuple[str, str, str]:
        """Return (audience_line, code_block, engagement_rules) for Pass 1."""
        engagement = profile.engagement
        audience = profile.audience

        if audience.mode == "peers":
            code_block = ""
            if allows_code_snippet(profile):
                code_block = (
                    f"\n- Optional: include 1-3 lines of {profile.code_language} code if it clarifies a tradeoff.\n"
                    "- Snippet must be illustrative only — do not invent APIs not hinted in title/facts.\n"
                    "- Put blank lines before and after any code block.\n"
                )
            audience_line = (
                "- Write for developer peers who already know the stack — not a general audience."
            )
            engagement_rules = (
                "Engagement rules:\n"
                "- The line immediately before the hashtags MUST be a specific developer question or A/B choice tied to the article spark.\n"
                "- Forbidden closers: thoughts?, agree?, let me know, share your thoughts, drop a comment, what do you think?\n"
                "- Do not ask 'my network'. Invite a reply a senior dev would actually type."
            )
            return audience_line, code_block, engagement_rules

        lead_map = {
            "impact": "why a team, hire, or project should care",
            "story": "a brief career-adjacent hook, then the point",
            "takeaway": "the plain-language takeaway upfront",
        }
        lead_hint = lead_map.get(audience.lead_with, lead_map["impact"])
        jargon_hint = (
            "Use minimal jargon — prefer plain business language."
            if audience.jargon_policy == "minimal_jargon"
            else "Every technical term or acronym MUST be glossed inline on first use (5-10 plain words)."
        )
        audience_line = (
            "- AUDIENCE: mixed LinkedIn feed — developers, hiring managers, tech-curious readers.\n"
            f"- Lead with {lead_hint} before technical detail.\n"
            f"- {jargon_hint}\n"
            "- Max one dense technical concept per paragraph.\n"
            "- NO code blocks. Do not assume the reader knows C# or .NET."
        )
        engagement_rules = (
            "Engagement rules:\n"
            "- The line immediately before the hashtags MUST be a specific question about team, hiring, delivery, or business tradeoff — tied to the article spark.\n"
            "- Forbidden closers: thoughts?, agree?, let me know, share your thoughts, drop a comment, what do you think?\n"
            "- Forbidden dev-only closers: 'in your codebase', syntax A/B choices, 'anyone else still on X' unless X is explained in plain English.\n"
            "- Do not ask 'my network'. Invite a reply a hiring manager or lead could answer in one line."
        )
        return audience_line, "", engagement_rules

    def _pass3_accessibility_block(self, profile: NicheProfile) -> str:
        if profile.audience.mode == "peers":
            return (
                "Engagement: the line immediately before the hashtags MUST be a SPECIFIC developer "
                "question or A/B choice tied to the post topic — not generic bait like \"thoughts?\" "
                "or \"agree?\". If the closer is vague, rewrite only that line."
            )
        return (
            "Accessibility pass (mixed audience):\n"
            "- Rewrite unexplained jargon or acronyms — add a brief plain-English gloss or simplify.\n"
            "- Rewrite dev-only closers ('in your codebase', syntax A/B) to team or business framing.\n"
            "- Keep senior-engineer voice — do not become corporate marketing.\n"
            "Engagement: the line immediately before the hashtags MUST be a SPECIFIC team, hiring, or "
            "delivery question — not generic bait. If the closer is vague or dev-only, rewrite only that line."
        )

    def _pass1(
        self,
        article: CandidatePost,
        facts: list[str],
        tone_key: str,
        opener_style: str,
        closer_style: str,
        profile: NicheProfile,
        focus: Focus,
    ) -> str:
        print("Pass 1 — draft (persona lock)")
        fact_block = "\n".join(f"- {f}" for f in facts) if facts else "- (none — do not invent facts)"
        weekday = self._weekday_angle(profile)
        weekday_block = ""
        if weekday:
            weekday_block = (
                f"\nWEEKDAY ANGLE:\n"
                f"- Focus: {weekday.focus}\n"
                f"- Audience: {weekday.audience_signal}\n"
                f"- Avoid: {weekday.avoid}\n"
            )
        engagement = profile.engagement
        audience_line, code_block, engagement_rules = self._pass1_audience_block(profile)
        hashtags_line = profile.required_hashtags_line
        user = f"""TONE: {tone_label(tone_key)}

FOCUS TOPIC: {focus.topic}
NICHE ANGLE: {focus.angle}
{weekday_block}
Article title (you did not write this, you did not ship it):
{article.title}

Key facts — steal ONE concrete detail as the SPARK. Do not summarise the list:
{fact_block}

OPENER: {opener_style}

ENGAGEMENT CLOSER: {closer_style}

Formatting:
- Max {engagement.max_sentences_per_paragraph} sentences per paragraph, then a blank line.
{audience_line}
{code_block}
{engagement_rules}

Write a LinkedIn post as that senior engineer.
First line exactly: TOPIC: {article.title}
Then the post. Last line exactly: {hashtags_line}
Stay under {MAX_POST_WORDS - 40} words so the gate does not kill it.

Contract — read carefully:
- You DID NOT use, build, ship, migrate to, deploy, or implement the thing in this article. You only READ it today.
- The article is the SPARK. Your post is YOUR take from YOUR career — separate from the article's subject.
- Allowed: "this reminded me of X from years ago", "this kind of thing bit us once on a different stack", "I keep seeing this pattern", "in my experience, the bigger issue is...".
- Forbidden when the object refers to the article's subject: "I shipped this", "I tried this and", "we migrated to this", "my team built this", "I deployed this", "we built this".
- One concrete detail from the article (number / quote / gotcha) is the SPARK in line 1-2, then pivot to your view. Do not turn the article detail into a war story.
- No marketing. No 'my network'.
- If you mention a date, write it like "28 July 2026" — never ISO (2026-07-28).
"""
        result = self._llm.complete(
            messages=[
                {"role": "system", "content": profile.persona},
                {"role": "user", "content": user},
            ],
            temperature=0.82,
            max_tokens=500,
        )
        if not result:
            raise Exception("Pass 1: LLM call failed")
        return strip_think_blocks(result)

    def _pass3(self, draft: str, profile: NicheProfile) -> str:
        print("Pass 3 — self-critique (rewrite cliché lines only)")
        combined_reject = list(dict.fromkeys(PASS3_REJECT + ENGAGEMENT_BAIT_REJECT))
        reject = ", ".join(f'"{t}"' for t in combined_reject)
        hashtags_line = profile.required_hashtags_line
        accessibility_block = self._pass3_accessibility_block(profile)
        prompt = f"""Read this draft. Flag any line that sounds like marketing copy, LinkedIn-guru \
cliché, or something no real engineer would say out loud. Rewrite only those \
lines. Keep everything else untouched. Output ONLY the final post.

Also kill any of these if they appear: {reject}
More than 3 hashtags is too many — keep only this exact last line: {hashtags_line}
Preserve the TOPIC: line at the top if present.
If a date appears, use spoken form like "28 July 2026", not ISO.

{accessibility_block}

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
            print("Pass 3: LLM call failed — keeping Pass 1 draft")
            return draft
        cleaned = strip_think_blocks(result)
        if len(cleaned.split()) < len(draft.split()) * 0.5:
            print("Pass 3: rewrite too short — keeping Pass 1 draft")
            return draft
        leftover = reject_hits(cleaned)
        if leftover:
            print(f"Pass 3: reject-list still present: {leftover}")
        return cleaned
