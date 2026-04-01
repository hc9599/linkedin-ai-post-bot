import requests
import os
import random
import time
import re
from datetime import datetime


# ---------------------------------------------------------------
# TOPIC ANGLES: rotate daily across different .NET/C# dimensions
# ---------------------------------------------------------------
TOPIC_ANGLES = {
    0: {  # Monday — language & runtime
        "focus": (
            "Focus on C# language features or .NET runtime improvements — new syntax, "
            "type system changes, performance characteristics, or how the language is evolving. "
            "Explain what the change means in practice, not just what it is."
        ),
        "audience_signal": (
            "Recruiting managers should come away thinking: this person understands the platform "
            "deeply and keeps up with where it is going. Developers should feel like a peer is "
            "sharing something genuinely useful."
        ),
        "avoid": "Do not reduce it to a feature announcement. Connect it to real decisions a developer makes.",
    },
    1: {  # Tuesday — tooling & developer experience
        "focus": (
            "Focus on developer tooling, IDE improvements, SDK changes, debugging experience, "
            "NuGet, or build systems. Describe the practical impact on daily development work."
        ),
        "audience_signal": (
            "Recruiting managers should see evidence of someone who cares about engineering craft "
            "and productivity, not just shipping. Developers should find something they can actually "
            "use or think about today."
        ),
        "avoid": (
            "Do not make it sound like a product review. Frame it around what changes in your "
            "workflow and why that matters."
        ),
    },
    2: {  # Wednesday — architecture & engineering decisions
        "focus": (
            "Focus on software architecture, design patterns, or engineering tradeoffs in .NET — "
            "async patterns, dependency injection, modular design, scalability decisions, or how "
            "to structure systems that are built to last."
        ),
        "audience_signal": (
            "Recruiting managers should see a developer who thinks beyond features — someone who "
            "reasons about systems and tradeoffs. Developers should find a concrete angle they "
            "can apply or debate."
        ),
        "avoid": "No vague architecture talk. Name a specific pattern, tradeoff, or decision point.",
    },
    3: {  # Thursday — C# positioning & career perspective
        "focus": (
            "Focus on where C# and .NET stand in the broader software industry — how it compares "
            "to other languages, why developers choose it, what the community is doing, or what "
            "makes it a strong platform choice for serious backend work in the current market."
        ),
        "audience_signal": (
            "Recruiting managers should see someone who understands the market and can articulate "
            "why their stack matters. Developers should find a perspective they can agree or "
            "disagree with — something worth discussing."
        ),
        "avoid": (
            "Do not write a generic 'C# is great' post. Take a position on something specific — "
            "adoption, community, competition, or direction."
        ),
    },
    4: {  # Friday — enterprise & infrastructure
        "focus": (
            "Focus on enterprise-scale .NET concerns — cloud infrastructure, data pipelines, "
            "file system integrations, security and permissions, compliance, or building systems "
            "that handle large volumes reliably. Be specific about what breaks at scale."
        ),
        "audience_signal": (
            "Recruiting managers should see someone with genuine enterprise experience, not someone "
            "who has only built tutorials. Developers working at scale should recognise the problem "
            "being described."
        ),
        "avoid": (
            "Do not reference NAS, SMB, or internal product details. Keep it generalisable to any "
            "senior .NET developer working on backend infrastructure."
        ),
    },
    5: {  # Saturday — performance & internals
        "focus": (
            "Focus on .NET performance — Span<T>, memory management, GC behaviour, benchmarking, "
            "JIT compilation, or low-level runtime details. Explain why it matters and what a "
            "developer should actually do with the information."
        ),
        "audience_signal": (
            "Recruiting managers should see someone who cares about performance at a level most "
            "developers do not. Developers should learn something concrete or be challenged to "
            "think about performance differently."
        ),
        "avoid": (
            "Do not just name a concept. Show the implication — what goes wrong without it, "
            "or what gets better with it."
        ),
    },
    6: {  # Sunday — new releases & future direction
        "focus": (
            "Focus on what is new or coming in .NET — release previews, the C# roadmap, upcoming "
            "features, or the direction the platform is heading. Evaluate what the changes actually "
            "mean for developers, not just what they are."
        ),
        "audience_signal": (
            "Recruiting managers should see someone who stays current and thinks critically about "
            "platform direction, not just someone who reads release notes. Developers should get "
            "a useful filter on what to pay attention to."
        ),
        "avoid": (
            "Do not write a changelog summary. Evaluate, filter, or push back on what is worth "
            "caring about."
        ),
    },
}

# ---------------------------------------------------------------
# BANNED PHRASES — lexical-level enforcement
# ---------------------------------------------------------------
BANNED_PHRASES = [
    "production taught me", "something I keep coming back to",
    "a pattern I've seen break teams", "we've all been there",
    "after years of", "hard-won", "battle-tested",
    "I just learned", "I recently discovered", "building my first",
    "I was surprised to find", "it's all about", "straightforward",
    "seamless", "dive into", "delve into", "I stumbled upon",
    "robust", "game-changer", "the key to", "the importance of",
    "in today's world", "in the world of", "navigating",
    "ever-evolving", "tech landscape", "as developers", "as a developer",
    "let that sink in", "food for thought", "it's worth noting",
    "at the end of the day", "take it to the next level",
    "I'm excited about", "I'm looking forward to",
    "I recall a particular", "I remember when",
    "highlighting the need for", "I'm thrilled", "noteworthy",
    "worth exploring", "it's a great time to", "can't wait to",
    "this is a must", "ultimate guide", "reduce repetitive",
    "exploring how", "looking forward to trying",
    "could have saved us", "hit a snag",
    "good reminder", "top of mind", "proactive approach",
    "always top of mind", "taking a proactive",
    "warrant a closer look", "without a second thought",
    "should always be", "most critical aspect",
    "cannot be overstated", "goes without saying",
    "in conclusion", "to summarise", "as we know",
    "underscores the severity", "demonstrates the platform",
    "highlights the importance", "data-driven approach",
    "valuable insights", "promising solution",
    "attention to detail", "ultimately benefiting",
]

# ---------------------------------------------------------------
# BANNED OPENERS — structural-level enforcement
# These patterns produce the bland, generic first sentences
# that make the posts feel like AI summaries, not human takes.
# ---------------------------------------------------------------
BANNED_OPENERS = [
    "Most teams...",
    "Most developers...",
    "Have you ever wondered...",
    "When working with X, have you ever...",
    "One of the most significant challenges is...",
    "The use of X can significantly...",
    "The integration of X is...",
    "The recent release of X...",
    "X is becoming increasingly...",
    "Any opener that reads like the first line of a Wikipedia article",
    "Any opener that makes a generic observation applying to all software development",
]

# ---------------------------------------------------------------
# OPENERS — positive instructions for the first sentence
# ---------------------------------------------------------------
OPENERS = [
    (
        "Open with a clear, direct statement of what the topic is and why it matters — no jargon "
        "without explanation, but do not oversimplify. A recruiting manager should understand the "
        "stakes; a developer should respect the framing."
    ),
    (
        "Open with a contrast: what the default behaviour or assumption is, versus what the "
        "evidence or experience suggests is better. Name the default specifically — not just 'most people'."
    ),
    (
        "Open with a direct, confident observation about a real tradeoff or tension in the topic. "
        "State your position clearly in the first sentence. Do not hedge."
    ),
    (
        "Open by naming a specific behaviour, pattern, or change — then in the next sentence, "
        "explain what makes it significant. Do not assume the reader already knows why it matters."
    ),
    (
        "Open with a short scenario (2 sentences max) that sets up the problem. "
        "It should be recognisable to developers and understandable to anyone who has worked with software teams."
    ),
]

# ---------------------------------------------------------------
# ENDINGS — how to close the post
# ---------------------------------------------------------------
ENDINGS = [
    (
        "End with a single genuine question that invites both developers and non-developers to share "
        "a perspective. Not rhetorical — actually curious about how others have dealt with this."
    ),
    (
        "End with your clearest takeaway in one sentence. State it plainly so a non-developer "
        "can repeat it to someone else and have it still make sense."
    ),
    (
        "End with a concrete action or check — one specific thing a developer can do, "
        "explained clearly enough that a manager understands why it is worth doing."
    ),
    (
        "End by connecting the technical point to a broader engineering or team dynamic — "
        "one sentence that shows you think about the human side of the work, not just the code."
    ),
    (
        "End with an honest, grounded observation about how common it is to get this wrong, "
        "or how long it takes most teams to notice the problem."
    ),
]

# ---------------------------------------------------------------
# FORMATS — post structure
# ---------------------------------------------------------------
FORMATS = [
    (
        "Two paragraphs. First paragraph (2-3 sentences): explain the context or problem clearly "
        "enough that a non-developer can follow it. Second paragraph (3-4 sentences): give your "
        "specific take, name what is interesting or underappreciated about it, and explain the "
        "practical implication. Every sentence ends with a full stop."
    ),
    (
        "Three short paragraphs, 2-3 sentences each. "
        "First: set up the situation or problem. "
        "Second: explain what most people miss or get wrong about it. "
        "Third: your specific take and what it means in practice. "
        "Every sentence ends with a full stop. No bullet points."
    ),
    (
        "One flowing paragraph of 6-8 sentences. Open with the context, move to the technical "
        "detail, explain why it matters to someone building real systems, and close with a clear "
        "point. Write so a smart non-developer can follow the logic even if they miss the "
        "technical details."
    ),
    (
        "Short lines, one sentence each, building toward a conclusion. "
        "Start with the broad context (1-2 lines), move to the specific technical point (2-3 lines), "
        "then explain the implication clearly (2 lines). "
        "Every line is a complete sentence. Full stops throughout. No fragments. No dashes as sentence starters."
    ),
]

# ---------------------------------------------------------------
# WORD COUNTS
# ---------------------------------------------------------------
WORD_COUNTS = [
    "between 130 and 160 words — enough to explain the context and make a clear point",
    "between 150 and 180 words — room for a specific example or concrete detail that grounds the insight",
    "between 160 and 200 words — use the space to build a proper argument: context, insight, implication",
    "between 120 and 150 words — tight and descriptive: every sentence should add something a reader could not infer themselves",
]


def _call_groq(messages: list, temperature: float = 0.85, max_tokens: int = 600) -> str | None:
    """
    Single reusable Groq call. Returns the text content or None on failure.
    Retries up to 3 times with exponential backoff.
    """
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    for attempt in range(3):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen/qwen3-32b",       # Better voice fidelity than llama-3.3-70b
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": 0.92,
                    "frequency_penalty": 0.5,
                    "presence_penalty": 0.4,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()

            print(f"Groq attempt {attempt + 1} failed: {response.status_code} — {response.text}")
        except Exception as e:
            print(f"Groq attempt {attempt + 1} exception: {e}")

        time.sleep(2 ** attempt)

    return None


def generate_linkedin_post(posts: list) -> str:
    """
    First-pass post generation.
    Picks one article, applies the daily angle, and writes a draft post.
    """
    today = datetime.now().strftime("%A, %B %d")
    weekday = datetime.now().weekday()

    posts_text = "\n\n".join([
        f"[{p['source']}] {p['title']} ({p['reactions']} upvotes)\n{p['summary']}"
        for p in posts
    ])

    angle = TOPIC_ANGLES[weekday]

    # Pick one variant from each category BEFORE building the prompt.
    # Presenting a menu of options invites the model to blend them into mush.
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

NO REPETITION: Each sentence must add something new. Do not restate the same point in different words. \
If you catch yourself making the same point twice, cut the second instance entirely.

NO INVENTED ANECDOTES: Do not write "I recall when..." or fabricated scenarios.
NO EMOJIS. NO MARKDOWN. NO SMILEY FACES.

WORD COUNT: {chosen_word_count}

HASHTAGS: On their own line at the very end, exactly: #CSharp #DotNet #Programming #SoftwareDevelopment

BANNED PHRASES — do not use any of these:
{banned_phrases_str}
"""

    result = _call_groq(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.90,
        max_tokens=700,
    )

    if not result:
        raise Exception("generate_linkedin_post: all Groq attempts failed")

    return result


def critique_and_rewrite(draft: str) -> str:
    """
    Second-pass self-critique and rewrite.
    Checks the draft against the five most common failure modes and rewrites
    only what needs fixing. Lower temperature for more disciplined output.
    """
    critique_prompt = f"""You are editing a LinkedIn post draft for a senior C#/.NET developer. \
Your job is to check it against the five failure modes below and rewrite only what fails. \
If a section passes, keep it exactly as written.

DRAFT:
{draft}

---

CHECK THESE FIVE FAILURE MODES IN ORDER:

1. OPENER — Does it open with a generic observation like "Most teams...", "Have you ever wondered...", \
or "One of the most significant challenges is..."? If yes, rewrite the opener to open with a \
specific behaviour, a direct position, or a named tradeoff. Do not start with a generalisation.

2. REPETITION — Does any point appear more than once in different words? If yes, cut the second \
instance entirely. Every sentence must add something new.

3. FILLER PHRASES — Does it contain any of these: "this is a good reminder", "it's worth noting", \
"the importance of", "cannot be overstated", "highlights the importance", "valuable insights", \
"data-driven approach", "demonstrates the platform", "underscores the severity"? \
If yes, replace with a concrete statement or cut entirely.

4. ARTICLE SUMMARY TEST — Could this post have been written from the article title alone, \
without reading the summary? If yes, rewrite to anchor on one specific technical detail \
or concrete fact from the content that only someone who read the summary would know.

5. POINT OF VIEW — Is there a clear, stated position or take — not just description? \
If not, add one sentence that states what the author actually thinks about this.

---

Output the rewritten post only.
No preamble. No explanation. No "Here is the rewritten post:".
Preserve the TOPIC: line at the top if present.
Preserve the hashtag line at the bottom exactly as written.
"""

    result = _call_groq(
        messages=[{"role": "user", "content": critique_prompt}],
        temperature=0.40,   # Low temp: disciplined editing, not creative rewriting
        max_tokens=700,
    )

    if not result:
        print("critique_and_rewrite: Groq failed — returning original draft")
        return draft

    return result


def strip_topic_line(text: str) -> str:
    """
    Removes the 'TOPIC: ...' debug line the model outputs at the top.
    Kept separate from clean_markdown so it runs after critique pass.
    """
    return re.sub(r'^TOPIC:.*\n?', '', text, flags=re.IGNORECASE).strip()
