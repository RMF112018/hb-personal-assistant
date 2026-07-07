# 02 — Schema V110 (action-stage-owned only)

`LATEST_SCHEMA_VERSION = 110`. `store/migrator.py` gains `_v110_statements()` (lazily importing
`V110_STATEMENTS` from `store/assistant_action_stage_tables.py`) and a guarded apply block
(`SELECT version FROM schema_migrations WHERE version=110` → loop statements →
`INSERT ... (110, 'v110_assistant_action_stage', ?)`). All DDL is `CREATE TABLE/INDEX IF NOT EXISTS`.

## Five tables
1. `assistant_action_stages` — headers: `stage_id` PK, `stage_type` (CHECK-in), workflow lineage, `title`,
   `status` (draft/staged/superseded), the pinned `_STAGE_POLICY` block, digests (request/source-context/
   input/output), `stage_policy_json`/`budget_json`, counts, `truncated`, `metadata_json`.
2. `assistant_action_stage_items` — `stage_item_id` PK, `action_kind` (CHECK-in internal-review kinds),
   `staged_state` (CHECK-in candidate/blocked), `source_section`, bounded `title`/`detail`, `block_reason`,
   `execution_status` pinned `='not_executed'`, `external_system` pinned `='none'`, `external_ref` pinned
   `IS NULL`, `requires_operator_review` pinned `=1`, `target_kind`/`target_id`, 19 provenance anchors,
   `review_state`/`effective_state` (re-used N8C-9 enums, nullable), `item_digest`, `metadata_json`.
3. `assistant_action_stage_citations` — bounded provenance bridge; provenance CHECK requires ≥1 anchor
   (target_id/workflow_id/draft_id/…/source_ref/rel_path).
4. `assistant_action_stage_receipts` — derivation receipts (digests + counts).
5. `assistant_action_stage_events` — append-only stage-record lifecycle (created/staged/item_added/
   citation_added/superseded). NOT an execution/dispatch ledger.

## Verified by `tests/test_action_stage_v110_migration.py` (14 cases)
- head == `LATEST_SCHEMA_VERSION`, floor ≥ 110; exactly the five stage tables; idempotent; prior V100–V110
  versions + V108 draft + V109 feedback tables survive.
- CHECK rejects: execution `execution_policy`, disposition `review_policy`, item `execution_status='executed'`,
  `external_system='slack'`, non-NULL `external_ref`, `staged_state='active'`, `requires_operator_review=0`,
  anchorless citation.
- `test_no_finality_or_dispatch_columns` — no sent/scheduled/completed/executed_at/dispatched/emailed/
  delivered/n8d_job_id/external_task_id/reminder_id/calendar_event_id column.
