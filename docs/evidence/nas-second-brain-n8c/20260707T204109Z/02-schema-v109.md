# 02 — Schema V109 (feedback-owned only)

`LATEST_SCHEMA_VERSION = 109`. `store/migrator.py` gains `_v109_statements()` (lazily importing
`V109_STATEMENTS` from `store/assistant_feedback_tables.py`) and a guarded apply block:
`SELECT version FROM schema_migrations WHERE version=109` → loop statements →
`INSERT ... (109, 'v109_assistant_feedback', ?)`. All DDL is `CREATE TABLE/INDEX IF NOT EXISTS`.

## Five tables
1. `assistant_feedback_records` — headers: `feedback_id` PK, `feedback_type` (CHECK-in enum), bounded `note`,
   `workflow_type`/`workflow_id`, `status` (feedback lifecycle: open/acknowledged/resolved/superseded), the
   pinned `_FEEDBACK_POLICY` block, `created_by`, `created_at`/`updated_at`, `input_digest`/`output_digest`,
   `target_count`/`recommendation_count`, `truncated CHECK(0,1)`, `metadata_json`.
2. `assistant_feedback_targets` — `feedback_target_id` PK, `feedback_id`, `target_order`, `target_kind`
   (CHECK-in), `target_id` **NOT NULL**, `target_label`, 23 typed provenance anchor columns, `target_digest`,
   `review_state`/`effective_state` (re-used from the N8C-9 review enums, nullable), `created_at`,
   `metadata_json`.
3. `assistant_feedback_recommendations` — `recommendation_id` PK, `feedback_id`, `recommendation_order`,
   `recommendation_type` (CHECK-in advisory-only enum), nullable `target_kind`/`target_id`, `rationale`,
   `review_policy` pinned `= 'advisory_review_loop'`, `requires_operator_review` pinned `= 1`, `created_at`,
   `metadata_json`.
4. `assistant_feedback_receipts` — derivation receipts (`feedback_receipt_id`, `feedback_id`,
   `builder_version`, `input_digest`/`output_digest`, counts, `dropped_count`, `truncated`, `created_at`,
   `metadata_json`).
5. `assistant_feedback_events` — append-only feedback-record lifecycle (`created/linked/recommended/
   acknowledged/resolved/superseded`). NOT a review-disposition or execution ledger.

## Verified by `tests/test_feedback_v109_migration.py` (13 cases)
- head == `LATEST_SCHEMA_VERSION`, floor ≥ 109; exactly the five feedback tables created; idempotent re-apply;
  prior V100–V108 versions + V108 answer-draft tables survive.
- CHECK rejects an execution `action_policy`, a disposition `review_policy`, `requires_operator_review=0`, an
  unknown `feedback_type`, a NULL `target_id`, and a non-advisory recommendation `review_policy`.
- `test_no_action_stage_tables` — no `assistant_action%` table.
- `test_no_finality_or_disposition_columns_on_feedback_tables` — no accepted/rejected/deferred/disposed/
  executed/execution_status/sent/scheduled/external_ref/external_system/dispatched/final_answer column.

## Idempotency
`SQLiteMigrator(...).apply()` re-run is a no-op; `schema_migrations` row for 109 is
`v109_assistant_feedback`.
