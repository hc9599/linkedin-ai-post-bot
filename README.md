# LinkedIn AI post bot

A weekday helper that finds niche tech articles, writes a LinkedIn post in a senior-developer voice, and can publish for you.

**Niche-configurable** — default is C# / .NET via `profiles/csharp_dotnet.yaml`. Add a YAML profile to target Python, Rust, or any stack without changing core code.

Meant to run on **GitHub Actions**. Run locally first with `--dry-run` so nothing goes live.

## What it does

1. Loads a niche profile (`--niche`, default `csharp-dotnet`).
2. Reads recent posts from Reddit, dev.to, Hacker News, and RSS feeds defined in the profile.
3. **Manual topic** (`--topic "EF Core"`) or **auto trend** (Groq picks a hot trend from feeds, maps to niche angle).
4. Asks Groq to write a LinkedIn post about one curated article.
5. Cleans markdown, emojis, and leftover notes; double-checks niche fit and source match.
6. Adds a Source line with title, site, and URL.
7. Optionally draws an infographic.
8. Posts to LinkedIn — unless dry-run.

## Folders

| Path | What it is |
| --- | --- |
| `script.py` | Entry point |
| `profiles/` | Niche YAML configs (sources, keywords, hashtags, persona) |
| `linkedin_bot/` | Bot package |
| `linkedin_bot/niche.py` | Profile loader |
| `linkedin_bot/discovery.py` | Topic / trend focus resolution |
| `linkedin_bot/sources/` | Feed fetchers |
| `linkedin_bot/generation/` | Multi-pass AI writing |
| `linkedin_bot/review.py` | Pre-publish niche + source gate |
| `.github/workflows/bot.yml` | Weekday timer + manual dispatch |

## Secrets

- `GROQ_API_KEY` — from [Groq](https://console.groq.com/)
- `LINKEDIN_TOKEN` — LinkedIn access token
- `LINKEDIN_PERSON_ID` — your LinkedIn person id

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
set GROQ_API_KEY=...
python script.py --dry-run --image
```

PowerShell:

```powershell
pip install -r requirements.txt
playwright install chromium
$env:GROQ_API_KEY = "..."
python script.py --dry-run --image
```

### Flags

| Flag | Env | Default | Description |
| --- | --- | --- | --- |
| `--dry-run` | `DRY_RUN` | off | Print post, do not publish |
| `--image` | `IMAGE` | off | Generate infographic |
| `--niche` | `NICHE` | `csharp-dotnet` | Profile id |
| `--topic` | `TOPIC` | empty | Manual focus; empty = trend mode |

Examples:

```powershell
# Default C#/.NET, auto trend
python script.py --dry-run

# Manual topic
python script.py --dry-run --topic "EF Core"

# Python niche
python script.py --dry-run --niche python --topic "async"
```

## Add a new niche

1. Copy `profiles/python.yaml` → `profiles/my_stack.yaml`
2. Set `id`, `display_name`, `relevance_keywords`, `hashtags`, `persona`, `sources`, `pulse_queries`
3. Run: `python script.py --dry-run --niche my-stack`

## GitHub Actions

Runs weekdays on cron. **Actions → Daily LinkedIn Post → Run workflow** supports optional `niche` and `topic` inputs.
