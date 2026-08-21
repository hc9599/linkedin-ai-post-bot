import argparse
from datetime import datetime

from linkedin_bot.cleaning import default_cleaning_pipeline, strip_think_blocks, CleaningPipeline
from linkedin_bot.config import env_flag
from linkedin_bot.generation import PostGenerator
from linkedin_bot.images import ImageService, PollinationsImageRenderer
from linkedin_bot.llm import GroqClient, LLMClient
from linkedin_bot.publishing import LinkedInPublisher, Publisher
from linkedin_bot.sources import SourceAggregator
from linkedin_bot.sources.devto import DevToSource
from linkedin_bot.sources.hackernews import HackerNewsSource
from linkedin_bot.sources.microsoft_blog import MicrosoftBlogSource
from linkedin_bot.sources.reddit import RedditSource


class DailyPostBot:
    """Facade: fetch → draft → critique → clean → optional image → publish."""

    def __init__(
        self,
        aggregator: SourceAggregator,
        generator: PostGenerator,
        cleaner: CleaningPipeline,
        publisher: Publisher,
        image_service: ImageService,
    ):
        self._aggregator = aggregator
        self._generator = generator
        self._cleaner = cleaner
        self._publisher = publisher
        self._image_service = image_service

    def run(self, *, dry_run: bool, generate_image: bool) -> None:
        if dry_run:
            print("*** DRY RUN MODE — post will NOT be published to LinkedIn ***\n")

        print("Fetching posts from Reddit, dev.to, and .NET Dev Blog...")
        posts = self._aggregator.fetch()

        if not posts:
            print("No posts fetched, exiting.")
            return

        print("\nGenerating LinkedIn post (first pass)...")
        linkedin_content = self._generator.draft(posts)

        linkedin_content = strip_think_blocks(linkedin_content)
        print("\nDraft (cleaned):")
        print(linkedin_content)

        print("\nRunning self-critique pass...")
        linkedin_content = self._generator.critique(linkedin_content)

        linkedin_content = self._cleaner.apply(linkedin_content)

        print("\n" + "=" * 60)
        print("FINAL POST:")
        print("=" * 60)
        print(linkedin_content)
        print("=" * 60)
        print(f"Character count: {len(linkedin_content)} / 3000")
        print(f"Word count: {len(linkedin_content.split())}")

        image_bytes = None
        if generate_image:
            print("\nGenerating image prompt...")
            image_bytes = self._image_service.generate(linkedin_content)
        else:
            print("\nImage generation disabled (use --image to enable).")

        if dry_run:
            print("\n*** DRY RUN — skipping LinkedIn publish ***")
            if image_bytes:
                img_path = f"dry_run_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                print(f"Image saved locally for preview: {img_path}")
            return

        print("\nPosting to LinkedIn...")
        self._publisher.publish(linkedin_content, image_bytes)


def compose() -> DailyPostBot:
    llm: LLMClient = GroqClient()
    aggregator = SourceAggregator([
        RedditSource(),
        DevToSource(),
        MicrosoftBlogSource(),
        HackerNewsSource(),
    ])
    return DailyPostBot(
        aggregator=aggregator,
        generator=PostGenerator(llm),
        cleaner=default_cleaning_pipeline(),
        publisher=LinkedInPublisher(),
        image_service=ImageService(llm, PollinationsImageRenderer()),
    )


def main() -> None:
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
    args = parser.parse_args()

    dry_run = args.dry_run or env_flag("DRY_RUN")
    generate_img = args.image or env_flag("IMAGE")
    compose().run(dry_run=dry_run, generate_image=generate_img)
