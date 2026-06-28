# Migration notes — V89

- LATEST_SCHEMA_VERSION 88 → 89; migration `v89_schedule_quality_app_cpm_metric_status`.
- **A migration WAS required** because schedule_quality_metric_results.status is enforced by a CHECK constraint (built from METRIC_STATUS_CHECK_VALUES). Inserting the new measurable status would fail without widening it.
- Change: added 'available_app_cpm_recalculated' to METRIC_STATUS_CHECK_VALUES; `_reconcile_v89_metric_status_app_cpm` rebuilds schedule_quality_metric_results with the widened status CHECK (same columns, same family CHECK), preserving all rows. Mirrors the V71 reconcile; guarded by a DDL substring check so it runs once.
- **No new tables.** table_lifecycle_status_contract.json table_count UNCHANGED at 477; the 23 count-assert test files untouched.
- Proven: fresh-migrate → version 89, DDL contains the new status, a row with it inserts; pre-v89 upgrade → reconcile rebuilds the CHECK, the new status is accepted and the pre-existing row survives (test_migrator_v89_…); re-apply is idempotent (version stays 89).
