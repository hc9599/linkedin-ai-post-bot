"""
Load niche profiles from YAML files in profiles/.

Each profile defines sources, keywords, hashtags, persona, and review labels
for a specific technology stack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Literal

import yaml

_ALLOWED_CODE_LANGUAGES = frozenset({"csharp", "python", "plain"})
_ALLOWED_AUDIENCE_MODES = frozenset({"peers", "mixed", "business"})
AudienceMode = Literal["peers", "mixed", "business"]

_DEFAULT_MIXED_CLOSERS = (
    "End with a team or hiring tradeoff question a manager could answer — tie it to the article.",
    "End asking whether this changes how they'd evaluate seniority on a team.",
    "End with a delivery-risk vs speed question in plain English — no syntax choices.",
)


@dataclass(frozen=True)
class RssFeedEntry:
    name: str
    urls: list[str]


@dataclass(frozen=True)
class SourceConfig:
    reddit_subreddits: list[str] = field(default_factory=list)
    devto_tags: list[str] = field(default_factory=list)
    hn_queries: list[str] = field(default_factory=list)
    rss_feeds: list[RssFeedEntry] = field(default_factory=list)


@dataclass(frozen=True)
class WeekdayAngle:
    focus: str
    audience_signal: str
    avoid: str


_DEFAULT_ENGAGEMENT_CLOSERS = (
    "End with one specific question a developer in this niche would answer in one line.",
)


@dataclass(frozen=True)
class EngagementConfig:
    closers: tuple[str, ...]
    allow_code_snippet: bool
    max_sentences_per_paragraph: int


def _default_audience_config() -> "AudienceConfig":
    return AudienceConfig(
        mode="mixed",
        closers=_DEFAULT_MIXED_CLOSERS,
        jargon_policy="explain_on_first_use",
        lead_with="impact",
    )


@dataclass(frozen=True)
class AudienceConfig:
    mode: AudienceMode
    closers: tuple[str, ...]
    jargon_policy: str
    lead_with: str


@dataclass(frozen=True)
class PostHistoryConfig:
    """Per-niche overrides for the post-history dedup store."""
    retention: int = 30


_MIN_RETENTION = 5
_MAX_RETENTION = 365


def _env_int(name: str, default: int) -> int:
    """Read an int env var, returning `default` on any parse error."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        print(f"WARNING: {name}={raw!r} is not an int — using default {default}")
        return default


def _clamp_retention(value: int) -> int:
    if value < _MIN_RETENTION:
        print(f"WARNING: post_history.retention {value} too low — clamping to {_MIN_RETENTION}")
        return _MIN_RETENTION
    if value > _MAX_RETENTION:
        print(f"WARNING: post_history.retention {value} too high — clamping to {_MAX_RETENTION}")
        return _MAX_RETENTION
    return value


@dataclass(frozen=True)
class NicheProfile:
    id: str
    display_name: str
    relevance_keywords: list[str]
    hashtags: list[str]
    persona: str
    review_niche_label: str
    weekday_angles: dict[int, WeekdayAngle]
    sources: SourceConfig
    pulse_queries: list[str]
    code_language: str
    default_angle: str = ""
    engagement: EngagementConfig = field(
        default_factory=lambda: EngagementConfig(
            closers=_DEFAULT_ENGAGEMENT_CLOSERS,
            allow_code_snippet=False,
            max_sentences_per_paragraph=2,
        )
    )
    audience: AudienceConfig = field(default_factory=_default_audience_config)
    post_history: PostHistoryConfig = field(
        default_factory=lambda: PostHistoryConfig(retention=_env_int("POST_HISTORY_RETENTION", 30))
    )

    @property
    def required_hashtags_line(self) -> str:
        return " ".join(self.hashtags)


def active_closers(profile: NicheProfile) -> tuple[str, ...]:
    if profile.audience.mode == "peers":
        return profile.engagement.closers
    if profile.audience.closers:
        return profile.audience.closers
    return _DEFAULT_MIXED_CLOSERS


def allows_code_snippet(profile: NicheProfile) -> bool:
    return profile.audience.mode == "peers" and profile.engagement.allow_code_snippet


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _profiles_dir() -> Path:
    return _repo_root() / "profiles"


def _niche_id_to_filename(niche_id: str) -> str:
    return niche_id.strip().lower().replace("-", "_")


def list_profiles() -> list[str]:
    """Return available niche ids derived from profiles/*.yaml filenames."""
    directory = _profiles_dir()
    if not directory.is_dir():
        return []
    ids: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        ids.append(path.stem.replace("_", "-"))
    return ids


def _parse_weekday_angles(raw: dict[str, Any] | None) -> dict[int, WeekdayAngle]:
    angles: dict[int, WeekdayAngle] = {}
    if not raw:
        return angles
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            day = int(key)
        except (TypeError, ValueError):
            continue
        focus = str(value.get("focus") or "").strip()
        audience = str(value.get("audience_signal") or "").strip()
        avoid = str(value.get("avoid") or "").strip()
        if focus:
            angles[day] = WeekdayAngle(
                focus=focus,
                audience_signal=audience,
                avoid=avoid,
            )
    return angles


def _parse_audience_mode(value: str) -> AudienceMode:
    mode = value.strip().lower()
    if mode not in _ALLOWED_AUDIENCE_MODES:
        allowed = ", ".join(sorted(_ALLOWED_AUDIENCE_MODES))
        raise ValueError(f"Invalid audience.mode {value!r}; allowed: {allowed}")
    return mode  # type: ignore[return-value]


def _parse_audience(raw: dict[str, Any] | None) -> AudienceConfig:
    default = _default_audience_config()
    if not raw or not isinstance(raw, dict):
        return default

    mode_raw = str(raw.get("mode") or default.mode)
    mode = _parse_audience_mode(mode_raw)

    closers_raw = raw.get("closers")
    closers: tuple[str, ...] = default.closers
    if isinstance(closers_raw, list) and closers_raw:
        parsed = tuple(str(item).strip() for item in closers_raw if str(item).strip())
        if parsed:
            closers = parsed

    jargon_policy = str(raw.get("jargon_policy") or default.jargon_policy).strip()
    if mode == "business" and jargon_policy == default.jargon_policy:
        jargon_policy = "minimal_jargon"

    lead_with = str(raw.get("lead_with") or default.lead_with).strip()
    if lead_with not in {"impact", "story", "takeaway"}:
        lead_with = default.lead_with

    return AudienceConfig(
        mode=mode,
        closers=closers,
        jargon_policy=jargon_policy,
        lead_with=lead_with,
    )


def _parse_post_history(raw: dict[str, Any] | None) -> PostHistoryConfig:
    env_default = _env_int("POST_HISTORY_RETENTION", 30)
    if not raw or not isinstance(raw, dict):
        return PostHistoryConfig(retention=env_default)
    retention_raw = raw.get("retention", env_default)
    try:
        retention = int(retention_raw)
    except (TypeError, ValueError):
        print(f"WARNING: post_history.retention {retention_raw!r} is not an int — using default {env_default}")
        retention = env_default
    return PostHistoryConfig(retention=_clamp_retention(retention))


def _parse_engagement(raw: dict[str, Any] | None) -> EngagementConfig:
    default = EngagementConfig(
        closers=_DEFAULT_ENGAGEMENT_CLOSERS,
        allow_code_snippet=False,
        max_sentences_per_paragraph=2,
    )
    if not raw or not isinstance(raw, dict):
        return default

    closers_raw = raw.get("closers")
    closers: tuple[str, ...] = default.closers
    if isinstance(closers_raw, list) and closers_raw:
        parsed = tuple(str(item).strip() for item in closers_raw if str(item).strip())
        if parsed:
            closers = parsed

    max_sentences = raw.get("max_sentences_per_paragraph", default.max_sentences_per_paragraph)
    try:
        max_sentences = int(max_sentences)
    except (TypeError, ValueError):
        max_sentences = default.max_sentences_per_paragraph
    max_sentences = max(1, min(4, max_sentences))

    allow_code = bool(raw.get("allow_code_snippet", default.allow_code_snippet))
    return EngagementConfig(
        closers=closers,
        allow_code_snippet=allow_code,
        max_sentences_per_paragraph=max_sentences,
    )


def _parse_sources(raw: dict[str, Any] | None) -> SourceConfig:
    if not raw:
        return SourceConfig()
    rss_raw = raw.get("rss_feeds") or []
    rss_feeds: list[RssFeedEntry] = []
    for entry in rss_raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        urls = [str(u).strip() for u in (entry.get("urls") or []) if str(u).strip()]
        if name and urls:
            rss_feeds.append(RssFeedEntry(name=name, urls=urls))
    return SourceConfig(
        reddit_subreddits=[str(s).strip() for s in (raw.get("reddit_subreddits") or []) if str(s).strip()],
        devto_tags=[str(t).strip() for t in (raw.get("devto_tags") or []) if str(t).strip()],
        hn_queries=[str(q).strip() for q in (raw.get("hn_queries") or []) if str(q).strip()],
        rss_feeds=rss_feeds,
    )


def _require_str(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"Profile missing required field: {key}")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[str]:
    raw = data.get(key)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Profile missing required non-empty list: {key}")
    return [str(item).strip() for item in raw if str(item).strip()]


def load_profile(niche_id: str) -> NicheProfile:
    """Load and validate a niche profile by CLI id (e.g. csharp-dotnet)."""
    stem = _niche_id_to_filename(niche_id)
    path = _profiles_dir() / f"{stem}.yaml"
    if not path.is_file():
        available = ", ".join(list_profiles()) or "(none)"
        raise FileNotFoundError(
            f"Niche profile not found: {niche_id} (expected {path}). "
            f"Available: {available}"
        )

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid profile YAML in {path}")

    code_language = _require_str(data, "code_language").lower()
    if code_language not in _ALLOWED_CODE_LANGUAGES:
        allowed = ", ".join(sorted(_ALLOWED_CODE_LANGUAGES))
        raise ValueError(f"Invalid code_language {code_language!r}; allowed: {allowed}")

    hashtags = _require_list(data, "hashtags")
    for tag in hashtags:
        if not tag.startswith("#"):
            raise ValueError(f"Hashtag must start with #: {tag!r}")

    display_name = _require_str(data, "display_name")
    default_angle = str(data.get("default_angle") or "").strip()
    if not default_angle:
        default_angle = f"Write for {display_name} peers about this topic."

    return NicheProfile(
        id=str(data.get("id") or niche_id).strip(),
        display_name=display_name,
        relevance_keywords=_require_list(data, "relevance_keywords"),
        hashtags=hashtags,
        persona=_require_str(data, "persona"),
        review_niche_label=_require_str(data, "review_niche_label"),
        weekday_angles=_parse_weekday_angles(data.get("weekday_angles")),
        sources=_parse_sources(data.get("sources")),
        pulse_queries=_require_list(data, "pulse_queries"),
        code_language=code_language,
        default_angle=default_angle,
        engagement=_parse_engagement(data.get("engagement")),
        audience=_parse_audience(data.get("audience")),
        post_history=_parse_post_history(data.get("post_history")),
    )
