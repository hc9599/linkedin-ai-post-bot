"""
The daily run: find articles, write a post, clean it, publish.

Think of DailyPostBot as the conductor. It does not fetch Reddit itself —
it asks helpers to do each step.
"""
import argparse
import os
from enum import Enum
import re

from linkedin_bot.cleaning import (
    CleaningPipeline,
    cleaning_pipeline_for,
    strip_hashtag_line,
    strip_source_credit,
    strip_think_blocks,
    strip_topic_line,
)
from linkedin_bot.config import env_flag
from linkedin_bot.discovery import fetch_pulse_titles, resolve_focus
from linkedin_bot.generation import PostGenerator
from linkedin_bot.generation.variance import LoopState, first_line, last_content_line
from linkedin_bot.history import DEFAULT_HISTORY_PATH, PostHistoryStore, build_post_record
from linkedin_bot.llm import LLMClient, create_llm_client, resolve_provider_id
from linkedin_bot.models import CandidatePost
from linkedin_bot.niche import NicheProfile, load_profile
from linkedin_bot.publishing import LinkedInPublisher, Publisher
from linkedin_bot.review import (
    attach_source_credit,
    review_before_publish,
    semantic_context_check,
)
from linkedin_bot.sources import SourceAggregator, build_sources


class DedupDecision(str, Enum):
    """Outcome of the dedup gate for one draft."""
    PASS = "PASS"
    ROLL = "ROLL"
    ABORT = "ABORT"


_HARD_DUPLICATE_THRESHOLD = 0.85
_SEMANTIC_LOWER = 0.40


def extract_body_for_history(text: str, hashtags: list[str]) -> str:
    """Strip TOPIC, hashtags, and Source credit to return the body only.

    Used to build a PostRecord whose body is comparable across runs without
    noise from deterministic header, hashtag line, or source credit.
    """
    body = strip_topic_line(text or "")
    body = strip_source_credit(body)
    body = strip_hashtag_line(body)
    for tag in hashtags or []:
        body = body.replace(tag, "")
    return re.sub(r"\s+", " ", body).strip()


def dedup_gate(
    store: PostHistoryStore,
    candidate_body: str,
    niche_id: str,
    llm: LLMClient,
) -> DedupDecision:
    """Compare a candidate body against same-niche history.

    Returns PASS when the body is far enough from history to publish,
    ROLL when it should be regenerated, ABORT only when the caller
    decides this is the third strike.
    """
    candidate = build_post_record(
        body=candidate_body,
        niche_id=niche_id,
        article_title="",  # only used for storage; not relevant for similarity
        article_link="",
    )
    score, matched = store.find_similar(candidate, niche_id, threshold=_HARD_DUPLICATE_THRESHOLD)
    record_count = len(store._data.get(niche_id, []))  # internal but documented
    if record_count == 0:
        print(f"Dedup: pass (empty history for niche {niche_id})")
        return DedupDecision.PASS
    if score > _HARD_DUPLICATE_THRESHOLD:
        print(
            f"Dedup: jaccard={score:.2f} vs {matched.date if matched else 'no history'} — ROLL"
        )
        return DedupDecision.ROLL
    if score < _SEMANTIC_LOWER:
        print(f"Dedup: pass (max jaccard={score:.2f} vs {record_count} history records)")
        return DedupDecision.PASS
    # Borderline band — ask the LLM
    if matched is None:
        print(f"Dedup: pass (max jaccard={score:.2f} borderline but no record)")
        return DedupDecision.PASS
    verdict = semantic_context_check(llm, candidate_body, matched.body)
    if verdict == "NEW":
        print(
            f"Dedup: borderline jaccard={score:.2f} vs {matched.date} post — semantic check: NEW — PASS"
        )
        return DedupDecision.PASS
    print(
        f"Dedup: borderline jaccard={score:.2f} vs {matched.date} post — semantic check: {verdict} — ROLL"
    )
    return DedupDecision.ROLL


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
        history: PostHistoryStore | None = None,
    ):
        self._aggregator = aggregator
        self._generator = generator
        self._cleaner = cleaner
        self._publisher = publisher
        self._llm = llm
        self._profile = profile
        self._history = history or PostHistoryStore.load(DEFAULT_HISTORY_PATH)

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

        # Dedup gate: up to 2 re-rolls. On the third ROLL we abort the run.
        final_post, source, dedup_aborted = self._run_with_dedup(
            linkedin_content, posts, focus, source, dry_run
        )
        if dedup_aborted:
            print("Not posting to LinkedIn.")
            return

        print("\n" + "=" * 60)
        print("FINAL POST:")
        print("=" * 60)
        print(final_post)
        print("=" * 60)
        print(f"Character count: {len(final_post)} / 3000")
        print(f"Word count: {len(final_post.split())}")
        print(f"Source: {source.title}")
        print(f"Link: {source.link}")

        # Record into history only after dedup has decided we publish.
        body_for_history = extract_body_for_history(final_post, self._profile.hashtags)
        if body_for_history:
            record = build_post_record(
                body=body_for_history,
                niche_id=self._profile.id,
                article_title=source.title,
                article_link=source.link,
            )
            self._history.record(record, retention=self._profile.post_history.retention)
            print(f"History: recorded post for {self._profile.id} ({record.date})")
        else:
            print("History: post body empty after stripping — not recording")

        state = LoopState.load()
        state.record(final_post)
        state.record_closer(final_post)
        print(f"Pass 4 — recorded opener: {first_line(final_post)}")
        print(f"Pass 4 — recorded closer: {last_content_line(final_post)}")

        if dry_run:
            print("\n*** DRY RUN — skipping LinkedIn publish ***")
            return

        print("\nPosting to LinkedIn...")
        self._publisher.publish(final_post)

    def _run_with_dedup(
        self,
        initial_post: str,
        posts: list[CandidatePost],
        focus,
        source: CandidatePost,
        dry_run: bool,
        max_rolls: int = 2,
    ) -> tuple[str, CandidatePost, bool]:
        """Re-roll the post up to `max_rolls` times when dedup rejects.

        Returns (final_post, source, aborted). `aborted=True` means all attempts
        failed dedup — caller should skip publish and not record.
        """
        candidate = initial_post
        candidate_source = source
        for attempt in range(max_rolls + 1):
            body = extract_body_for_history(candidate, self._profile.hashtags)
            decision = dedup_gate(self._history, body, self._profile.id, self._llm)
            if decision == DedupDecision.PASS:
                return candidate, candidate_source, False
            if attempt == max_rolls:
                record_count = len(self._history._data.get(self._profile.id, []))
                print(
                    f"Dedup: ABORT — {max_rolls + 1} attempts all rolled "
                    f"(history: {record_count} records)"
                )
                return candidate, candidate_source, True
            # Re-roll: re-compose with exclude_titles forwarded to pick_article.
            exclude = list(self._history.recent_article_titles(self._profile.id, k=5))
            if candidate_source and candidate_source.title:
                exclude.insert(0, candidate_source.title)
            print(
                f"Dedup: re-roll attempt {attempt + 1}/{max_rolls} "
                f"(excluding {len(exclude)} article(s))"
            )
            try:
                candidate = strip_think_blocks(
                    self._generator.compose(
                        posts, self._profile, focus, exclude_titles=tuple(exclude)
                    )
                )
            except ValueError as exc:
                print(f"Dedup: ABORT — {exc}")
                return candidate, candidate_source, True
            candidate = self._cleaner.apply(candidate)
            new_source, new_fail = review_before_publish(
                self._llm,
                candidate,
                candidate,
                posts,
                self._profile,
            )
            if new_fail or new_source is None:
                print(f"Dedup: re-roll review failed — {new_fail or 'no source matched'}")
                continue
            candidate_source = new_source
            candidate = attach_source_credit(candidate, candidate_source)
        return candidate, candidate_source, True


def compose(
    niche_id: str,
    *,
    focus_topic: str | None = None,
    llm_provider: str | None = None,
    history: PostHistoryStore | None = None,
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
        history=history,
    )


def prune_history(profile: NicheProfile) -> int:
    """Run a manual groom on the profile's history store. Returns records dropped."""
    store = PostHistoryStore.load(DEFAULT_HISTORY_PATH)
    dropped = store.groom(profile.post_history.retention)
    print(
        f"Prune: dropped {dropped} record(s); retention={profile.post_history.retention}"
    )
    return dropped


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
    parser.add_argument(
        "--prune-history",
        action="store_true",
        help="Trim post history to the retention limit and exit.",
    )
    args = parser.parse_args()

    if args.prune_history:
        profile = load_profile(args.niche)
        prune_history(profile)
        return

    dry_run = args.dry_run or env_flag("DRY_RUN")
    topic = (args.topic or "").strip() or None
    llm_provider = (args.llm_provider or "").strip() or None

    compose(args.niche, focus_topic=topic, llm_provider=llm_provider).run(
        dry_run=dry_run,
        topic=topic,
    )
