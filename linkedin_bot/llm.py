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
            for attempt in range(3):
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

                    response = http_session().post(
                        GROQ_API_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=30,
                    )

                    if response.status_code == 200:
                        print(f"Groq: using model {model}")
                        return response.json()["choices"][0]["message"]["content"].strip()

                    # 400/404 means "this model name is wrong" — skip to the next model.
                    if response.status_code in (400, 404):
                        print(
                            f"Groq model {model} rejected ({response.status_code}) — trying next model"
                        )
                        break

                    print(
                        f"Groq [{model}] attempt {attempt + 1} failed: "
                        f"{response.status_code} — {response.text[:120]}"
                    )

                except Exception as e:
                    print(f"Groq [{model}] attempt {attempt + 1} exception: {e}")

                time.sleep(2 ** attempt)

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
