# Data Model: Generic Niche Topic & Trend Bot

**Feature**: 001-generic-topic-trend  
**Date**: 2026-09-08

## Entity Relationship

```text
NicheProfile 1──* PostSource (via build_sources)
NicheProfile 1──1 SourceConfig
Focus *──1 NicheProfile (angle scoped to niche)
CandidatePost *──1 PostSource (via source field string)
DailyPostBot *──1 NicheProfile (runtime injection)
```

## Entities

### NicheProfile

Stack-specific configuration loaded from YAML.

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `id` | string | yes | Matches filename stem; kebab-case in CLI |
| `display_name` | string | yes | Non-empty; used in logs and infographic labels |
| `relevance_keywords` | list[string] | yes | Min 1 entry; lowercase recommended |
| `hashtags` | list[string] | yes | Min 1; each starts with `#` |
| `persona` | string | yes | Non-empty system prompt for Pass 1 |
| `review_niche_label` | string | yes | Non-empty; inserted into review LLM prompt |
| `weekday_angles` | map[int → WeekdayAngle] | yes | Keys 0–6 (Mon–Sun) |
| `sources` | SourceConfig | yes | At least one source block non-empty |
| `pulse_queries` | list[string] | yes | Min 1 for trend mode |
| `code_language` | string | yes | One of: `csharp`, `python`, `plain` |
| `default_angle` | string | no | Manual focus fallback; default: "Write for {display_name} peers." |

**Computed**:
- `required_hashtags_line`: space-joined `hashtags` (used in Pass 1 last line)

**State**: Immutable after load (`frozen` dataclass).

---

### SourceConfig

Nested under `NicheProfile.sources`.

| Field | Type | Required | Maps to |
| --- | --- | --- | --- |
| `reddit_subreddits` | list[string] | no | `RedditSource` |
| `devto_tags` | list[string] | no | `DevToSource` |
| `hn_queries` | list[string] | no | `HackerNewsSource` base queries |
| `rss_feeds` | list[RssFeedEntry] | no | `RssFeedSource` instances |

**RssFeedEntry**:

| Field | Type | Required |
| --- | --- | --- |
| `urls` | list[string] | yes |
| `name` | string | yes |

---

### WeekdayAngle

| Field | Type | Required |
| --- | --- | --- |
| `focus` | string | yes |
| `audience_signal` | string | yes |
| `avoid` | string | yes |

---

### Focus

Runtime discovery result; not persisted.

| Field | Type | Values |
| --- | --- | --- |
| `topic` | string | Manual topic or trend label or fallback title |
| `angle` | string | Niche-specific writing angle for Pass 1 |
| `mode` | enum | `manual` \| `trend` |

**Transitions**:
- CLI/env topic present → `mode=manual`, `topic=user input`
- No topic → Groq trend JSON → `mode=trend`; on failure → `topic=top niche post title`, `mode=trend`

---

### CandidatePost (existing — unchanged)

| Field | Type | Notes |
| --- | --- | --- |
| `title` | string | |
| `link` | string | |
| `summary` | string | |
| `reactions` | int | Engagement proxy |
| `source` | string | Human-readable source name |

---

### PostSource (protocol — unchanged shape)

```python
def fetch(self) -> list[CandidatePost]: ...
```

Implementations: `RedditSource`, `DevToSource`, `HackerNewsSource`, `RssFeedSource`.

---

## Scoring model (pick_article)

For each `CandidatePost` in pool:

```text
score = topic_overlap(focus.topic, title, summary) * 3
      + (1 if is_relevant(title, summary, profile.relevance_keywords) else 0) * 2
      + normalize(reactions)
```

Pick highest score among niche-relevant posts; if none relevant, pick highest reactions in full pool.

---

## Validation rules at load time

1. Profile file must exist at `profiles/{niche_id_with_underscores}.yaml`.
2. Unknown `code_language` → error listing allowed values.
3. Empty `hashtags` or `relevance_keywords` → error.
4. `weekday_angles` must include all keys 0–6 or loader fills missing with generic defaults.

---

## Files on disk

| Path | Entity |
| --- | --- |
| `profiles/*.yaml` | NicheProfile persistence |
| `data/loop_state.json` | Opener variance history (unchanged) |

No database. No new persistent state for Focus or trend picks.
