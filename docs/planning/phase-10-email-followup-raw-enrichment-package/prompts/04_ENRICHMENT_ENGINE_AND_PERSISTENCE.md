# Prompt 04 — Enrichment Engine and Persistence

## Objective

Connect deterministic follow-up/watch candidates, raw window builder, local model route, and V45 review-safe persistence.

## Scope

Implement an enrichment engine that:

- Selects eligible source-linked email follow-up candidates/watch items.
- Builds bounded sanitized raw windows.
- Calls local structured model route.
- Validates output.
- Persists review-safe V45 rows only under explicit apply/cap.
- Writes hash-only local model receipts if the repo already supports this pattern.
- Leaves dry-run as default.
- Is idempotent.

## Eligibility Rules

Only enrich items that:

- Already exist as deterministic accepted task/commitment/follow-up watch candidates.
- Have source refs linked to email thread/message records.
- Are not already closed unless explicit diagnostic mode is requested.
- Have enough local raw source data available to build a bounded window.

Do not create brand-new action candidates from raw content in this prompt. This feature enriches existing source-linked follow-up items.

## Persistence Rules

Persist to V45 only when:

- `apply=True` or CLI equivalent.
- `max_persist` cap is provided and positive.
- Structured output is valid.
- No raw leakage is detected.
- Source refs validate.
- idempotency key is available.

Persist only:

- structured enriched title
- waiting state
- assignee fields
- suggested next action
- due date if supported
- confidence
- reason codes
- source refs
- review status, default pending
- model/task/profile metadata
- input/output hashes
- raw excerpt hash

Do not persist:

- raw excerpt text
- raw prompt
- raw model response
- body text
- body HTML
- URLs
- tokens
- secrets
- email address dumps

## Review Status

Default review status:

```text
pending
```

Daily brief may consume `pending` rows later, but must label them.

## Idempotency

Compute a stable idempotency key from:

```text
source_candidate_id
watch_item_id
email thread/message refs or hashes
raw_excerpt_hash
model task family
prompt template version
schema version
```

Re-running the same enrichment must not create duplicates.

## Required Tests

Add tests for:

- No eligible source refs -> no model call.
- Missing raw content -> degraded result, no failure.
- Model unavailable -> deterministic result remains, no persistence unless safe receipt pattern requires failure receipt.
- Dry-run writes nothing.
- Apply without cap fails.
- Apply with cap persists at most cap.
- Idempotent re-run does not duplicate rows.
- Persisted V45 row has no raw fields.
- Persisted V45 row source refs match known candidates/watch items.
- Raw leakage detector blocks persistence.
- Closed items are skipped by default.

## Stop Conditions

Stop if:

- Engine cannot validate source refs.
- Dry-run cannot be guaranteed write-free.
- Idempotency cannot be guaranteed.
- Existing model receipt framework forces raw prompt/response persistence.

## Commit

After tests pass:

```bash
git add <engine files> <persistence files> <tests>
git commit -m "feat(follow-up): persist review-safe raw enrichment results"
```

## Exit Criteria

- Enrichment engine implemented.
- V45 persistence implemented.
- Dry-run/apply/cap/idempotency behavior tested.
- Commit created.
