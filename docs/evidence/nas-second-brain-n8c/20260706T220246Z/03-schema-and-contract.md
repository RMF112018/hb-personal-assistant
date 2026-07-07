# 03 — Schema & contract (V105)

`LATEST_SCHEMA_VERSION 104 → 105`. Registered in `src/hb_assistant/store/migrator.py` as a guarded block
(`SELECT version FROM schema_migrations WHERE version = 105`) running `_v105_statements()` which imports
`V105_STATEMENTS` from `src/hb_assistant/store/assistant_review_tables.py`. Migration name
`v105_assistant_review_queue`. Additive; idempotent; empty on create.

## Tables (all `CREATE TABLE IF NOT EXISTS`, all indexes `IF NOT EXISTS`)

### assistant_review_items (durable review-queue snapshots — overlay, never replaces the source)
- PK `review_item_id`; `target_kind` (enum, NOT NULL), `target_id` (NOT NULL), `target_digest`,
  `target_state_digest`, `review_type` (enum, NOT NULL).
- `title`, `summary`, `evidence_excerpt`, `evidence_location` — bounded metadata only.
- `review_state` (enum, default `unreviewed`), `effective_state` (enum, default `candidate`),
  `confidence` (0..1 CHECK), `priority`, `stale` (0/1), `superseded` (0/1).
- Provenance anchors: `source_id, note_rel_path, claim_id, receipt_id, pack_id, pack_item_id,
  memory_node_id, memory_mention_id, compilation_id, decision_id, preference_id, open_loop_id`,
  `source_digest`, `card_digest`.
- CHECK: at least one provenance anchor non-NULL (shared `_PROVENANCE_CHECK`). `target_id` separately
  NOT NULL. Indexes on `(target_kind,target_id,review_state)`, `(review_type,review_state)`,
  `(effective_state)`.

### assistant_review_dispositions (append-only local/operator ledger)
- PK `disposition_id` (event-unique); `review_item_id` (NOT NULL); `disposition_type` (enum, NOT NULL);
  `from_review_state`/`to_review_state`, `from_effective_state`/`to_effective_state`; `operator_id`,
  `reason`, `evidence_note` (bounded); `created_by`, `created_at`, `metadata_json`. Index
  `(review_item_id, created_at)`. No UPDATE path — inserts only.

### assistant_review_events (append-only lifecycle log — NOT a bridge/job event system)
- PK `event_id`; `review_item_id`; `event_type` ∈ {created, updated, disposition_recorded, marked_stale,
  marked_superseded, failed}; `from_state`, `to_state`, `detail`, `created_at`. Index
  `(review_item_id, created_at)`.

## Enums (single source of truth = schema module, re-exported by the models)
- target_kind: claim, enrichment_receipt, enrichment_review_item, context_pack, context_pack_item,
  memory_node, memory_mention, memory_compilation, decision, preference, open_loop, unknown.
- review_type: claim_review, enrichment_review, context_pack_review, memory_review, decision_review,
  preference_review, open_loop_review, stale_review, conflict_review, unknown.
- review_state: unreviewed, needs_review, operator_accepted, operator_rejected, deferred, not_required,
  stale, superseded.
- effective_state: candidate, accepted, rejected, deferred, not_required, stale, superseded.
- disposition_type: accept, reject, defer, mark_not_required, mark_stale, mark_superseded,
  request_more_context, unknown.

## Determinism
- `review_item_id = sha256(target_kind | target_id | target_digest | review_type | "review-queue-v1")[:24]`
  — stable idempotent rebuild; a changed `target_digest` → new id + prior superseded (same lineage).
- `disposition_id = sha256(review_item_id | disposition_type | to_review_state | to_effective_state |
  operator_id | reason_digest | created_at_nonce)[:24]` — event-unique (append-only ledger).

## Additive proof
V100/V101/V102/V103/V104 tables and rows survive the V105 migration; re-apply is a no-op (one
`schema_migrations` row for 105). See `tests/test_review_v105_migration.py` and the added
`test_v105_migration_row_present` / `test_prior_assistant_tables_survive_v105` in
`tests/test_schema_version_head_consistency.py`.
