"""LLM provider configuration types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ApiStyle = Literal["openai_chat", "anthropic_messages"]


@dataclass(frozen=True)
class LLMProviderConfig:
    id: str
    api_style: ApiStyle
    api_url: str
    env_key: str
    default_models: list[str]
