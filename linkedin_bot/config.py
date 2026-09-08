"""
Settings and secrets.

Nothing secret lives in this file. Keys come from environment variables
(GitHub Actions secrets, or your local machine).
"""
import os

# Pretend to be a normal Chrome browser. Sites block "bot" names from GitHub servers.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


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
