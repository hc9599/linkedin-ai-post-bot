"""
The daily run: find articles, write a post, clean it, publish.

Think of DailyPostBot as the conductor. It does not fetch Reddit itself —
it asks helpers to do each step.
"""
import argparse
import os

from linkedin_bot.cleaning import CleaningPipeline, cleaning_pipeline_for, strip_think_blocks
from linkedin_bot.config import env_flag
from linkedin_bot.discovery import fetch_pulse_titles, resolve_focus
from linkedin_bot.generation import PostGenerator
from linkedin_bot.generation.variance import LoopState, first_line, last_content_line
from linkedin_bot.llm import LLMClient, create_llm_client, resolve_provider_id
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
        llm: LLMClient,
        profile,
    ):
        self._aggregator = aggregator
        self._generator = generator
        self._cleaner = cleaner
        self._publisher = publisher
        self._llm = llm
        self._profile = profile

    def run(
        self,
        *,
        dry_run: bool,
        topic: str | None,
    ) -> None:
        if dry_run:
            print("*** DRY RUN MODE — post will NOT be published to LinkedIn ***\n")

        print(f"Niche: {self._profile.display_name} ({self._profile.id})")
        print(f"Audience mode: {self._profile.audience.mode}")
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

        state = LoopState.load()
        state.record(linkedin_content)
        state.record_closer(linkedin_content)
        print(f"Pass 4 — recorded opener: {first_line(linkedin_content)}")
        print(f"Pass 4 — recorded closer: {last_content_line(linkedin_content)}")

        if dry_run:
            print("\n*** DRY RUN — skipping LinkedIn publish ***")
            return

        print("\nPosting to LinkedIn...")
        self._publisher.publish(linkedin_content)


def compose(
    niche_id: str,
    *,
    focus_topic: str | None = None,
    llm_provider: str | None = None,
) -> DailyPostBot:
    """
    Plug the real services together for a niche profile.

    Swap sources by editing profiles/*.yaml without rewriting the bot.
    """
    profile = load_profile(niche_id)
    provider_id = resolve_provider_id(llm_provider)
    print(f"LLM provider: {provider_id}")
    llm: LLMClient = create_llm_client(provider_id)
    aggregator = SourceAggregator(build_sources(profile, focus_topic=focus_topic))
    return DailyPostBot(
        aggregator=aggregator,
        generator=PostGenerator(llm),
        cleaner=cleaning_pipeline_for(profile),
        publisher=LinkedInPublisher(),
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
        "--niche",
        default=os.environ.get("NICHE", "csharp-dotnet"),
        help="Niche profile id (default: csharp-dotnet).",
    )
    parser.add_argument(
        "--topic",
        default=os.environ.get("TOPIC", ""),
        help="Manual focus topic. Omit for auto trend discovery.",
    )
    parser.add_argument(
        "--llm-provider",
        default=os.environ.get("LLM_PROVIDER", ""),
        help="LLM backend: groq (default), openai, anthropic.",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or env_flag("DRY_RUN")
    topic = (args.topic or "").strip() or None
    llm_provider = (args.llm_provider or "").strip() or None

    compose(args.niche, focus_topic=topic, llm_provider=llm_provider).run(
        dry_run=dry_run,
        topic=topic,
    )
