"""
Ask Groq (the AI) to write text.

If the first model is gone (404), try the next one. That is why GitHub Actions
used to die when Groq retired llama / qwen — both names were hardcoded.
"""
import time
from typing import Protocol

from linkedin_bot.config import GROQ_API_URL, GROQ_MODELS, groq_api_key
from linkedin_bot.http import http_session


class LLMClient(Protocol):
    """Anything that can turn a prompt into a string. Groq is the real one today."""

    def complete(
        self,
        messages: list,
        *,
        temperature: float = 0.85,
        max_tokens: int = 800,
    ) -> str | None:
        ...


class GroqClient:
    """Calls Groq's chat API. Tries models in order until one answers."""

    def __init__(self, api_key: str | None = None, models: list[str] | None = None):
        self._api_key = api_key
        self._models = models if models is not None else list(GROQ_MODELS)

    def complete(
        self,
        messages: list,
        *,
        temperature: float = 0.85,
        max_tokens: int = 800,
    ) -> str | None:
        api_key = self._api_key if self._api_key is not None else groq_api_key()
        for model in self._models:
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": 0.92,
                    "frequency_penalty": 0.5,
                    "presence_penalty": 0.4,
                    "max_tokens": max_tokens,
                }
                reasoning_effort = self._reasoning_effort(model)
                if reasoning_effort is not None:
                    payload["reasoning_effort"] = reasoning_effort

                print(f"Groq: calling {model}...")
                started = time.monotonic()
                response = http_session().post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=20,
                )
                elapsed = time.monotonic() - started

                if response.status_code == 200:
                    raw = response.json()["choices"][0]["message"].get("content") or ""
                    content = raw.strip()
                    if not content:
                        print(
                            f"Groq: {model} empty after {elapsed:.1f}s "
                            "(thinking ate the tokens) — next model"
                        )
                        continue
                    print(f"Groq: using {model} ({elapsed:.1f}s)")
                    return content

                if response.status_code in (400, 404):
                    print(
                        f"Groq model {model} rejected ({response.status_code}) — trying next model"
                    )
                    continue

                print(
                    f"Groq [{model}] failed: {response.status_code} — {response.text[:120]}"
                )

            except Exception as e:
                print(f"Groq [{model}] exception: {e}")

        return None

    def _reasoning_effort(self, model: str) -> str | None:
        """
        How hard the model should "think" before writing.

        Groq is picky: Qwen wants none/default. GPT-OSS wants low/medium/high.
        Sending the wrong word returns 400, so we pick per family.
        """
        if "qwen" in model:
            return "none"
        if "gpt-oss" in model:
            return "low"
        return None
