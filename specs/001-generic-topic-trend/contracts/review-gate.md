# Contract: Review Gate

**Version**: 1.0  
**Feature**: 001-generic-topic-trend

## Entry

```python
def review_before_publish(
    llm: LLMClient,
    draft_with_topic: str,
    cleaned_post: str,
    candidates: list[CandidatePost],
    profile: NicheProfile,
) -> tuple[CandidatePost | None, str | None]: ...
```

Returns `(source, None)` on pass; `(None, reason)` on abort.

## Checks (unchanged order, profile-driven labels)

1. **Source match** — `match_source(topic, candidates, body)` (unchanged logic)
2. **Keyword pre-check** — `is_relevant(body, source.title + source.summary, profile.relevance_keywords)`; log warning if weak, still run LLM
3. **Reject list** — `reject_hits(cleaned_post)` (unchanged)
4. **First-person claim** — `first_person_subject_claim(body, source)` (unchanged)
5. **Hashtag allowlist** — only tags in `profile.hashtags`
6. **Word count** — `MAX_POST_WORDS` (unchanged)
7. **LLM niche check** — `llm_niche_source_check(llm, post, source, profile)`

## llm_niche_source_check

Replaces `llm_dotnet_source_check`. Prompt MUST use:

- `profile.review_niche_label` instead of hardcoded "C# and/or .NET"
- Same PASS/FAIL line format and first-person / opener rules

```python
def llm_niche_source_check(
    llm: LLMClient,
    post_text: str,
    source: CandidatePost,
    profile: NicheProfile,
) -> tuple[bool, str]: ...
```

## attach_source_credit

Unchanged — appends `Source: {title} ({source})\n{link}` above hashtags.
