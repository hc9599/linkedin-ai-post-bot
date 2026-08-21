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
            "Write for other C# developers. A hiring manager might lurk, but do not explain "
            "the industry to them. If a peer would skip the paragraph, cut it."
        ),
        "avoid": "Do not announce the feature. Say what it changes in day-to-day C#.",
    },
    1: {  # Tuesday — tooling & developer experience
        "focus": (
            "Focus on tooling — IDE, SDK, debugger, NuGet, MSBuild. What changes in the "
            "afternoon you already work, not a product tour."
        ),
        "audience_signal": (
            "Sound like you tried the tool, or you know why you still will not. Peers, not a review site."
        ),
        "avoid": "Do not write a product review. No 'this will transform your workflow'.",
    },
    2: {  # Wednesday — architecture & engineering decisions
        "focus": (
            "Focus on a .NET architecture tradeoff — async, DI, module boundaries, how the "
            "system is shaped. Name the tension."
        ),
        "audience_signal": (
            "Another senior should want to agree or argue. Vague 'think about tradeoffs' is a fail."
        ),
        "avoid": "No architecture poetry. One named pattern or decision.",
    },
    3: {  # Thursday — C# positioning & career perspective
        "focus": (
            "Focus on where C# / .NET sits this year — compared to other stacks, hiring, "
            "community, or why you still pick it for backend work."
        ),
        "audience_signal": (
            "A take someone can disagree with. Cheerleading 'C# is great' is a fail."
        ),
        "avoid": "Do not write a generic 'C# is great' post. Pick adoption, competition, or direction.",
    },
    4: {  # Friday — enterprise & infrastructure
        "focus": (
            "Focus on enterprise .NET — cloud, data, security, pipelines, what actually "
            "breaks when the system is large. Be specific about the failure mode."
        ),
        "audience_signal": (
            "Someone who has been paged should nod. Tutorial-speak is a fail."
        ),
        "avoid": (
            "Do not reference NAS, SMB, or internal product details. Keep it any senior "
            ".NET backend person could own."
        ),
    },
    5: {  # Saturday — performance & internals
        "focus": (
            "Focus on .NET performance — Span<T>, GC, benchmarks, JIT. What you would "
            "measure or change, not a concept name-drop."
        ),
        "audience_signal": (
            "Show you have been bitten by allocations or pauses. Abstract 'performance matters' is a fail."
        ),
        "avoid": "Do not just name a concept. Say what goes wrong without it.",
    },
    6: {  # Sunday — new releases & future direction
        "focus": (
            "Focus on what is new or coming in .NET. Filter it: what you would try, skip, "
            "or wait on. Not a changelog."
        ),
        "audience_signal": (
            "A useful opinion on the roadmap. Reciting release notes is a fail."
        ),
        "avoid": "Do not write a changelog summary. Push back or filter.",
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
    "Any opener that reads like the first line of a Wikipedia article",
    "Any opener that defines a problem for 'the industry' instead of a thing you actually touch",
    "Any opener that makes a generic observation applying to all software development",
]

# ---------------------------------------------------------------
# OPENERS — positive instructions for the first sentence
# ---------------------------------------------------------------
OPENERS = [
    (
        "Open on a named thing you actually use (MSBuild, binlogs, Convert.ChangeType, "
        "a specific API). First sentence should sound like a Slack message, not a whitepaper."
    ),
    (
        "Open with a concrete annoyance: something slow, opaque, easy to get wrong. "
        "Name the tool or API. No 'most teams'."
    ),
    (
        "Open mid-thought, like you already started talking. Example shape: "
        "'We've had X for years. Nobody uses it because Y.'"
    ),
    (
        "Open with what you would try or skip, then say why in the next line. "
        "Opinion first, recap later (or never)."
    ),
    (
        "Open with one specific workflow moment (CI log, debugger, PR review). "
        "Keep it to two short sentences max."
    ),
]

# ---------------------------------------------------------------
# ENDINGS — how to close the post
# ---------------------------------------------------------------
ENDINGS = [
    (
        "End with what you will actually do next (try it on the next failure, ignore it, "
        "wait for GA). No 'what are your thoughts?'"
    ),
    (
        "End with one blunt takeaway in plain words. No moral. No 'this matters because teams'."
    ),
    (
        "End with one check a .NET person can run this week. One sentence."
    ),
    (
        "End by naming who this is for (the person on the flaky pipeline, the one drowning "
        "in binlogs). Then stop."
    ),
    (
        "End with a small doubt or limit ('not magic', 'still have to read the task output'). "
        "Humans hedge a little. Do not write a TED closer."
    ),
]

# ---------------------------------------------------------------
# FORMATS — post structure
# ---------------------------------------------------------------
FORMATS = [
    (
        "LinkedIn-native: 3 or 4 short paragraphs, 1-2 sentences each, blank line between. "
        "Look like a person typed this on their phone, not a blog post pasted in."
    ),
    (
        "Hook line (one sentence, own paragraph). Then two short paragraphs of 2 sentences. "
        "Then a one-line closer. No wall of text."
    ),
    (
        "Four to seven short lines. Some lines can be one sentence. Use line breaks the way "
        "people do on LinkedIn. No bullet points. No numbered list."
    ),
    (
        "Two short paragraphs only. First: the situation. Second: your take + what you'd do. "
        "Keep sentences uneven — mix a short one with a longer one. Do not make every sentence "
        "the same length."
    ),
]

WORD_COUNTS = [
    "between 80 and 110 words — short, like a real update, not an essay",
    "between 90 and 130 words — room for one concrete detail from the article",
    "between 70 and 100 words — tight. Cut anything a coworker already knows",
    "between 100 and 140 words — still a post, not a blog. Stop when the point is made",
]
