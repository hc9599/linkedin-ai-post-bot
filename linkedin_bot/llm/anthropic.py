"""Anthropic Messages API client."""
from __future__ import annotations

import time

from linkedin_bot.http import http_session


class AnthropicClient:
    """Maps LLMClient messages to Anthropic /v1/messages."""

    def __init__(
        self,
        *,
        provider_id: str,
        api_url: str,
        api_key: str,
        models: list[str],
    ):
        self._provider_id = provider_id
        self._api_url = api_url
        self._api_key = api_key
        self._models = models

    def complete(
        self,
        messages: list,
        *,
        temperature: float = 0.85,
        max_tokens: int = 800,
    ) -> str | None:
        system_parts = [
            str(m.get("content", ""))
            for m in messages
            if m.get("role") == "system" and m.get("content")
        ]
        system = "\n\n".join(system_parts) if system_parts else None

        api_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        if not api_messages:
            return None

        for model in self._models:
            for attempt in range(3):
                try:
                    payload: dict = {
                        "model": model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": api_messages,
                    }
                    if system:
                        payload["system"] = system

                    response = http_session().post(
                        self._api_url,
                        headers={
                            "x-api-key": self._api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=60,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        blocks = data.get("content") or []
                        if blocks and blocks[0].get("text"):
                            print(f"LLM [{self._provider_id}] using model {model}")
                            return str(blocks[0]["text"]).strip()
                        print(f"LLM [{self._provider_id}] empty content from {model}")
                        break

                    if response.status_code in (400, 404):
                        print(
                            f"LLM [{self._provider_id}] model {model} rejected "
                            f"({response.status_code}) — trying next model"
                        )
                        break

                    print(
                        f"LLM [{self._provider_id}] [{model}] attempt {attempt + 1} failed: "
                        f"{response.status_code} — {response.text[:120]}"
                    )

                except Exception as exc:
                    print(
                        f"LLM [{self._provider_id}] [{model}] attempt {attempt + 1} "
                        f"exception: {exc}"
                    )

                time.sleep(2 ** attempt)

        return None
