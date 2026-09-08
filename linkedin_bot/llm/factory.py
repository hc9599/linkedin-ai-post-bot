"""Load provider config and construct LLM clients."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from linkedin_bot.llm.anthropic import AnthropicClient
from linkedin_bot.llm.openai_chat import OpenAIChatClient, groq_reasoning_effort
from linkedin_bot.llm.types import ApiStyle, LLMProviderConfig

_DEFAULT_PROVIDER = "groq"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _config_path() -> Path:
    return _repo_root() / "config" / "llm_providers.yaml"


def _parse_api_style(value: str) -> ApiStyle:
    if value == "openai_chat":
        return "openai_chat"
    if value == "anthropic_messages":
        return "anthropic_messages"
    raise ValueError(f"Unknown api_style: {value!r}")


def load_provider_configs() -> dict[str, LLMProviderConfig]:
    path = _config_path()
    if not path.is_file():
        raise FileNotFoundError(f"LLM provider config not found: {path}")

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid LLM config YAML in {path}")

    raw_providers = data.get("providers")
    if not isinstance(raw_providers, dict) or not raw_providers:
        raise ValueError(f"No providers defined in {path}")

    configs: dict[str, LLMProviderConfig] = {}
    for provider_id, entry in raw_providers.items():
        if not isinstance(entry, dict):
            continue
        models = entry.get("default_models") or []
        if not models:
            raise ValueError(f"Provider {provider_id!r} has no default_models")
        configs[str(provider_id)] = LLMProviderConfig(
            id=str(provider_id),
            api_style=_parse_api_style(str(entry["api_style"])),
            api_url=str(entry["api_url"]).strip(),
            env_key=str(entry["env_key"]).strip(),
            default_models=[str(m).strip() for m in models if str(m).strip()],
        )
    return configs


def list_llm_providers() -> list[str]:
    return sorted(load_provider_configs().keys())


def resolve_provider_id(cli_value: str | None = None) -> str:
    if cli_value and cli_value.strip():
        return cli_value.strip().lower()
    env = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if env:
        return env
    return _DEFAULT_PROVIDER


def resolve_models(config: LLMProviderConfig) -> list[str]:
    models_env = os.environ.get("LLM_MODELS", "").strip()
    if models_env:
        return [m.strip() for m in models_env.split(",") if m.strip()]
    single = os.environ.get("LLM_MODEL", "").strip()
    if single:
        return [single]
    return list(config.default_models)


def resolve_api_url(provider_id: str, config: LLMProviderConfig) -> str:
    if provider_id == "openai":
        override = os.environ.get("LLM_BASE_URL", "").strip()
        if override:
            return override
    return config.api_url


def _read_api_key(config: LLMProviderConfig) -> str:
    key = os.environ.get(config.env_key, "").strip()
    if not key:
        raise ValueError(f"{config.env_key} not set (required for provider {config.id!r})")
    return key


def create_llm_client(provider_id: str | None = None):
    resolved = resolve_provider_id(provider_id)
    configs = load_provider_configs()
    if resolved not in configs:
        allowed = ", ".join(sorted(configs)) or "(none)"
        raise ValueError(f"Unknown LLM provider {resolved!r}. Allowed: {allowed}")

    config = configs[resolved]
    api_key = _read_api_key(config)
    models = resolve_models(config)
    api_url = resolve_api_url(resolved, config)

    if config.api_style == "openai_chat":
        extra = None
        if resolved == "groq":
            def _groq_extra(model: str, payload: dict) -> None:
                effort = groq_reasoning_effort(model)
                if effort is not None:
                    payload["reasoning_effort"] = effort

            extra = _groq_extra
        return OpenAIChatClient(
            provider_id=resolved,
            api_url=api_url,
            api_key=api_key,
            models=models,
            extra_payload=extra,
        )

    if config.api_style == "anthropic_messages":
        return AnthropicClient(
            provider_id=resolved,
            api_url=api_url,
            api_key=api_key,
            models=models,
        )

    exhaustive: ApiStyle = config.api_style
    raise ValueError(f"Unhandled api_style: {exhaustive!r}")
