# Schedule CPM Criticality Foundation — Phase 6

Generated: 20260628T074818Z (UTC)
Branch: feat/schedule-cpm-criticality-foundation
Base commit: a0b491b0 (Phase 5 `feat/schedule-cpm-longest-path-foundation`, committed + pushed, NOT on origin/main → branched from the Phase 5 commit; stacked P1→2→3→4→5→6)
Schema: v87 → **v88** (additive COLUMNS only; no new tables; table_count unchanged at 477)

## Implemented
Deterministic application-computed **critical / near-critical / noncritical** classification from the Phase 4 computed total float, with Phase 5 longest-path membership as CONTEXT only:
- `construction/analytics/schedule_cpm_criticality.py` (new) — pure, SQL-free: `compute_criticality` (threshold validation + classification + membership context + caveats) + `FLOAT_ROW_WHITELIST`.
- `construction/analytics/schedule_cpm_service.py` — added `run_criticality_classification(svk, *, critical_threshold_days=0.0, near_critical_threshold_days=10.0)` (reads persisted float + longest-path runs; whitelist-copies app-owned fields; writes a NEW criticality run; prior runs untouched).
- `store/schedule_cpm_tables.py` — V88 additive column dicts (12 activity + 7 run).
- `store/schedule_cpm_repository.py` — `get_longest_path_run`, `replace_criticality_run`, classification columns in SELECTs.
- `store/migrator.py` — v88 column-existence-guarded reconcile; LATEST 87→88.
- `tests/test_schedule_cpm_criticality.py` (new) — 17 unit + 6 integration.

## Result
- Thresholds (default critical 0.0 / near-critical 10.0 / tol 1e-6, configurable). **Validated first** — invalid (critical>near, tolerance<0, non-finite) → block `invalid_criticality_thresholds`.
- tf ≤ crit+tol → computed_critical; ≤ near+tol → computed_near_critical; else noncritical; missing tf → unclassified/missing_computed_total_float. Negative float classifies critical (caveat negative_total_float); never clamped.
- Longest-path membership recorded (flag/sequence) as CONTEXT — never overrides class. Caveats: zero_float_not_on_longest_path, longest_path_member_not_zero_float, threshold_boundary_value.
- Separate criticality run (`calculation_type='criticality'`, `cpm_recalculation_status='criticality_classification_only'`, `source_run_id`=longest-path run, chaining to float). Prior runs untouched (proven). Activity rows built by an EXPLICIT app-owned-field whitelist (never blind-copied), then classification columns.
- Blocks (no activity rows) on invalid thresholds, fatal graph diagnostics, missing float run, or missing longest-path run.

## Explicitly NOT implemented
NOT DCMA critical-path compliance: no `is_critical` mutation; source `is_critical`/driving-path/float are NOT computation inputs; never presents computed criticality as DCMA critical path. No DCMA metric integration/relabel (stays NOT_MEASURABLE_RECALC). No schedule quality metric behavior change. No frontend/API.
