"""Trending and daily-life hooks for the LinkedIn opener. Not article sources."""

from linkedin_bot.hooks.world import WorldHeadline, WorldHookSet, fetch_world_hooks

__all__ = ["WorldHeadline", "WorldHookSet", "fetch_world_hooks"]
