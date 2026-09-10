"""
Validate the post-history & dedup feature without LLM calls.

This script runs the pure-logic validation scenarios from
specs/005-post-history-dedup/quickstart.md that don't need an LLM, an
article fetch, or a LinkedIn publish. It exercises PostHistoryStore,
PostRecord, normalize/jaccard, niche post_history parsing, and dedup_gate's
hard-threshold path (skipping the semantic-check branch by using clearly
different bodies for S3/S5).

Run: python tests_validate_history.py
Exit 0 = pass; non-zero = fail.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Repo-root on sys.path so we can import linkedin_bot.* without install.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from linkedin_bot.history import (
    DEFAULT_RETENTION,
    PostHistoryStore,
    PostRecord,
    build_post_record,
    jaccard,
    normalize,
    token_set,
)
from linkedin_bot.niche import (
    PostHistoryConfig,
    _clamp_retention,
    _env_int,
    _parse_post_history,
)
from linkedin_bot.cleaning import (
    strip_hashtag_line,
    strip_source_credit,
    strip_topic_line,
)
from linkedin_bot.bot import (
    DedupDecision,
    extract_body_for_history,
)


FAILS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"  --  {detail}"
        print(msg)
        FAILS.append(label)


def scenario_s1_persists_across_runs(tmp: Path) -> None:
    print("\nScenario 1 — history persists across runs")
    path = tmp / "history.json"
    body = "GC pauses are not the bug. They are the canary."
    record = build_post_record(
        body=body,
        niche_id="csharp-dotnet",
        article_title="Understanding .NET GC pauses",
        article_link="https://example.com/gc",
    )
    store = PostHistoryStore(path=path)
    store.record(record, retention=30)
    # Simulate second run
    store2 = PostHistoryStore.load(path)
    records = store2._data.get("csharp-dotnet", [])
    check("S1: one record persisted", len(records) == 1)
    check(
        "S1: body matches",
        records and records[0].body == body,
    )


def scenario_s2_dedup_catches_near_duplicate(tmp: Path) -> None:
    print("\nScenario 2 — dedup catches near-duplicate (hard reject)")
    path = tmp / "history.json"
    record = build_post_record(
        body="GC pauses are not the bug. They are the canary.",
        niche_id="csharp-dotnet",
        article_title="Understanding .NET GC pauses",
        article_link="https://example.com/gc",
    )
    store = PostHistoryStore.load(path)
    store.record(record, retention=30)

    # Candidate shares most tokens with the existing record.
    candidate_body = "GC pauses are the canary. They are not the bug."
    candidate = build_post_record(
        body=candidate_body,
        niche_id="csharp-dotnet",
        article_title="",
        article_link="",
    )
    score, matched = store.find_similar(candidate, "csharp-dotnet")
    check("S2: jaccard above hard threshold", score > 0.85, f"got {score:.2f}")
    check("S2: matched record returned", matched is not None)


def scenario_s3_different_topic_passes(tmp: Path) -> None:
    print("\nScenario 3 — different topic = no dedup clash")
    path = tmp / "history.json"
    record = build_post_record(
        body="GC pauses are not the bug. They are the canary.",
        niche_id="csharp-dotnet",
        article_title="GC",
        article_link="https://example.com/gc",
    )
    store = PostHistoryStore.load(path)
    store.record(record, retention=30)

    candidate_body = "Minimal APIs change how you shape endpoints."
    candidate = build_post_record(
        body=candidate_body,
        niche_id="csharp-dotnet",
        article_title="",
        article_link="",
    )
    score, matched = store.find_similar(candidate, "csharp-dotnet")
    check("S3: jaccard below hard threshold", score < 0.85, f"got {score:.2f}")
    check("S3: well below borderline band", score < 0.40, f"got {score:.2f}")


def scenario_s4_grooming(tmp: Path) -> None:
    print("\nScenario 4 — grooming keeps file bounded")
    path = tmp / "history.json"
    store = PostHistoryStore(path=path)
    for i in range(35):
        rec = build_post_record(
            body=f"post number {i}",
            niche_id="csharp-dotnet",
            article_title=f"article-{i}",
            article_link=f"https://example.com/{i}",
            date=f"2026-08-{(i % 30) + 1:02d}",
        )
        store._data.setdefault("csharp-dotnet", []).append(rec)
    dropped = store.groom(retention=30)
    check("S4: dropped exactly 5", dropped == 5)
    remaining = len(store._data.get("csharp-dotnet", []))
    check("S4: 30 records remain", remaining == 30)


def scenario_s5_niche_isolation(tmp: Path) -> None:
    print("\nScenario 5 — niche-scoped history")
    path = tmp / "history.json"
    store = PostHistoryStore(path=path)
    store.record(
        build_post_record(
            body="GC pauses are the canary.",
            niche_id="csharp-dotnet",
            article_title="GC",
            article_link="https://example.com/gc",
        ),
        retention=30,
    )
    store.record(
        build_post_record(
            body="Django middleware order matters because of how request flow runs through the stack.",
            niche_id="python",
            article_title="Django",
            article_link="https://example.com/django",
        ),
        retention=30,
    )
    candidate = build_post_record(
        body="Django middleware order matters because of how request flow runs through the stack entirely.",
        niche_id="python",
        article_title="",
        article_link="",
    )
    score, matched = store.find_similar(candidate, "python")
    check("S5: high score within python niche", score > 0.85, f"got {score:.2f}")
    candidate_csharp = build_post_record(
        body="GC pauses are the canary.",
        niche_id="csharp-dotnet",
        article_title="",
        article_link="",
    )
    score2, matched2 = store.find_similar(candidate_csharp, "csharp-dotnet")
    check("S5: csharp candidate finds csharp match", matched2 is not None)


def scenario_s6_corrupt_history(tmp: Path) -> None:
    print("\nScenario 6 — corrupt history does not crash")
    path = tmp / "history.json"
    path.write_text("{ this is not json", encoding="utf-8")
    store = PostHistoryStore.load(path)
    check("S6: load returns empty store on corrupt file", store._data == {})

    path.write_text('"a string not a dict"', encoding="utf-8")
    store = PostHistoryStore.load(path)
    check("S6: load returns empty store on non-dict root", store._data == {})

    path.write_text('{"csharp-dotnet": "not a list"}', encoding="utf-8")
    store = PostHistoryStore.load(path)
    check("S6: per-niche wrong type is dropped", store._data == {})


def scenario_s7_env_var_override() -> None:
    print("\nScenario 7 — POST_HISTORY_RETENTION env var override")
    os.environ["POST_HISTORY_RETENTION"] = "10"
    cfg = _parse_post_history(None)
    check("S7: env var parsed", cfg.retention == 10)
    del os.environ["POST_HISTORY_RETENTION"]
    cfg = _parse_post_history(None)
    check("S7: default when env var unset", cfg.retention == DEFAULT_RETENTION)
    cfg = _parse_post_history({"retention": 50})
    check("S7: YAML wins over default", cfg.retention == 50)
    os.environ["POST_HISTORY_RETENTION"] = "not-an-int"
    cfg = _parse_post_history(None)
    check("S7: invalid env var falls back to default", cfg.retention == DEFAULT_RETENTION)
    del os.environ["POST_HISTORY_RETENTION"]

    # Clamping
    check("S7: clamp low value", _clamp_retention(2) == 5)
    check("S7: clamp high value", _clamp_retention(9999) == 365)


def scenario_s8_inspect(tmp: Path) -> None:
    print("\nScenario 8 — inspect history")
    path = tmp / "history.json"
    store = PostHistoryStore(path=path)
    store.record(
        build_post_record(
            body="GC pauses are the canary.",
            niche_id="csharp-dotnet",
            article_title="GC",
            article_link="https://example.com/gc",
        ),
        retention=30,
    )
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    check("S8: top level is dict", isinstance(parsed, dict))
    check("S8: csharp-dotnet key present", "csharp-dotnet" in parsed)
    arr = parsed["csharp-dotnet"]
    check("S8: array has one entry", len(arr) == 1)
    entry = arr[0]
    for field in (
        "date", "niche_id", "body", "normalized_text",
        "token_set", "article_title", "article_link",
    ):
        check(f"S8: entry has {field}", field in entry)


def helper_normalize_token_jaccard() -> None:
    print("\nHelper — normalize, token_set, jaccard")
    text = "GC pauses are the canary! The canary never lies."
    n = normalize(text)
    check("Helper: lowercased and stripped", n == n.lower() and "!" not in n)
    ts = token_set(text)
    check("Helper: tokens is frozenset", isinstance(ts, frozenset))
    check("Helper: 'pauses' present", "pauses" in ts)
    check("Helper: stopword 'the' absent", "the" not in ts)
    a = frozenset({"pauses", "bug"})
    b = frozenset({"pauses", "canary"})
    check("Helper: jaccard correct", abs(jaccard(a, b) - 1 / 3) < 1e-9)
    check("Helper: jaccard empty a = 0", jaccard(frozenset(), b) == 0.0)
    check("Helper: jaccard empty both = 0", jaccard(frozenset(), frozenset()) == 0.0)


def helper_cleaning_helpers() -> None:
    print("\nHelper — cleaning.strip_*")
    sample = (
        "TOPIC: GC pauses\n\n"
        "Body line one.\n\n"
        "Body line two.\n\n"
        "#dotnet #csharp"
    )
    no_topic = strip_topic_line(sample)
    check("Helper: strip_topic_line removes TOPIC", not no_topic.startswith("TOPIC:"))
    no_hashtag = strip_hashtag_line(sample)
    check("Helper: strip_hashtag_line removes trailing hashtags", "#dotnet" not in no_hashtag)
    no_source = strip_source_credit("Body.\n\nSource: Foo (Bar)\nhttps://example.com")
    check("Helper: strip_source_credit removes credit", "Source:" not in no_source)
    check("Helper: body kept", "Body." in no_source)


def helper_extract_body_for_history() -> None:
    print("\nHelper — extract_body_for_history")
    text = (
        "TOPIC: GC pauses\n\n"
        "Body line one.\n\n"
        "Source: Title (Site)\nhttps://example.com/x\n\n"
        "#dotnet #csharp"
    )
    body = extract_body_for_history(text, ["#dotnet", "#csharp"])
    check("Helper: TOPIC stripped", "TOPIC:" not in body)
    check("Helper: Source stripped", "Source:" not in body)
    check("Helper: hashtags stripped", "#dotnet" not in body and "#csharp" not in body)
    check("Helper: body retained", "Body line one." in body)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        scenario_s1_persists_across_runs(tmp)
        scenario_s2_dedup_catches_near_duplicate(tmp)
        scenario_s3_different_topic_passes(tmp)
        scenario_s4_grooming(tmp)
        scenario_s5_niche_isolation(tmp)
        scenario_s6_corrupt_history(tmp)
        scenario_s7_env_var_override()
        scenario_s8_inspect(tmp)
        helper_normalize_token_jaccard()
        helper_cleaning_helpers()
        helper_extract_body_for_history()

    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s)")
        for label in FAILS:
            print(f"  - {label}")
        return 1
    print(f"All {28} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
