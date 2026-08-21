# LinkedIn AI post bot

A weekday helper that finds a C# / .NET article, writes a LinkedIn post in a senior-developer voice, and can publish it for you.

It is meant to run on **GitHub Actions**. You can also run it on your laptop first with `--dry-run` so nothing goes live.

## What it does, in plain words

1. Reads recent posts from Reddit, dev.to, the Microsoft .NET blog, and Hacker News.
2. Picks a small mix of those articles.
3. Asks Groq (an AI service) to write a LinkedIn post about one of them.
4. Asks Groq again to clean up generic fluff.
5. Strips markdown, emojis, and leftover "thinking" notes.
6. Double-checks the post is actually about C# / .NET and matches the source article. If not, it **does not publish**.
7. Adds a Source line with the article title, site, and URL so readers can see where the take came from.
8. Optionally draws a picture.
9. Posts to LinkedIn — unless you used dry-run.

If one news site blocks GitHub's servers, the bot retries and tries a backup URL. The job should not die just because Reddit said 403.

## Folders

| Path | What it is |
| --- | --- |
| `script.py` | The doorbell. GitHub runs this. |
| `linkedin_bot/` | The actual bot. |
| `linkedin_bot/sources/` | Websites we read. |
| `linkedin_bot/generation/` | How the AI is asked to write. |
| `linkedin_bot/review.py` | Last check: credit the article, skip publish if it is not C#/.NET. |
| `.github/workflows/bot.yml` | The weekday timer. |

## Secrets (GitHub repo → Settings → Secrets and variables → Actions)

Set these three. Do not put them in the code.

- `GROQ_API_KEY` — from [Groq](https://console.groq.com/)
- `LINKEDIN_TOKEN` — LinkedIn access token
- `LINKEDIN_PERSON_ID` — your LinkedIn person id (the bit in `urn:li:person:...`)

## Run on your machine

```bash
pip install -r requirements.txt
set GROQ_API_KEY=...
python script.py --dry-run
```

On PowerShell:

```powershell
pip install -r requirements.txt
$env:GROQ_API_KEY = "..."
python script.py --dry-run
```

Flags:

- `--dry-run` — write the post, print it, do **not** publish
- `--image` — also try to generate a picture

Same switches as env vars: `DRY_RUN=true`, `IMAGE=true`.

## GitHub Actions

The workflow runs weekdays. You can also click **Actions → Daily LinkedIn Post → Run workflow**.

This branch is a feature branch. It is **not** merged to `main` by this change. Merge yourself when you are happy with a test run.

## If a source looks empty in the log

That usually means the site blocked the GitHub IP. The log will show `retry` and then a fallback (for Reddit, often **Arctic Shift**). Other sources still feed the mixer, so the bot can still write a post.
