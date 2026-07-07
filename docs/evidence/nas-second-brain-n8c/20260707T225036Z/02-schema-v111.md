# N8C-20 — V111 schema proof

## Head + tables (fresh empty DB migrated)

```
SCHEMA_HEAD 111   LATEST 111
TOTAL_TABLES 549
QUALITY_TABLES ['assistant_quality_events', 'assistant_quality_findings',
                'assistant_quality_receipts', 'assistant_quality_runs', 'assistant_quality_targets']
```

Migration `schema_migrations` record: `version=111, name='v111_assistant_quality'`. Re-running the migrator
is idempotent (head stays 111). Prior V100–V110 versions and their tables all survive (asserted by
`test_prior_v100_v111_versions_survive`, `test_prior_v108_v110_tables_survive`).

## Five quality-owned tables (all `CREATE TABLE IF NOT EXISTS`, additive only)

- `assistant_quality_runs` — run headers. `target_kind`/`status` CHECK-in; the fixed policy pinned by CHECK:
  `action_policy='no_execution'`, `execution_policy='evaluate_only'`, `review_policy='advisory_review_loop'`,
  `source_policy='preserve_source_truth'`, `citation_policy='preserve_citations'`,
  `requires_operator_review=1`.
- `assistant_quality_findings` — one advisory finding each. `finding_type` (21 values) + `severity`
  (info/warn/risk) CHECK-in; the same no-execution / evaluate-only / advisory-review-loop /
  requires_operator_review=1 policy pinned by CHECK; 22 bounded provenance anchors; `review_state` /
  `effective_state` re-use the N8C-9 review enums (nullable). No accept/reject/repair/disposition column.
- `assistant_quality_targets` — the evaluated target(s) with preserved provenance + copied review/effective
  state.
- `assistant_quality_receipts` — derivation receipts (evaluator version + digests + counts).
- `assistant_quality_events` — append-only lifecycle (`created`/`evaluated`/`finding_added`/`superseded`).
  NOT a repair/execution/disposition ledger.

## CHECK constraints proven to fire (negative tests)

`test_quality_v111_migration.py` asserts `IntegrityError` on: `action_policy!='no_execution'`,
`execution_policy!='evaluate_only'`, `review_policy!='advisory_review_loop'`, `requires_operator_review!=1`,
unknown `status`, unknown `target_kind`, unknown `finding_type`, unknown `severity`, finding
`execution_policy` deviation, and unknown `event_type`. A valid advisory finding row reads back
`(no_execution, evaluate_only, advisory_review_loop, 1)`.

## No repair / execution / disposition columns

`test_no_repair_execution_or_disposition_columns` asserts none of the five tables contains any of:
`repaired`, `repaired_at`, `executed`, `executed_at`, `applied`, `applied_at`, `sent`, `dispatched`,
`accepted`, `rejected`, `deferred`, `disposed`, `disposition`, `n8d_job_id`, `external_task_id`,
`reminder_id`, `calendar_event_id`.
