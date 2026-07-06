# 03 — Schema & contract (N8C-6, V102)

## Head version
`LATEST_SCHEMA_VERSION = 101 → 102` (`store/migrator.py:17`). Migration name `v102_assistant_context_packs`.

## Migrator wiring (mirrors the V100/V101 additive pattern)
- `_v102_statements()` lazy-imports `V102_STATEMENTS` from `store/assistant_context_pack_tables.py`.
- A `WHERE version = 102` guarded block appends the DDL and inserts the `schema_migrations` row, inside
  the same `with transaction(conn):` used by V99–V101.

## Four additive tables (context-pack-owned only)
- **`assistant_context_packs`** — header: `pack_id` PK, `pack_type` (CHECK enum), `title/objective`,
  `scope_json/budget_json`, `status` (CHECK enum, default `draft`), `created_by/builder_version`,
  `input_digest/output_digest`, accounting `source_count/claim_count/receipt_count/item_count`,
  `truncated` (0/1), `stale_count`, timestamps, `metadata_json`.
- **`assistant_context_pack_items`** — `pack_item_id` PK, `pack_id`, `item_order`, `item_type` (CHECK),
  provenance `source_id/note_rel_path/claim_id/job_id/receipt_id` (table CHECK: at least one present),
  bounded `content_excerpt/evidence_excerpt`, `source_digest/card_digest/result_digest`,
  `source_state`, `confidence` (0..1 CHECK), `review_tier` (CHECK), `token_estimate`, `included` (0/1),
  `exclusion_reason`, `metadata_json`.
- **`assistant_context_pack_receipts`** — per-build reproducibility snapshot: digests, `scope_json`,
  `budget_json`, `included_count/excluded_count`, `source_count/claim_count/receipt_count/stale_count`,
  `truncated`, `total_chars/total_token_estimate`.
- **`assistant_context_pack_events`** — lifecycle-ONLY log (`created/built/marked_stale/superseded`).
  Explicitly NOT a bridge/job/execution event table (clarification #2).

Enum tuples live in the schema module and are re-exported by `context_pack_models` as the single
source of truth, so the DB CHECKs and the Python layer cannot drift (same convention as V100/V101).

## Additive + idempotent + prior rows survive
Proof (`test_context_pack_v102_migration.py`, `test_schema_version_head_consistency.py`):
- fresh DB migrates to exactly 102; the 4 tables exist.
- applying twice → exactly one v102 `schema_migrations` row.
- V100 (`assistant_claims`, `_events`) and V101 (`assistant_enrichment_jobs`, `_receipts`) tables and
  migration rows remain present after V102.
- `/health` reports `schema_version == schema_expected == 102`, `schema_ready is True`.

## pack_id contract (clarification #1)
`pack_id = sha256(pack_type | normalized scope_json | normalized budget_json | input_digest |
builder_version)[:24]`. `input_digest` folds in the anchor + `source_digest`/`result_digest`/
`source_state` of every gathered input, so a changed source/receipt yields a new `pack_id` (and drives
the explicit stale check). `build --apply` refuses to overwrite an existing `pack_id` (reports
`reused`). Proof: `test_context_pack_builder.py::test_deterministic_ordering_and_output_digest`,
`::test_apply_is_idempotent_reuse`; `test_context_pack_repository.py::test_no_silent_overwrite`.
