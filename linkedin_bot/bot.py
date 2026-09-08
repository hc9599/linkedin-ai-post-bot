"""
The daily run: find articles, write a post, clean it, maybe make an image, maybe publish.

Think of DailyPostBot as the conductor. It does not fetch Reddit itself —
it asks helpers to do each step.
"""
import argparse
import os
from datetime import datetime

from linkedin_bot.cleaning import CleaningPipeline, cleaning_pipeline_for, strip_think_blocks
from linkedin_bot.config import env_flag
from linkedin_bot.discovery import fetch_pulse_titles, resolve_focus
from linkedin_bot.generation import PostGenerator
from linkedin_bot.generation.variance import LoopState, first_line
from linkedin_bot.images import ImageService
from linkedin_bot.llm import GroqClient, LLMClient
from linkedin_bot.niche import load_profile
from linkedin_bot.publishing import LinkedInPublisher, Publisher
from linkedin_bot.review import attach_source_credit, review_before_publish
from linkedin_bot.sources import SourceAggregator, build_sources


class DailyPostBot:
    """Runs one full LinkedIn post from start to finish."""

    def __init__(
        self,
        aggregator: SourceAggregator,
        generator: PostGenerator,
        cleaner: CleaningPipeline,
        publisher: Publisher,
        image_service: ImageService,
        llm: LLMClient,
        profile,
    ):
        self._aggregator = aggregator
        self._generator = generator
        self._cleaner = cleaner
        self._publisher = publisher
        self._image_service = image_service
        self._llm = llm
        self._profile = profile

    def run(
        self,
        *,
        dry_run: bool,
        generate_image: bool,
        topic: str | None,
    ) -> None:
        if dry_run:
            print("*** DRY RUN MODE — post will NOT be published to LinkedIn ***\n")

        print(f"Niche: {self._profile.display_name} ({self._profile.id})")
        print(f"Fetching posts for {self._profile.display_name}...")
        posts = self._aggregator.fetch()

        if not posts:
            print("No posts fetched, exiting.")
            return

        pulse_titles: list[str] = []
        if not (topic and topic.strip()):
            pulse_titles = fetch_pulse_titles(self._profile)

        focus = resolve_focus(self._llm, self._profile, posts, pulse_titles, topic)

        print("\nRunning senior-dev generation loop...")
        linkedin_content = strip_think_blocks(
            self._generator.compose(posts, self._profile, focus)
        )
        print("\nDraft after loop:")
        print(linkedin_content)
        draft_with_topic = linkedin_content

        linkedin_content = self._cleaner.apply(linkedin_content)

        print(f"\nChecking {self._profile.display_name} fit and attaching the source article...")
        source, fail_reason = review_before_publish(
            self._llm,
            draft_with_topic,
            linkedin_content,
            posts,
            self._profile,
        )
        if fail_reason or source is None:
            print(f"ABORT: {fail_reason or 'no source matched'}")
            print("Not posting to LinkedIn.")
            return

        linkedin_content = attach_source_credit(linkedin_content, source)

        print("\n" + "=" * 60)
        print("FINAL POST:")
        print("=" * 60)
        print(linkedin_content)
        print("=" * 60)
        print(f"Character count: {len(linkedin_content)} / 3000")
        print(f"Word count: {len(linkedin_content.split())}")
        print(f"Source: {source.title}")
        print(f"Link: {source.link}")

        LoopState.load().record(linkedin_content)
        print(f"Pass 4 — recorded opener: {first_line(linkedin_content)}")

        image_bytes = None
        if generate_image:
            print("\nGenerating infographic strictly tied to the post...")
            image_bytes = self._image_service.generate(
                linkedin_content,
                profile=self._profile,
                source_title=source.title,
            )
        else:
            print("\nImage generation disabled (use --image to enable).")

        if dry_run:
            print("\n*** DRY RUN — skipping LinkedIn publish ***")
            if image_bytes:
                img_path = f"dry_run_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(img_path, "wb") as handle:
                    handle.write(image_bytes)
                print(f"Image saved locally for preview: {img_path}")
            return

        print("\nPosting to LinkedIn...")
        self._publisher.publish(linkedin_content, image_bytes)


def compose(niche_id: str, *, focus_topic: str | None = None) -> DailyPostBot:
    """
    Plug the real services together for a niche profile.

    Swap sources by editing profiles/*.yaml without rewriting the bot.
    """
    profile = load_profile(niche_id)
    llm: LLMClient = GroqClient()
    aggregator = SourceAggregator(build_sources(profile, focus_topic=focus_topic))
    return DailyPostBot(
        aggregator=aggregator,
        generator=PostGenerator(llm),
        cleaner=cleaning_pipeline_for(profile),
        publisher=LinkedInPublisher(),
        image_service=ImageService(llm),
        llm=llm,
        profile=profile,
    )


def main() -> None:
    """Read command-line flags (or env vars) and start one run."""
    parser = argparse.ArgumentParser(description="Generate and post a LinkedIn update.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print the post without publishing to LinkedIn.",
    )
    parser.add_argument(
        "--image",
        action="store_true",
        help="Generate and attach an image to the post (off by default).",
    )
    parser.add_argument(
        "--niche",
        default=os.environ.get("NICHE", "csharp-dotnet"),
        help="Niche profile id (default: csharp-dotnet).",
    )
    parser.add_argument(
        "--topic",
        default=os.environ.get("TOPIC", ""),
        help="Manual focus topic. Omit for auto trend discovery.",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or env_flag("DRY_RUN")
    generate_img = args.image or env_flag("IMAGE")
    topic = (args.topic or "").strip() or None

    compose(args.niche, focus_topic=topic).run(
        dry_run=dry_run,
        generate_image=generate_img,
        topic=topic,
    )
