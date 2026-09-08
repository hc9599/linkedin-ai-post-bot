# Feature Specification: Generic Niche Topic & Trend Bot

**Feature Branch**: `001-generic-topic-trend`

**Created**: 2026-09-08

**Status**: Draft

**Input**: Refactor LinkedIn AI post bot into a niche-configurable curator. Profile YAML drives sources, keywords, hashtags, and prompts. Support manual `--topic` focus or auto trend discovery from existing feeds + Groq. Remove C#/.NET hardcoding and dead code. Preserve default C#/.NET behavior via `profiles/csharp_dotnet.yaml`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run default niche unchanged (Priority: P1)

As a bot operator, I run the bot with no new flags so it behaves like today's C#/.NET weekday post bot.

**Why this priority**: Backward compatibility is the baseline; breaking the default run blocks adoption.

**Independent Test**: `python script.py --dry-run` completes, fetches from Reddit/dev.to/HN/RSS, generates a C#/.NET post, passes review gate, prints final post without publishing.

**Acceptance Scenarios**:

1. **Given** no `--niche` or `NICHE` env, **When** the bot runs, **Then** it loads `profiles/csharp_dotnet.yaml` and produces a C#/.NET-relevant post.
2. **Given** dry-run mode, **When** generation completes, **Then** no LinkedIn publish occurs and source credit is attached.

---

### User Story 2 - Focus run with manual topic (Priority: P1)

As a bot operator, I pass `--topic "EF Core"` so the bot searches niche sources for matching articles and curates a post around that focus.

**Why this priority**: Manual topic control is the primary user-requested workflow.

**Independent Test**: `python script.py --dry-run --topic "EF Core"` logs manual focus mode, picks a relevant article, generates post aligned to topic.

**Acceptance Scenarios**:

1. **Given** `--topic "EF Core"`, **When** sources are fetched, **Then** HN queries include topic-augmented searches and article pick favors topic overlap.
2. **Given** a generated post, **When** review runs, **Then** niche keyword and LLM checks use profile labels, not hardcoded C#/.NET strings.

---

### User Story 3 - Auto trend discovery (Priority: P2)

As a bot operator, I run without `--topic` so Groq picks a current tech trend from feed titles and maps it to the active niche angle before curating a post.

**Why this priority**: Enables hands-off weekday runs with fresher angles without new search APIs.

**Independent Test**: `python script.py --dry-run` (no topic) logs trend pick + niche angle before article lock.

**Acceptance Scenarios**:

1. **Given** no topic and pulse titles from HN broad queries, **When** `resolve_focus` runs, **Then** it returns a `Focus` with `mode=trend`, trend label, and niche-specific angle.
2. **Given** Groq returns invalid JSON, **When** trend resolution fails, **Then** fallback uses top-reaction niche post title as topic.

---

### User Story 4 - Switch niche via profile (Priority: P2)

As a bot operator, I run `--niche python` to curate Python-focused posts using `profiles/python.yaml` without changing core code.

**Why this priority**: Proves generic design; unlocks reuse for other stacks.

**Independent Test**: `python script.py --dry-run --niche python --topic "async"` uses Python keywords, subs/tags, hashtags from profile.

**Acceptance Scenarios**:

1. **Given** `profiles/python.yaml` exists, **When** `--niche python` is passed, **Then** sources, relevance filter, hashtags, and review prompt use Python profile values.
2. **Given** a missing profile id, **When** the bot starts, **Then** it fails fast with a clear error listing available profiles.

---

### User Story 5 - GitHub Actions manual dispatch (Priority: P3)

As a bot operator, I trigger the workflow manually with optional `niche` and `topic` inputs.

**Why this priority**: Production trigger path; lower priority than local CLI validation.

**Independent Test**: Workflow YAML exposes `workflow_dispatch` inputs and passes `NICHE`/`TOPIC` env vars.

**Acceptance Scenarios**:

1. **Given** manual workflow run with `niche=csharp-dotnet` and empty topic, **When** job executes, **Then** trend mode runs on schedule-equivalent path.
2. **Given** manual run with `topic=Blazor`, **When** job executes, **Then** manual focus mode is used.

---

### Edge Cases

- All niche sources return empty → bot exits gracefully without publish.
- Trend pulse fetch fails → trend mode uses niche titles only.
- No article matches topic well → fall back to best niche-relevant by reactions; log warning.
- Invalid or partial profile YAML → load error with field name.
- Profile missing required fields → validation error at startup.
- Infographic highlighter unsupported for niche `code_language` → passthrough plain code block.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load niche configuration from `profiles/{niche_id}.yaml` (default `csharp-dotnet` → `profiles/csharp_dotnet.yaml`).
- **FR-002**: System MUST accept `--niche` CLI flag and `NICHE` env var; `--topic` and `TOPIC` for optional manual focus.
- **FR-003**: System MUST parameterize Reddit, dev.to, Hacker News, and RSS sources from profile `sources` block.
- **FR-004**: System MUST replace `microsoft_blog.py` with generic `RssFeedSource(feed_urls, source_name)`.
- **FR-005**: System MUST implement `resolve_focus` supporting manual and trend modes without external search APIs.
- **FR-006**: System MUST score and pick articles using topic overlap, niche relevance keywords, and reactions.
- **FR-007**: System MUST inject profile persona, hashtags, weekday angles, and focus into generation prompts.
- **FR-008**: System MUST generalize review gate to use `profile.review_niche_label` and `profile.relevance_keywords`.
- **FR-009**: System MUST remove unused prompt banks from `style.py` and delete niche-hardcoded functions (`is_dotnet_relevant`, `llm_dotnet_source_check`).
- **FR-010**: System MUST fix `SourceAggregator` dedupe bug (return deduped list, not pre-dedupe slice).
- **FR-011**: System MUST preserve existing multi-pass generation, cleaning, review, infographic, and publish pipeline.
- **FR-012**: System MUST NOT require new paid search APIs (Tavily/SerpAPI/Bing).

### Key Entities

- **NicheProfile**: Stack-specific config — keywords, hashtags, persona, sources, pulse queries, weekday angles, code language.
- **SourceConfig**: Nested config for reddit subs, dev.to tags, HN queries, RSS feeds.
- **Focus**: Resolved topic + niche angle + mode (`manual` | `trend`).
- **CandidatePost**: Existing article candidate from any source (unchanged).
- **PostSource**: Protocol — `fetch() -> list[CandidatePost]` (unchanged contract).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Default dry-run (`python script.py --dry-run`) succeeds with C#/.NET profile and produces review-passing output.
- **SC-002**: Manual topic dry-run completes with logged `mode=manual` and topic-scored article pick.
- **SC-003**: Trend dry-run completes with logged `mode=trend`, trend label, and niche angle before article lock.
- **SC-004**: `--niche python` dry-run uses Python profile values (grep logs / hashtags differ from C# default).
- **SC-005**: Codebase grep shows zero `is_dotnet_relevant`, `llm_dotnet_source_check`, `REQUIRED_HASHTAGS` in core modules after refactor.
- **SC-006**: Dead style banks removed; `microsoft_blog.py` deleted; `style.py` retains only niche-agnostic constants.

## Assumptions

- PyYAML added to `requirements.txt` for profile loading (acceptable small dependency).
- Groq API key remains required for generation and trend/review checks.
- LinkedIn credentials unchanged for publish path.
- `profiles/python.yaml` is a minimal stub proving second niche; user expands later.
- Infographic C# highlighter remains; other niches get passthrough until dedicated highlighter added.
- Constitution file is template-only; gates derived from project SOLID/minimal-diff conventions.
