# 03 — Schema and Migrations

## Schema version

- **`LATEST_SCHEMA_VERSION = 89`** (`src/hb_assistant/store/migrator.py:17`; see
  `artifacts/schema-version.txt`).
- The evidence DB copy (`/tmp/hb-schedule-cpm-evaluation.sqlite`) was migrated from schema
  **version 82 to 89** as part of building this package (see
  `artifacts/apply-evidence-db-migrations-output.txt` /
  `artifacts/apply-evidence-db-migrations-terminal.txt`). `MAX(version)` in the evidence DB's
  `schema_migrations` is **89** (`artifacts/table-count.txt`).

## v83–v89 migration summary

The v83–v88 reconciles add/repair the CPM run + result columns as each computation phase landed;
v89 widens the DCMA quality-metric status CHECK. Reconcile functions verified in `migrator.py`:

| Version | Reconcile function | Purpose |
| --- | --- | --- |
| v84 | `_reconcile_v84_schedule_cpm_run_columns` | CPM run columns |
| v85 | `_reconcile_v85_schedule_cpm_backward_columns` | backward-pass columns |
| v86 | `_reconcile_v86_schedule_cpm_float_columns` | float columns |
| v87 | `_reconcile_v87_schedule_cpm_path_run_columns` | longest-path / path-run columns |
| v88 | `_reconcile_v88_schedule_cpm_criticality_columns` | criticality columns |
| v89 | `_reconcile_v89_metric_status_app_cpm` | row-preserving rebuild of `schedule_quality_metric_results.status` CHECK to add `available_app_cpm_recalculated` |

(v83 is part of the same CPM-foundation sequence; the table-rebuild pattern in v89 mirrors the
earlier v71 status-widening migration.)

### v89 detail

`schedule_quality_metric_results.status` is CHECK-constrained from
`METRIC_STATUS_CHECK_VALUES` (`schedule_float_tables.py:32` includes
`"available_app_cpm_recalculated"`). Adding the new measured status therefore required a
**row-preserving table rebuild** (`_reconcile_v89_metric_status_app_cpm`), not a plain column
add. No new tables were introduced by v89.

## CPM tables present

The 6 CPM tables exist in the evidence DB (confirmed via `.tables`; DDL source in
`artifacts/cpm-table-ddl.txt`):

- `schedule_cpm_runs`
- `schedule_cpm_activity_results`
- `schedule_cpm_relationship_results`
- `schedule_cpm_diagnostics`
- `schedule_cpm_paths`
- `schedule_cpm_path_activities`

## Table count

- **Lifecycle contract `table_count` = 477** (asserted across many `tests/test_*` files; see
  `artifacts/schema-version.txt`). Unchanged by the CPM phases on the contract axis.
- **Evidence DB physical table count = 476** (`artifacts/table-count.txt`,
  `SELECT COUNT(*) FROM sqlite_master WHERE type='table'`).

The 476-vs-477 difference is a **physical-vs-contract distinction**, not a CPM defect: the
lifecycle contract count (477) is the governance figure asserted by the test suite, while the
476 is the raw physical table count of this particular evidence DB copy. This is recorded as a
factual observation; it is not a Schedule-CPM finding and does not affect CPM computation or
evidence.

## Phase 8 schema impact

**Phase 8 (CPM API / Frontend Surfacing) added no migration and no schema change** — it is a
read-only surfacing layer over the already-persisted CPM runs. The last CPM-related schema
change is v89 from Phase 7.

## Artifact references

- `artifacts/apply-evidence-db-migrations-output.txt`
- `artifacts/apply-evidence-db-migrations-terminal.txt`
- `artifacts/apply-evidence-db-migrations.py`
- `artifacts/schema-version.txt`
- `artifacts/table-count.txt`
- `artifacts/cpm-table-ddl.txt`
