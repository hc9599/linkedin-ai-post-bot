# Research: Generic Niche Topic & Trend Bot

**Feature**: 001-generic-topic-trend  
**Date**: 2026-09-08

## R-001: Profile format — YAML vs JSON

**Decision**: YAML via PyYAML (`profiles/{id}.yaml`).

**Rationale**:
- Weekday angles and persona are multi-line strings; YAML reads cleaner than JSON escapes.
- Single new dependency; acceptable for operator-edited config.
- Profile ids use kebab-case CLI (`csharp-dotnet`) mapped to snake_case filenames (`csharp_dotnet.yaml`).

**Alternatives considered**:
- **JSON only (stdlib)**: No dependency, but painful for long prompt strings.
- **Python modules per niche**: Type-safe but requires code change for each new stack; violates open/closed goal.
- **TOML**: Less common for nested prompt blocks; team familiarity lower.

---

## R-002: Trend discovery without web search APIs

**Decision**: HN Algolia pulse queries (from profile `pulse_queries`) + niche feed titles → Groq JSON `{trend, niche_angle, why}`.

**Rationale**:
- Matches user constraint: no Tavily/SerpAPI/Bing.
- Reuses existing `fetch_json` + Algolia integration from `hackernews.py`.
- Pulse titles never published directly; only inform trend pick.

**Alternatives considered**:
- **Reactions-only ranking**: Already exists; does not satisfy "latest technology trend" intent.
- **Google Trends / RSS news**: New integrations, brittle, out of scope.
- **LLM-only trend inventing**: Hallucinates trends without feed grounding.

**Fallback**: If Groq JSON parse fails or trend drifts off-niche, use highest-reaction niche post title as `Focus.topic`.

---

## R-003: Article scoring for topic-aware pick

**Decision**: Weighted score = `topic_token_overlap * 3 + is_relevant * 2 + normalized_reactions`.

**Rationale**:
- Reuses token overlap logic already in `review.py` (`_tokens`, `_overlap_score`).
- Keeps engagement signal so viral on-topic posts still win.
- Clear fallback when overlap is zero: best niche-relevant by reactions.

**Alternatives considered**:
- **Reactions only**: Ignores manual topic intent.
- **LLM pick article**: Extra Groq call per run; slower, costlier, less deterministic.
- **Strict topic filter**: Too brittle when HN search is sloppy.

---

## R-004: SOLID module boundaries

**Decision**:

| Module | Responsibility |
| --- | --- |
| `niche.py` | Load/validate `NicheProfile` |
| `discovery.py` | `Focus`, `resolve_focus`, `fetch_pulse_titles` |
| `sources/*` | Fetch only; parameterized by profile |
| `sources/__init__.py` | `build_sources(profile)`, `SourceAggregator` |
| `generation/*` | Write loop; accepts profile + focus |
| `review.py` | Pre-publish gate; profile-driven niche check |
| `bot.py` | Orchestration + `compose(niche_id)` DI wiring |

**Rationale**: Matches existing pipeline seams; new behavior via config + small interface extensions, not rewrites.

**Alternatives considered**:
- **Monolithic config dict passed everywhere**: Violates typing and validation clarity.
- **Plugin registry with dynamic imports**: Over-engineered for two shipped profiles.

---

## R-005: Dead code removal scope

**Decision**: Remove from `style.py`: `TOPIC_ANGLES`, `BANNED_PHRASES`, `BANNED_OPENERS`, `OPENERS`, `ENDINGS`, `FORMATS`, `WORD_COUNTS`, `WIT_MODES`. Keep: `PASS3_REJECT`, `OPENER_STYLES`, `TONES`, `MAX_POST_WORDS`.

**Rationale**: Grep confirms these banks are never imported outside `style.py`. Live gates use `PASS3_REJECT` + review regexes. `TOPIC_ANGLES` moves to profile YAML and gets wired into Pass 1.

**Alternatives considered**:
- **Wire unused banks into prompts**: Adds complexity without user request; duplicates `PASS3_REJECT`.

---

## R-006: RSS source generalization

**Decision**: Replace `MicrosoftBlogSource` with `RssFeedSource(feed_urls: list[str], source_name: str)` using same `fetch_feed_entries` logic.

**Rationale**: Microsoft blog is generic RSS; name and URLs belong in profile `sources.rss`.

**Alternatives considered**:
- **Keep MicrosoftBlogSource + add RssFeedSource**: Duplicate fetch logic.
- **Single global RSS list in profile only**: Same outcome via one class.

---

## R-007: Infographic language handling

**Decision**: Profile field `code_language` (`csharp`, `python`, `plain`). Map to highlighter: `csharp` → existing `highlight_csharp`; others → HTML-escape passthrough.

**Rationale**: Minimal change; C# default preserved. Python stub profile works without new highlighter work.

**Alternatives considered**:
- **Pygments generic highlighter**: New dependency + template risk for v1.
- **Skip images for non-C# niches**: Regresses feature parity.

---

## R-008: Niche id → file mapping

**Decision**: CLI `--niche csharp-dotnet` maps to `profiles/csharp_dotnet.yaml` (hyphens → underscores).

**Rationale**: CLI-friendly ids, filesystem-safe filenames, one predictable rule.

**Alternatives considered**:
- **Exact filename match**: Forces underscores in CLI; worse UX.
- **Directory per niche**: Heavier layout for single YAML file.

---

## R-009: Testing approach

**Decision**: Manual dry-run verification per quickstart.md; no new pytest suite in this feature (repo has no existing test harness).

**Rationale**: Matches current project state; quickstart documents validation scenarios.

**Alternatives considered**:
- **Add pytest unit tests for niche loader**: Valuable follow-up; out of scope for plan phase unless user requests.

---

## Resolved clarifications

All Technical Context items resolved — no remaining NEEDS CLARIFICATION.
