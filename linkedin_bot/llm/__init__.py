"""LLM provider abstraction — OpenAI, Groq, Anthropic."""
from typing import Protocol

from linkedin_bot.llm.factory import create_llm_client, list_llm_providers, resolve_provider_id


class LLMClient(Protocol):
    """Anything that can turn a chat messages list into assistant text."""

    def complete(
        self,
        messages: list,
        *,
        temperature: float = 0.85,
        max_tokens: int = 800,
    ) -> str | None:
        ...


__all__ = [
    "LLMClient",
    "create_llm_client",
    "list_llm_providers",
    "resolve_provider_id",
]
