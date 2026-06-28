# Repo-Truth Audit — Phase 9A.1

Grounded in the actual repo (worktree base `origin/main` @ `37767f36`, schema v89). Confirms the
SOW's claims and records two corrections.

## Reused (composed, not duplicated)
- `ScheduleReadService.get_health_data(svk)` — `schedule_import_service.py:2419`; route handler
  `schedule_version_health_data()` — `api.py:3481`.
- `ScheduleCpmReadService(*, db_path)` — `schedule_cpm_read_service.py:86`: `cpm_summary` (:137),
  `cpm_longest_path` (:200), `cpm_diagnostics` (:239). Emits `evidence_class:"application_computed_cpm"`,
  `source_export_evidence:"separate"`, `source_critical_flags_used:false`.
- `ScheduleCpmDiagnosticsRepository` — `schedule_cpm_repository.py`: `list_runs(svk)` (:106) and
  `_get_latest_run`/`get_criticality_run` (:359)/`get_float_run` (:351) already return the per-run
  aggregates `computed_critical_activity_count`, `computed_near_critical_activity_count`,
  `computed_noncritical_activity_count`, `longest_path_member_count`,
  `critical_float_threshold_days`, `near_critical_float_threshold_days`. **No 1507-row hydration
  needed** — the SOW's efficiency risk does not apply.
- Service factories in `api.py`: `_schedule_db_path()` (:3177), `_schedule_read_service()` (:3187),
  `_schedule_cpm_read_service()` (:3606).

## Added (this PR)
- `ScheduleCpmDiagnosticsRepository.float_risk_counts(cpm_run_id, *, high_total_float_days)` — one
  read-only `SUM(CASE…)` aggregate over `schedule_cpm_activity_results.computed_total_float`
  (negative / zero / high / classified). No row hydration, no writes.
- `schedule_health_cpm_service.py` — `ScheduleHealthCpmService.build_computed_cpm_health(svk)`
  composing the above into the `computed_cpm_health` envelope. Read-only; fail-soft to
  `available:false` when no CPM runs.
- `api.py`: `_schedule_health_cpm_service()` factory + additive, fail-soft enrichment of the
  `/health-data` response with `computed_cpm_health`.
- `frontend/src/lib/api.ts`: `ComputedCpmHealth` typed interface + optional
  `computed_cpm_health` field on `ScheduleHealthData`. No rendering changes.

## SOW corrections
1. **Unknown/mismatched project scope → HTTP 404** on the `/health-data` read route (via
   `_enforce_version_project_scope` → `assert_version_matches_project` → `_raise_schedule_import_error`),
   not 400. (400 is the commit-path behavior.) Test asserts 404.
2. **Float-bucket counts are NOT pre-aggregated** on `schedule_cpm_runs`; they required the new
   `float_risk_counts` query. Criticality/near-critical/longest-path-member counts ARE pre-aggregated.

## Provenance vocabulary (reused verbatim)
`evidence_class:"application_computed_cpm"`, `source_export_evidence:"separate"`,
`source_critical_flags_used:false`, caveat `computed_critical_outside_longest_path`. The computed
activity whitelist (`_ACTIVITY_WHITELIST`) keeps source critical/driving/float fields out of computed
views; this envelope surfaces only application-computed aggregates.
