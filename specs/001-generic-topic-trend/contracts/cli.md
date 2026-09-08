# Contract: CLI & Environment

**Version**: 1.0  
**Feature**: 001-generic-topic-trend

## Entry point

```bash
python script.py [OPTIONS]
```

Delegates to `linkedin_bot.bot.main()`.

## Flags

| Flag | Env var | Default | Description |
| --- | --- | --- | --- |
| `--dry-run` | `DRY_RUN` | off | Generate and print; do not publish |
| `--image` | `IMAGE` | off | Generate infographic PNG |
| `--niche` | `NICHE` | `csharp-dotnet` | Profile id to load |
| `--topic` | `TOPIC` | empty | Manual focus; empty → trend mode |

Env vars use truthy values `1`, `true`, `yes` for boolean flags (existing pattern).

## Run sequence (orchestrator)

```text
1. load_profile(niche_id)
2. build_sources(profile) → SourceAggregator.fetch() → posts
3. if topic empty: fetch_pulse_titles(profile) → pulse_titles
4. resolve_focus(llm, profile, posts, pulse_titles, topic) → focus
5. PostGenerator.compose(posts, profile, focus)
6. cleaning pipeline (profile hashtags)
7. review_before_publish(llm, draft, cleaned, posts, profile)
8. attach_source_credit → optional image → publish (unless dry-run)
```

## GitHub Actions

`workflow_dispatch` inputs:

| Input | Type | Default |
| --- | --- | --- |
| `niche` | string | `csharp-dotnet` |
| `topic` | string | `` |

Mapped to `NICHE` and `TOPIC` env in run step.

Scheduled cron: no topic → trend mode; niche defaults to `csharp-dotnet`.

## Exit behavior

| Outcome | Exit |
| --- | --- |
| No posts fetched | print + return (exit 0) |
| Review abort | print ABORT + return (exit 0) |
| Missing GROQ key at LLM call | ValueError / Exception |
| Missing profile | error before fetch |
