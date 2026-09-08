# Contract: Discovery & Focus

**Version**: 1.0  
**Feature**: 001-generic-topic-trend

## Focus

```python
@dataclass(frozen=True)
class Focus:
    topic: str
    angle: str
    mode: Literal["manual", "trend"]
```

## resolve_focus

```python
def resolve_focus(
    llm: LLMClient,
    profile: NicheProfile,
    niche_posts: list[CandidatePost],
    pulse_titles: list[str],
    topic: str | None,
) -> Focus: ...
```

### Manual mode (`topic` non-empty)

- `mode = "manual"`
- `topic = topic.strip()`
- `angle = profile.default_angle or f"Write for {profile.display_name} peers about this topic."`

### Trend mode (`topic` empty)

1. Build compact title lists from `niche_posts` (top by reactions) and `pulse_titles`.
2. Groq prompt requests JSON only:

```json
{
  "trend": "short trend label",
  "niche_angle": "how this trend relates to {profile.display_name}",
  "why": "one sentence rationale"
}
```

3. On success: `Focus(topic=trend, angle=niche_angle, mode="trend")`
4. On parse/validation failure: `Focus(topic=<top niche post title>, angle=profile.default_angle, mode="trend")`

Pulse titles are **never** published as source articles.

## fetch_pulse_titles

```python
def fetch_pulse_titles(profile: NicheProfile, *, limit: int = 20) -> list[str]: ...
```

- Uses HN Algolia with `profile.pulse_queries`
- No niche keyword filter on pulse hits
- Returns deduplicated title strings only

## Article pick (downstream)

```python
def pick_article(
    posts: list[CandidatePost],
    profile: NicheProfile,
    focus: Focus,
) -> CandidatePost: ...
```

Scoring contract documented in [data-model.md](../data-model.md).

## Generation injection (Pass 1)

Prompt MUST include:

```text
FOCUS TOPIC: {focus.topic}
NICHE ANGLE: {focus.angle}
WEEKDAY ANGLE: {profile.weekday_angles[weekday].focus}  # plus audience_signal, avoid
```

Persona from `profile.persona`; last line hashtags from `profile.hashtags`.
