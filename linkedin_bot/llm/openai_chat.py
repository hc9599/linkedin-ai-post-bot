"""OpenAI-compatible chat completions client (OpenAI + Groq)."""
from __future__ import annotations

import time
from collections.abc import Callable

from linkedin_bot.http import http_session


def groq_reasoning_effort(model: str) -> str | None:
    """Groq-specific reasoning_effort for gpt-oss / qwen model families."""
    if "qwen" in model:
        return "none"
    if "gpt-oss" in model:
        return "low"
    return None


class OpenAIChatClient:
    """POST chat/completions; try models in order with retries."""

    def __init__(
        self,
        *,
        provider_id: str,
        api_url: str,
        api_key: str,
        models: list[str],
        extra_payload: Callable[[str, dict], None] | None = None,
    ):
        self._provider_id = provider_id
        self._api_url = api_url
        self._api_key = api_key
        self._models = models
        self._extra_payload = extra_payload

    def complete(
        self,
        messages: list,
        *,
        temperature: float = 0.85,
        max_tokens: int = 800,
    ) -> str | None:
        for model in self._models:
            for attempt in range(3):
                try:
                    payload: dict = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "top_p": 0.92,
                        "frequency_penalty": 0.5,
                        "presence_penalty": 0.4,
                        "max_tokens": max_tokens,
                    }
                    if self._extra_payload is not None:
                        self._extra_payload(model, payload)

                    response = http_session().post(
                        self._api_url,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=60,
                    )

                    if response.status_code == 200:
                        print(f"LLM [{self._provider_id}] using model {model}")
                        return response.json()["choices"][0]["message"]["content"].strip()

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
