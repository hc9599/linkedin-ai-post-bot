---
description: "Task list for generic niche topic & trend bot"
---

# Tasks: Generic Niche Topic & Trend Bot

**Input**: Design documents from `/specs/001-generic-topic-trend/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Manual dry-run per quickstart.md (no pytest tasks)

**Organization**: Tasks grouped by user story for independent delivery.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and profile directory

- [x] T001 Add PyYAML to requirements.txt
- [x] T002 [P] Create profiles/ directory at repository root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Niche profile layer + generic sources — MUST complete before user stories

**⚠️ CRITICAL**: No user story work until this phase completes

- [x] T003 Implement NicheProfile, SourceConfig, load_profile, list_profiles in linkedin_bot/niche.py
- [x] T004 [P] Create profiles/csharp_dotnet.yaml with migrated hardcoded values
- [x] T005 [P] Create stub profiles/python.yaml
- [x] T006 Remove REQUIRED_HASHTAGS and HASHTAGS from linkedin_bot/config.py
- [x] T007 Generalize linkedin_bot/sources/relevance.py to is_relevant() and matches_topic()
- [x] T008 [P] Add linkedin_bot/sources/rss_feed.py (generic RSS source)
- [x] T009 Parameterize linkedin_bot/sources/reddit.py with subreddits constructor arg
- [x] T010 [P] Parameterize linkedin_bot/sources/devto.py with tags constructor arg
- [x] T011 Parameterize linkedin_bot/sources/hackernews.py with queries, keywords, extra_queries
- [x] T012 Add build_sources(profile) and fix dedupe in linkedin_bot/sources/__init__.py
- [x] T013 Delete linkedin_bot/sources/microsoft_blog.py

**Checkpoint**: Profile loads; sources build from YAML; RSS replaces Microsoft blog

---

## Phase 3: User Story 1 - Default niche unchanged (Priority: P1) 🎯 MVP

**Goal**: `python script.py --dry-run` behaves like today's C#/.NET bot via default profile

**Independent Test**: Dry-run completes with csharp_dotnet profile, C# hashtags, review pass, no publish

### Implementation for User Story 1

- [x] T014 [US1] Wire compose(niche_id) and default niche in linkedin_bot/bot.py
- [x] T015 [US1] Update PostGenerator.compose(posts, profile, focus=None) persona and hashtags from profile in linkedin_bot/generation/__init__.py
- [x] T016 [US1] Update pick_article(posts, profile) in linkedin_bot/generation/facts.py
- [x] T017 [US1] Generalize review_before_publish and llm_niche_source_check in linkedin_bot/review.py
- [x] T018 [US1] Pass profile hashtags through linkedin_bot/cleaning.py pipeline
- [x] T019 [US1] Use profile.display_name in linkedin_bot/images.py and linkedin_bot/infographic/renderer.py

**Checkpoint**: Default dry-run works end-to-end with profile-driven pipeline

---

## Phase 4: User Story 2 - Manual topic focus (Priority: P1)

**Goal**: `--topic "EF Core"` drives HN extra queries and topic-scored article pick

**Independent Test**: `python script.py --dry-run --topic "EF Core"` logs mode=manual

### Implementation for User Story 2

- [x] T020 [US2] Implement Focus dataclass and manual branch in linkedin_bot/discovery.py
- [x] T021 [US2] Add topic-aware scoring to pick_article in linkedin_bot/generation/facts.py
- [x] T022 [US2] Pass focus topic as HackerNewsSource extra_queries in linkedin_bot/sources/__init__.py
- [x] T023 [US2] Inject FOCUS TOPIC and NICHE ANGLE into Pass 1 in linkedin_bot/generation/__init__.py
- [x] T024 [US2] Add --topic flag and TOPIC env in linkedin_bot/bot.py

**Checkpoint**: Manual topic dry-run picks topic-aligned article

---

## Phase 5: User Story 3 - Auto trend discovery (Priority: P2)

**Goal**: No topic triggers Groq trend pick from pulse + niche feeds

**Independent Test**: Dry-run without topic logs mode=trend and niche angle

### Implementation for User Story 3

- [x] T025 [US3] Implement fetch_pulse_titles in linkedin_bot/discovery.py
- [x] T026 [US3] Implement resolve_focus trend mode with Groq JSON and fallback in linkedin_bot/discovery.py
- [x] T027 [US3] Wire pulse fetch and resolve_focus in linkedin_bot/bot.py run loop

**Checkpoint**: Trend mode runs when TOPIC empty

---

## Phase 6: User Story 4 - Switch niche via profile (Priority: P2)

**Goal**: `--niche python` loads profiles/python.yaml without code changes

**Independent Test**: `python script.py --dry-run --niche python --topic "async"` uses Python hashtags

### Implementation for User Story 4

- [x] T028 [US4] Add --niche flag and NICHE env with fail-fast missing profile in linkedin_bot/bot.py
- [x] T029 [US4] Wire weekday_angles from profile into Pass 1 in linkedin_bot/generation/__init__.py
- [x] T030 [US4] Add code_language highlighter map in linkedin_bot/infographic/renderer.py

**Checkpoint**: Second niche profile works from YAML only

---

## Phase 7: User Story 5 - GitHub Actions dispatch (Priority: P3)

**Goal**: Manual workflow accepts niche and topic inputs

**Independent Test**: bot.yml has workflow_dispatch inputs for niche and topic

### Implementation for User Story 5

- [x] T031 [US5] Add workflow_dispatch niche and topic inputs to .github/workflows/bot.yml

**Checkpoint**: CI passes NICHE and TOPIC env vars

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Dead code removal and docs

- [x] T032 [P] Prune dead banks from linkedin_bot/generation/style.py (keep PASS3_REJECT, OPENER_STYLES, TONES, MAX_POST_WORDS)
- [x] T033 [P] Update README.md for niche-configurable bot and profile guide
- [x] T034 Run quickstart.md grep checks and verify no is_dotnet_relevant in linkedin_bot/

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 → Phase 2 → User Stories (3–7) → Phase 8
- US1 blocks US2/US3 integration in bot.py but foundational must come first
- US2 and US3 both extend discovery.py and bot.py sequentially
- US4 depends on US1 profile wiring
- US5 independent after US1

### Parallel Opportunities

- T004 + T005 + T008 + T010 (different files)
- T032 + T033 (polish, parallel)

### MVP Scope

**User Story 1 only**: Phase 1 + Phase 2 + Phase 3 (T001–T019)

---

## Implementation Strategy

1. Complete Setup + Foundational (T001–T013)
2. Deliver US1 default niche (T014–T019) → validate dry-run
3. Add US2 manual topic (T020–T024)
4. Add US3 trend mode (T025–T027)
5. Add US4 multi-niche (T028–T030)
6. Add US5 workflow (T031)
7. Polish (T032–T034)
