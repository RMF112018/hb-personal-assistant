# Prompt 01 — V45 Schema and Contracts

## Objective

Add a V45 migration for a review-safe email follow-up raw enrichment table and define the core typed contracts. This prompt establishes persistence boundaries before model or CLI integration.

## Scope

Implement:

- Schema version bump from V44 to V45.
- Migration adding `email_followup_enrichments` or repo-style equivalent.
- All required indexes/unique keys.
- All required guard columns used elsewhere in Phase 10.
- Typed contract/dataclass/model for enrichment rows and results.
- Tests proving fresh and upgraded DB migration.

Do not implement raw loading or model calls in this prompt.

## Required Table Semantics

The table must support:

- source candidate linkage
- follow-up watch item linkage when applicable
- email thread/message source linkage by stable IDs or hashes
- raw excerpt hash only
- structured enriched fields
- review status
- model/task/profile metadata
- idempotency
- guard columns

It must not include any raw body or unsafe field.

Use `reference/V45_TABLE_SPEC.md` as the target. Adapt names to repo style if necessary, but preserve the safety properties.

## Required No-Raw Column Audit

After migration, run an introspection query and assert no column name contains:

```text
body
html
raw_text
raw_body
raw_prompt
raw_response
prompt
response
url
token
secret
html
```

`raw_excerpt_hash` is allowed. `raw_source_ref` is not allowed unless it is a hash or opaque non-content ID. Prefer explicit `_hash` naming.

## Required Tests

Add tests for:

- Fresh DB migrates to V45.
- Existing V44 DB migrates to V45.
- `LATEST_SCHEMA_VERSION == 45`.
- Enrichment table exists.
- Required indexes/unique keys exist.
- Guard columns exist and default to 0.
- No disallowed raw-content columns exist.
- Inserting a minimal review-safe enrichment row succeeds.
- Inserting duplicate idempotency key performs expected upsert/ignore behavior, depending on repo convention.

## Suggested Contract Fields

Structured result contract should include:

```text
enrichment_id
source_candidate_id
source_candidate_type
watch_item_id
email_thread_ref_hash
email_message_ref_hashes_json
raw_excerpt_hash
enriched_title
waiting_state
assignee_type
assignee_display
suggested_next_action
due_at_utc
confidence
reason_codes_json
source_refs_json
review_status
model_task
model_profile_id
prompt_template_version
input_context_hash
output_hash
created_utc
updated_utc
```

If the repo has existing enums for waiting state, candidate type, confidence, or review status, reuse them.

## Stop Conditions

Stop if:

- Existing schema/migration convention is unclear after inspection.
- A destructive migration appears necessary.
- The migration would require raw body columns.
- Fresh DB migration cannot pass.
- Existing Phase 10 guard-column pattern cannot be preserved.

## Commit

After tests pass:

```bash
git add <schema files> <contract files> <tests>
git commit -m "feat(schema): add V45 email follow-up enrichment table"
```

## Exit Criteria

- V45 schema implemented.
- Contracts compile/typecheck.
- Migration tests pass.
- No raw columns are introduced.
- Commit created.
