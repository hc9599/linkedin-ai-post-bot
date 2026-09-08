# Quickstart: Generic Niche Topic & Trend Bot

**Feature**: 001-generic-topic-trend  
**Branch**: `001-generic-topic-trend`

Validation guide for manual dry-run checks. See [data-model.md](./data-model.md) and [contracts/](./contracts/) for entity and interface details.

## Prerequisites

- Python 3.11
- Dependencies installed: `pip install -r requirements.txt`
- Playwright (only if testing `--image`): `playwright install chromium`
- `GROQ_API_KEY` set (required for generation and trend/review checks)
- LinkedIn secrets **not** required for dry-run

PowerShell:

```powershell
cd D:\Users\hchoudhary\Downloads\linkedin-ai-post-bot-main
pip install -r requirements.txt
$env:GROQ_API_KEY = "your-key"
```

## Scenario 1 — Default niche (backward compatible)

**Goal**: SC-001 — default run matches pre-refactor C#/.NET behavior class.

```powershell
python script.py --dry-run
```

**Expected**:
- Log: loads niche `csharp-dotnet` (or default profile name)
- Fetches Reddit, dev.to, HN, RSS (.NET Dev Blog via profile)
- Logs article lock with C#/.NET-relevant title
- Pass 5 review passes
- Final post includes `#CSharp #DotNet ...` and `Source:` line
- Ends with `*** DRY RUN — skipping LinkedIn publish ***`

---

## Scenario 2 — Manual topic focus

**Goal**: SC-002 — topic drives search and pick.

```powershell
python script.py --dry-run --topic "EF Core"
```

**Expected**:
- Log: `Focus mode=manual`, topic `EF Core`
- HN fetch includes topic-augmented queries
- Locked article title/summary overlaps EF Core / Entity Framework domain
- Generated post references niche angle for manual topic

Env equivalent:

```powershell
$env:TOPIC = "EF Core"
python script.py --dry-run
```

---

## Scenario 3 — Auto trend discovery

**Goal**: SC-003 — no topic triggers trend mode.

```powershell
Remove-Item Env:TOPIC -ErrorAction SilentlyContinue
python script.py --dry-run
```

**Expected**:
- Log: pulse titles fetched from broad HN queries
- Log: `Focus mode=trend`, trend label + niche angle before article lock
- Post still niche-relevant (C#/.NET for default profile)

---

## Scenario 4 — Alternate niche profile

**Goal**: SC-004 — Python stub profile works without code change.

```powershell
python script.py --dry-run --niche python --topic "async"
```

**Expected**:
- Loads `profiles/python.yaml`
- Hashtags differ from C# default (e.g. `#Python`)
- Review prompt uses Python niche label
- Dry-run completes or aborts with clear review reason (stub profile may have fewer sources)

---

## Scenario 5 — Missing profile error

```powershell
python script.py --dry-run --niche nonexistent-stack
```

**Expected**:
- Fail fast before fetch
- Error lists available profiles in `profiles/`

---

## Scenario 6 — GitHub Actions inputs (manual)

**Goal**: SC-005 workflow wiring (validate YAML only until merge).

1. Open Actions → Daily LinkedIn Post → Run workflow
2. Set `niche`: `csharp-dotnet`, `topic`: empty → trend mode
3. Set `niche`: `csharp-dotnet`, `topic`: `Blazor` → manual mode

**Expected**: Workflow passes `NICHE` and `TOPIC` env to `python script.py --image`.

---

## Post-refactor grep checks

Run from repo root:

```powershell
# Should return no matches in linkedin_bot/
rg "is_dotnet_relevant|llm_dotnet_source_check|REQUIRED_HASHTAGS" linkedin_bot/

# Should not exist
Test-Path linkedin_bot\sources\microsoft_blog.py  # False

# style.py should not contain dead banks
rg "BANNED_PHRASES|WIT_MODES|TOPIC_ANGLES" linkedin_bot/generation/style.py  # no matches
```

---

## Adding a new niche (operator guide)

1. Copy `profiles/python.yaml` → `profiles/my_stack.yaml`
2. Set `id`, `display_name`, `relevance_keywords`, `hashtags`, `persona`, `sources`, `pulse_queries`
3. Run: `python script.py --dry-run --niche my-stack --topic "your angle"`

No core code changes required unless adding a new source type.
