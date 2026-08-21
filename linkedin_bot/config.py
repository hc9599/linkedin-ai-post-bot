import os

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
# Browser UA: GitHub Actions datacenter IPs get Cloudflare/Reddit 403 on bot UAs.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
REQUIRED_HASHTAGS = "#CSharp #DotNet #Programming #SoftwareDevelopment"
HASHTAGS = ["#CSharp", "#DotNet", "#Programming", "#SoftwareDevelopment"]


def groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not set")
    return key


def linkedin_credentials() -> tuple[str, str]:
    token = os.environ.get("LINKEDIN_TOKEN")
    person_id = os.environ.get("LINKEDIN_PERSON_ID")
    if not token or not person_id:
        raise ValueError("LinkedIn credentials not set")
    return token, person_id


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
