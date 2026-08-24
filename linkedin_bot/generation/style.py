# ---------------------------------------------------------------
# Writing style for the AI.
# These are not code — they are instructions mixed into the prompt.
# Each weekday gets a different angle so Monday does not sound like Friday.
# ---------------------------------------------------------------
TOPIC_ANGLES = {
    0: {  # Monday — language & runtime
        "focus": (
            "Focus on a C# language feature or .NET runtime change — syntax, types, "
            "performance, or how the language is moving. Talk about what you would actually "
            "do differently in code, not a feature recap."
        ),
        "audience_signal": (
            "C# peer first. One short gloss for jargon. Do not write a beginner lesson."
        ),
        "avoid": (
            "Do not recap the article. React: what you would try, skip, or argue with. "
            "Land it through a trending topic or daily-life analogy."
        ),
    },
    1: {  # Tuesday — tooling & developer experience
        "focus": (
            "Focus on tooling — IDE, SDK, debugger, NuGet, MSBuild. What changes in the "
            "afternoon you already work, not a product tour."
        ),
        "audience_signal": (
            "Sound like you tried the tool, or you know why you still will not. "
            "Say what the tool does in one plain clause before the take."
        ),
        "avoid": (
            "Do not write a product review or a feature walkthrough. Your workflow take only. "
            "Land it through a trending topic or daily-life analogy."
        ),
    },
    2: {  # Wednesday — architecture & engineering decisions
        "focus": (
            "Focus on a .NET architecture tradeoff — async, DI, module boundaries, how the "
            "system is shaped. Name the tension."
        ),
        "audience_signal": (
            "Another senior should want to agree or argue. Name the tradeoff in plain words, "
            "not architecture slang alone."
        ),
        "avoid": (
            "No architecture poetry. No blog rewrite. One named tension and your side of it. "
            "Land it through a trending topic or daily-life analogy."
        ),
    },
    3: {  # Thursday — C# positioning & career perspective
        "focus": (
            "Focus on where C# / .NET sits this year — compared to other stacks, hiring, "
            "community, or why you still pick it for backend work."
        ),
        "audience_signal": (
            "A take someone can disagree with. No cheerleading. No insider-only slang."
        ),
        "avoid": (
            "Do not summarise the piece. Take a side on adoption, competition, or direction. "
            "Land it through a trending topic or daily-life analogy."
        ),
    },
    4: {  # Friday — enterprise & infrastructure
        "focus": (
            "Focus on enterprise .NET — cloud, data, security, pipelines, what actually "
            "breaks when the system is large. Be specific about the failure mode."
        ),
        "audience_signal": (
            "Someone who has been paged should nod. One gloss if the failure has a jargon name."
        ),
        "avoid": (
            "Do not reference NAS, SMB, or internal product details. Do not paste the article. "
            "Keep it any senior .NET backend person could own. "
            "Land it through a trending topic or daily-life analogy."
        ),
    },
    5: {  # Saturday — performance & internals
        "focus": (
            "Focus on .NET performance — Span<T>, GC, benchmarks, JIT. What you would "
            "measure or change, not a concept name-drop."
        ),
        "audience_signal": (
            "Show what gets slow or fat, in plain words. Do not only name Span or GC."
        ),
        "avoid": (
            "Do not lecture the concept from the article. Say what you would measure or change. "
            "Land it through a trending topic or daily-life analogy."
        ),
    },
    6: {  # Sunday — new releases & future direction
        "focus": (
            "Focus on what is new or coming in .NET. Filter it: what you would try, skip, "
            "or wait on. Not a changelog."
        ),
        "audience_signal": (
            "A useful opinion on what to try or skip. Explain the change like you would at lunch."
        ),
        "avoid": (
            "Do not write a changelog. Filter it: try, skip, or wait - and why. "
            "Land it through a trending topic or daily-life analogy."
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
    "seamless", "seamlessly", "dive into", "delve into", "I stumbled upon",
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
    "in conclusion", "to summarise", "to summarize", "as we know",
    "underscores the severity", "demonstrates the platform",
    "highlights the importance", "data-driven approach",
    "valuable insights", "promising solution",
    "attention to detail", "ultimately benefiting",
    "becoming a crucial component", "adaptability to emerging technologies",
    "higher-level tasks", "real-time feedback", "repetitive tasks",
    "work smarter, not harder",
    "silver bullet",
    "thoughtful integration",
    "maximize value",
    "without compromising",
    "team ownership",
    "AI isn't a",
    "AI is not a",
    "worth evaluating",
    "reduce friction",
    "real-world complexity",
    "without requiring a complete overhaul",
    "new layer of support",
    "not just automation",
    "context switching between languages",
    # LinkedIn-GPT tells
    "in practice",
    "the result is",
    "missed opportunities",
    "injects AI",
    "debugging loop",
    "black box",
    "black boxes",
    "large-scale pipelines",
    "reliable and compliant",
    "guided investigation",
    "incident resolution",
    "what are your thoughts",
    "curious to hear",
    "let's unpack",
    "let's dive",
    "here's the thing",
    "here's why",
    "the reality is",
    "the truth is",
    "make no mistake",
    "at its core",
    "when it comes to",
    "plays a crucial role",
    "it is important to",
    "not only",
    "but also",
    "leverage",
    "unlock",
    "empower",
    "cutting-edge",
    "revolutionary",
    "furthermore",
    "moreover",
    "additionally",
    "it's not just",
    "more than just",
    "that's exactly how",
    "in an era",
    "landscape",
    "tapestry",
    "plethora",
    "utilize",
    "facilitate",
    "holistic",
    "paradigm",
    "synergy",
    "pivotal",
    "testament",
    "foster",
    "harness",
    "realm of",
    "delve",
    "underscore",
    "underscores",
    "showcasing",
    "showcases",
    "deep dive",
    "game changer",
    "transform your",
    "elevate",
    "supercharge",
    "thought leadership",
    "let that sink",
    "drop a comment",
    "hit like if",
    "agree?",
    "I came across",
    "I recently read",
    "sharing this",
    "interesting article",
    "allows you to",
    "enables you to",
    "enables developers",
    "you can now",
    "as an Indian developer",
    "in the Indian context",
    "in the current climate",
    "in today's climate",
    "my new recipe",
    "my recipe",
    "pro tip",
    "here's how I",
    "the fix is simple",
    "silently hijack",
    "phantom package",
    "I've been pinning",
    "I've been doing this for",
    "for a while, but",
    "need an upgrade?",
    "my go-to",
    "hot take:",
    "unpopular opinion:",
    "vibe:",
    "downstream consumers",
    "contract test",
    "verify the shape",
    "parsing scripts",
    "I'm adding a",
    "I'll flip the switch",
    "I'm flipping the switch",
    "I'll add a quick",
    "I'll copy the",
    "I'll give it a shot in our",
    "deterministic failure",
    "guard test",
    "one dry aside",
    "on the menu",
    "10 am",
    "10am",
    "9 am",
    "9am",
    "before 10",
]

# ---------------------------------------------------------------
# BANNED OPENERS — structural-level enforcement
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
    "In today's...",
    "In an era...",
    "It's no secret...",
    "Let's be honest...",
    "Here's the thing...",
    "Imagine this...",
    "Picture this...",
    "Enterprise .NET / In the world of...",
    "I came across an article...",
    "I just read about...",
    "Sharing this with my network...",
    "Any opener that reads like the first line of a Wikipedia article",
    "Any opener that defines a problem for 'the industry' instead of a thing you actually touch",
    "Any opener that makes a generic observation applying to all software development",
    "Any opener that starts explaining the article's product as if you shipped it",
    "Standup / inbox / Slack / badge / calendar / fire drill as the first line",
    "As an Indian developer...",
    "In the Indian context...",
    "In today's climate...",
    "X vibe: ...",
    "My new recipe: ...",
    "Hot take: ...",
    "Unpopular opinion: ...",
]

# ---------------------------------------------------------------
# OPENERS — positive instructions for the first sentence
# ---------------------------------------------------------------
OPENERS = [
    (
        "Open on today's weekday life vibe (Monday leftover takeout, Friday dinner plans) "
        "or a headline. Then land the .NET take. Phone-in-pocket energy, not a whitepaper. "
        "Only name today's weekday. No office openers."
    ),
    (
        "Open with a headline jab ONLY if the analogy is obvious. Otherwise a routine. "
        "Two sentences max for the hook. Then your view. No 'most teams'."
    ),
    (
        "Open mid-thought on daily life: 'Unread group chat energy.' Then name the tool "
        "(MSBuild, binlogs, Convert.ChangeType) and your take."
    ),
    (
        "Open with what you would try or skip, tied to a daily annoyance or a news beat. "
        "Do not explain the article's feature list."
    ),
    (
        "Open with a hook a .NET person would smirk at "
        "(power flicker at 99%, muted match tab, today's weekday if it fits). Then the actual take."
    ),
]

# ---------------------------------------------------------------
# ENDINGS — how to close the post
# ---------------------------------------------------------------
ENDINGS = [
    (
        "End with a specific conversation starter "
        "('Anyone else's CI still feel like today's weekday roulette?'). "
        "No 'what are your thoughts?' No 'curious to hear'."
    ),
    (
        "End with what YOU will do next (try it, ignore it, wait for GA). "
        "Do not recap the product again."
    ),
    (
        "End with one blunt take of yours. No moral. No 'this matters because teams'."
    ),
    (
        "End with a small doubt ('not magic', 'still have to read the task output'). "
        "Humans hedge. Do not write a TED closer."
    ),
    (
        "If humor is on, end on a dry line. If humor is off, stop after the take."
    ),
]

# ---------------------------------------------------------------
# FORMATS — post structure
# ---------------------------------------------------------------
FORMATS = [
    (
        "Looks like a chat, not a blog. 3 or 4 short paragraphs, 1-2 sentences each, "
        "blank line between. Trending or daily-life hook first. At most ONE sentence "
        "restates a fact from the article. The rest is your view."
    ),
    (
        "Hook line (headline jab or daily-life scene, own paragraph). One sentence of spark "
        "from the article. Then your argument. Then a one-line conversation starter. "
        "No wall of text."
    ),
    (
        "Four to seven short lines. Mix a 4-word line with a longer one. Line breaks "
        "like a human on LinkedIn. Do not walk through the article. No bullets."
    ),
    (
        "Two short paragraphs only. First: the trending or daily-life situation. "
        "Second: how that article fits - try / skip / argue - in your words. "
        "Uneven sentence length."
    ),
]

WORD_COUNTS = [
    "between 55 and 80 words - casual. A phone post, not a how-to",
    "between 60 and 90 words - room for one concrete detail, then stop",
    "between 50 and 75 words - tight. Cut anything a coworker already knows",
    "between 65 and 95 words - still a chat. If it reads like a recipe, cut it",
]

# How funny today. Weighted at pick time so it is not always a bit.
WIT_MODES = [
    {
        "name": "straight",
        "instruction": (
            "No jokes today. Still human. Sharp opinion. Do not pad with corporate warmth."
        ),
    },
    {
        "name": "dry",
        "instruction": (
            "One muttered aside. Not a punchline hunt. Then back to the take. "
            "Do not write the words 'dry aside'."
        ),
    },
    {
        "name": "witty",
        "instruction": (
            "Be funny enough that a C# person stops scrolling. "
            "One hook with bite (unread match chat, power flicker at 99%, "
            "Copilot narrating XML, today's weekday only if it is actually today). "
            "Then a real viewpoint. "
            "Not cringe LinkedIn. Not 'who's with me'. Not mean."
        ),
    },
]
