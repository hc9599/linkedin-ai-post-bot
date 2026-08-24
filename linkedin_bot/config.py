"""
Settings and secrets.

Nothing secret lives in this file. Keys come from environment variables
(GitHub Actions secrets, or your local machine).
"""
import os

# Groq is the AI service that writes the LinkedIn post.
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Fast model first. 120b thinks so long that Actions looks stuck.
GROQ_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
# Pretend to be a normal Chrome browser. Sites block "bot" names from GitHub servers.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
REQUIRED_HASHTAGS = "#CSharp #DotNet #Programming #SoftwareDevelopment"
HASHTAGS = ["#CSharp", "#DotNet", "#Programming", "#SoftwareDevelopment"]


def groq_api_key() -> str:
    """Read the Groq password/key. Fail early if someone forgot to set it."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not set")
    return key


def linkedin_credentials() -> tuple[str, str]:
    """Read LinkedIn login pieces. Need both token and person id to post."""
    token = os.environ.get("LINKEDIN_TOKEN")
    person_id = os.environ.get("LINKEDIN_PERSON_ID")
    if not token or not person_id:
        raise ValueError("LinkedIn credentials not set")
    return token, person_id


def env_flag(name: str) -> bool:
    """Treat 1 / true / yes as on. Used for DRY_RUN and IMAGE switches."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
