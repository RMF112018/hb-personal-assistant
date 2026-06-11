You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-email-followup-candidate-projection-package/`

Before doing anything else:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main` or if unexplained dirty files are present.

Hard safety constraints:

- Do not mutate the production DB.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Use `/tmp` DB copies for apply validation.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.

# 03 — Deterministic Candidate Extractor

## Objective

Implement the deterministic extractor before any model-assisted behavior.

## Implementation Guidance

Create a focused module unless repo truth indicates an existing better home, for example:

`src/hb_assistant/construction/second_brain/local_ai/email_followup_candidate_projection.py`

Core functions should be small and testable:

- `build_email_followup_candidates(...)`
- `extract_email_followup_candidates_from_structured(...)`
- `classify_thread_followup(...)`
- `classify_message_followup(...)`
- `bounded_redacted_title(...)`
- `bounded_redacted_reason(...)`
- `candidate_key_for(...)`

Prefer structured read models and structured tables:

- `email_raw_message_structured`
- `email_raw_thread_structured`
- `email_raw_thread_messages_structured`
- recipient/attachment child counts, not full arrays
- `EmailMessageContext`
- `ThreadContext`

## Deterministic Signals

Use only safe signals unless audited raw access is unavoidable:

- source tier/source quality
- project key
- thread ref
- conversation hash
- message hash
- from domain
- recipient count
- attachment count
- message count
- participant count
- sent/received timestamps
- body availability flags and char counts
- safe bounded subject if repository already permits it in structured read models
- safe attachment metadata counts/names only if bounded/redacted
- existing project identity matches/review queue outputs

## Raw Body Rule

Do not use body text for the first pass unless the schema/read-model audit proves structured metadata is insufficient for the selected candidate family.

If raw body access is used:

- access only through `load_body(...)`
- write/verify `raw_content_access_events`
- extract only bounded redacted labels
- do not write raw excerpts
- add synthetic sentinel tests proving no body/HTML leakage

## Tests

Create targeted tests, likely:

`tests/test_phase_10_email_followup_candidate_projection.py`

Test:

- waiting-on candidate from structured thread fixture
- response-needed candidate from structured message/thread fixture
- stale-thread nudge candidate
- user commitment candidate
- third-party commitment candidate
- project action item candidate
- time-sensitive follow-up candidate
- bounded title/reason
- no raw body/HTML/URL/recipient array in output
- raw body access not used by default
- deterministic keys stable across runs

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/03-extractor-results.md`

Include only counts, candidate family distributions, safe reason codes, and test names.
