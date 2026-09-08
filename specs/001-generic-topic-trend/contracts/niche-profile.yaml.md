# Contract: Niche Profile YAML

**Version**: 1.0  
**Feature**: 001-generic-topic-trend

## File location

```text
profiles/{niche_id}.yaml
```

CLI id `csharp-dotnet` maps to file `profiles/csharp_dotnet.yaml` (hyphens → underscores).

## Schema

```yaml
id: string                    # required; must match CLI id (kebab-case)
display_name: string          # required
relevance_keywords: string[]  # required; min 1
hashtags: string[]            # required; min 1; each starts with #
persona: string               # required; multi-line OK
review_niche_label: string    # required; e.g. "C# and/or .NET"
default_angle: string         # optional
code_language: string         # required: csharp | python | plain
pulse_queries: string[]       # required; min 1; broad tech for trend mode

weekday_angles:
  0:                           # Monday (datetime.weekday())
    focus: string
    audience_signal: string
    avoid: string
  1: ...                       # through 6 (Sunday)

sources:
  reddit_subreddits: string[]  # optional
  devto_tags: string[]         # optional
  hn_queries: string[]         # optional
  rss_feeds:
    - name: string
      urls: string[]           # try in order until entries returned
```

## Loader API

```python
def load_profile(niche_id: str) -> NicheProfile: ...
def list_profiles() -> list[str]: ...
```

## Errors

| Condition | Behavior |
| --- | --- |
| File not found | `FileNotFoundError` with available profile ids |
| Missing required field | `ValueError` naming field |
| Invalid `code_language` | `ValueError` with allowed values |
| Empty hashtags/keywords | `ValueError` |

## Example (minimal)

See `profiles/csharp_dotnet.yaml` (shipped with implementation).
