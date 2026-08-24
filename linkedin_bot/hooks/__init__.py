"""Trending and daily-life hooks for the LinkedIn opener. Not article sources."""

from linkedin_bot.hooks.world import (
    DAY_VIBES,
    WorldHeadline,
    WorldHookSet,
    current_day_context,
    fetch_world_hooks,
)

__all__ = [
    "DAY_VIBES",
    "WorldHeadline",
    "WorldHookSet",
    "current_day_context",
    "fetch_world_hooks",
]
