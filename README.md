# LinkedIn AI post bot

A weekday helper that finds niche tech articles, writes an interactive LinkedIn post in a senior-developer voice, and can publish for you.

**Niche-configurable** — default is C# / .NET via `profiles/csharp_dotnet.yaml`. Add a YAML profile to target Python, Rust, or any stack without changing core code.

**LLM-configurable** — default provider is **Groq**. Switch to OpenAI or Anthropic Claude via `--llm-provider` or `LLM_PROVIDER`.

Posts are tuned for developer engagement: specific question closers, short mobile-friendly paragraphs, optional code snippets (C# profile).

Meant to run on **GitHub Actions**. Run locally first with `--dry-run` so nothing goes live.

## What it does

1. Loads a niche profile (`--niche`, default `csharp-dotnet`).
2. Reads recent posts from Reddit, dev.to, Hacker News, and RSS feeds defined in the profile.
3. **Manual topic** (`--topic "EF Core"`) or **auto trend** (LLM picks a hot trend from feeds, maps to niche angle).
4. Asks the configured LLM to write a LinkedIn post about one curated article — with a peer-level engagement closer.
5. Cleans markdown, emojis, and leftover notes; double-checks niche fit and source match.
6. Adds a Source line with title, site, and URL.
7. Posts text to LinkedIn — unless dry-run.

## Folders

| Path | What it is |
| --- | --- |
| `script.py` | Entry point |
| `profiles/` | Niche YAML configs (persona, sources, engagement closers) |
| `config/llm_providers.yaml` | LLM provider defaults (models, URLs) |
| `linkedin_bot/llm/` | OpenAI, Groq, Anthropic clients + factory |
| `linkedin_bot/niche.py` | Profile loader |
| `linkedin_bot/discovery.py` | Topic / trend focus resolution |
| `linkedin_bot/sources/` | Feed fetchers |
| `linkedin_bot/generation/` | Multi-pass AI writing + engagement closers |
| `linkedin_bot/review.py` | Pre-publish niche + source gate |
| `.github/workflows/bot.yml` | Weekday timer + manual dispatch |

## Secrets

Set the key for your chosen LLM provider plus LinkedIn:

| Provider | Secret | Get key |
| --- | --- | --- |
| Groq (default) | `GROQ_API_KEY` | [Groq console](https://console.groq.com/) |
| OpenAI | `OPENAI_API_KEY` | [OpenAI platform](https://platform.openai.com/) |
| Anthropic | `ANTHROPIC_API_KEY` | [Anthropic console](https://console.anthropic.com/) |

Always required for publish:

- `LINKEDIN_TOKEN`
- `LINKEDIN_PERSON_ID`

## Run locally

PowerShell:

```powershell
pip install -r requirements.txt
$env:GROQ_API_KEY = "gsk_..."
python script.py --dry-run
```

### Flags

| Flag | Env | Default | Description |
| --- | --- | --- | --- |
| `--dry-run` | `DRY_RUN` | off | Print post, do not publish |
| `--niche` | `NICHE` | `csharp-dotnet` | Profile id |
| `--topic` | `TOPIC` | empty | Manual focus; empty = trend mode |
| `--llm-provider` | `LLM_PROVIDER` | `groq` | `groq`, `openai`, or `anthropic` |

Optional model overrides:

- `LLM_MODEL` — single model id
- `LLM_MODELS` — comma-separated fallback list
- `LLM_BASE_URL` — override OpenAI API URL (proxies, Azure)

Examples:

```powershell
# Groq (default)
$env:GROQ_API_KEY = "gsk_..."
python script.py --dry-run

# OpenAI override
$env:OPENAI_API_KEY = "sk-..."
python script.py --dry-run --llm-provider openai

# Anthropic Claude
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python script.py --dry-run --llm-provider anthropic

# Custom OpenAI model
$env:LLM_MODEL = "gpt-4o"
python script.py --dry-run --llm-provider openai
```

## Engagement (profiles)

Add an `engagement:` block to any profile YAML:

```yaml
engagement:
  allow_code_snippet: true
  max_sentences_per_paragraph: 2
  closers:
    - "End with a specific A/B choice tied to the article."
```

See `profiles/csharp_dotnet.yaml` for the default C# tuning.

## Add a new niche

1. Copy `profiles/python.yaml` → `profiles/my_stack.yaml`
2. Set `id`, `display_name`, `relevance_keywords`, `hashtags`, `persona`, `sources`, `pulse_queries`
3. Optionally add `engagement:` closers
4. Run: `python script.py --dry-run --niche my-stack`

## GitHub Actions

Runs weekdays on cron. **Actions → Daily LinkedIn Post → Run workflow** supports optional `niche`, `topic`, and `llm_provider` inputs.

Add `GROQ_API_KEY` (and optionally `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) to repo secrets.
