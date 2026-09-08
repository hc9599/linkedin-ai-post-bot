# Implementation Plan: Generic Niche Topic & Trend Bot

**Branch**: `001-generic-topic-trend` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-generic-topic-trend/spec.md`  
**Source plan**: `.cursor/plans/topic_trend_discovery_e4ec8212.plan.md`

## Summary

Refactor the LinkedIn AI post bot from a hardcoded C#/.NET curator into a **niche-configurable** pipeline. YAML profiles drive sources, relevance keywords, hashtags, persona, and review labels. Operators pass `--topic` for manual focus or omit it for **auto trend discovery** (HN pulse + niche feeds + Groq). Existing multi-pass generation, review gate, infographic, and publish flow are reused. Dead prompt banks and `microsoft_blog.py` are removed. Default profile preserves current behavior.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: requests, feedparser, urllib3, jinja2, playwright (existing); **PyYAML** (new, profile loading)

**Storage**: YAML files in `profiles/`; `data/loop_state.json` for opener variance (unchanged)

**Testing**: Manual dry-run scenarios in [quickstart.md](./quickstart.md); no pytest harness today

**Target Platform**: Linux (GitHub Actions ubuntu-latest), Windows dev

**Project Type**: CLI automation bot (`script.py` → `linkedin_bot.bot.main`)

**Performance Goals**: Single daily run completes within existing 60-minute workflow timeout

**Constraints**: No paid web search APIs; Groq + LinkedIn secrets required; backward-compatible default run

**Scale/Scope**: ~15 Python modules touched; 2 profile YAMLs shipped; 1 new module (`discovery.py`), 1 new module (`niche.py`), 1 new source (`rss_feed.py`), 1 deleted source (`microsoft_blog.py`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Project constitution (`.specify/memory/constitution.md`) is a template — apply these derived gates:

| Gate | Pre-Phase 0 | Post-Phase 1 |
| --- | --- | --- |
| Backward compatible default | PASS — `csharp_dotnet.yaml` mirrors current hardcoded values | PASS |
| SOLID separation | PASS — niche/discovery/sources/generation/review/bot split | PASS — contracts document interfaces |
| Minimal diff / reuse pipeline | PASS — no rewrite of publish/infographic/cleaning | PASS |
| No unjustified complexity | PASS — one new dep (PyYAML), no plugin registry | PASS |
| Dead code removed | N/A pre-design | PASS — explicit removal list in spec FR-009 |

**Result**: All gates PASS. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/001-generic-topic-trend/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 entities
├── quickstart.md        # Phase 1 validation guide
├── contracts/           # Phase 1 interface contracts
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
script.py
profiles/
├── csharp_dotnet.yaml   # Default niche (migrated from hardcoded values)
└── python.yaml          # Stub second niche
linkedin_bot/
├── bot.py               # Orchestrator; compose(niche_id); CLI --niche --topic
├── niche.py             # NEW: NicheProfile load/validate
├── discovery.py         # NEW: Focus, resolve_focus, fetch_pulse_titles
├── config.py            # Secrets/flags only; hashtags move to profile
├── models.py            # CandidatePost (unchanged)
├── review.py            # Generic niche review gate
├── cleaning.py          # Hashtags from profile
├── images.py            # Profile display_name / code_language in prompts
├── sources/
│   ├── __init__.py      # build_sources(profile); dedupe fix
│   ├── relevance.py     # is_relevant(), matches_topic()
│   ├── rss_feed.py      # NEW: generic RSS (replaces microsoft_blog)
│   ├── reddit.py        # Parameterized subreddits
│   ├── devto.py         # Parameterized tags
│   └── hackernews.py    # Parameterized queries + keywords + focus extras
├── generation/
│   ├── __init__.py      # compose(posts, profile, focus)
│   ├── facts.py         # pick_article(posts, profile, focus)
│   └── style.py         # Pruned to niche-agnostic constants only
└── infographic/         # Highlighter selection via profile.code_language
.github/workflows/bot.yml  # workflow_dispatch niche + topic inputs
```

**Structure Decision**: Single Python package (`linkedin_bot/`) with YAML profiles at repo root. No new top-level apps or test tree in this feature.

## Implementation Phases

### Phase A — Niche profile layer

1. Add `linkedin_bot/niche.py` with `NicheProfile`, `SourceConfig`, `load_profile(niche_id)`.
2. Create `profiles/csharp_dotnet.yaml` — migrate keywords, hashtags, persona, sources, weekday angles, pulse queries from current code.
3. Create stub `profiles/python.yaml`.
4. Add `pyyaml` to `requirements.txt`.
5. Remove `REQUIRED_HASHTAGS` / `HASHTAGS` from `config.py`.

### Phase B — Generic sources

1. Add `sources/rss_feed.py`; wire Microsoft .NET feed via profile.
2. Parameterize `RedditSource`, `DevToSource`, `HackerNewsSource` constructors.
3. Generalize `relevance.py` → `is_relevant(title, summary, keywords)`, `matches_topic(...)`.
4. Add `build_sources(profile)` in `sources/__init__.py`; fix dedupe return.
5. Delete `sources/microsoft_blog.py`.

### Phase C — Discovery + scoring

1. Add `discovery.py`: `Focus`, `resolve_focus`, `fetch_pulse_titles`.
2. Update `facts.pick_article(posts, profile, focus)` with weighted scoring.

### Phase D — Pipeline wiring

1. `PostGenerator.compose(posts, profile, focus)` — persona, hashtags, weekday angle, focus injection.
2. `review.review_before_publish(..., profile)` — generic niche LLM check.
3. `cleaning.py` — profile hashtags.
4. `images.py` / `infographic/renderer.py` — profile labels + highlighter map.
5. `bot.py` — full run order: fetch → pulse (if no topic) → resolve_focus → generate → clean → review → publish.
6. CLI `--niche`, `--topic`; env `NICHE`, `TOPIC`.

### Phase E — Prune + docs

1. Prune `style.py` dead banks.
2. Scrub niche-hardcoded log strings.
3. Update `README.md`, `.github/workflows/bot.yml`.

## Complexity Tracking

> No violations requiring justification.

## Phase 0 Output

See [research.md](./research.md) — all clarifications resolved.

## Phase 1 Output

- [data-model.md](./data-model.md)
- [contracts/](./contracts/)
- [quickstart.md](./quickstart.md)

## Post-Design Constitution Re-check

All gates remain PASS after Phase 1 design artifacts.
