"""
Optional picture for the post.

We ask Groq for a short image description, then Pollinations draws it.
If either step fails, the LinkedIn post still goes out as text.
"""
import urllib.parse
from typing import Protocol

from linkedin_bot.http import get_with_retry
from linkedin_bot.llm import LLMClient


class ImageRenderer(Protocol):
    """Anything that can turn an English prompt into image bytes."""
    def render(self, prompt: str) -> bytes | None:
        ...


class PollinationsImageRenderer:
    """Free image site. No API key. Can be slow or fail; that is OK."""

    def render(self, prompt: str) -> bytes | None:
        encoded = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1200&height=627&nologo=true&enhance=true&model=flux"
        )

        print(f"Generating image with prompt: {prompt}")
        print("Waiting for image generation (this can take 15-30s)...")

        response = get_with_retry(url, timeout=60, attempts=4)
        if (
            response is not None
            and response.status_code == 200
            and response.headers.get("content-type", "").startswith("image")
        ):
            print(f"Image generated — {len(response.content) // 1024}KB")
            return response.content
        status = response.status_code if response is not None else "no response"
        print(f"Image generation failed: {status}")
        return None


class ImageService:
    """Ask the AI for a picture idea, then ask Pollinations to draw it."""
    def __init__(self, llm: LLMClient, renderer: ImageRenderer):
        self._llm = llm
        self._renderer = renderer

    def generate_prompt(self, post_content: str) -> str | None:
        system = (
            "You generate image prompts for LinkedIn tech posts. "
            "Output only the image prompt — no explanation, no preamble, no quotes. "
            "Style: clean flat illustration, dark background, subtle code or tech motif. "
            "No people, no faces, no text in the image. "
            "Keep it abstract and professional — suitable for a developer's LinkedIn post."
        )
        user = (
            f"Based on this LinkedIn post, write a short image generation prompt (max 30 words):\n\n"
            f"{post_content}"
        )
        return self._llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            max_tokens=80,
        )

    def generate(self, post_content: str) -> bytes | None:
        image_prompt = self.generate_prompt(post_content)
        if not image_prompt:
            print("Could not generate image prompt — skipping image.")
            return None
        print(f"Image prompt: {image_prompt}")
        return self._renderer.render(image_prompt)
