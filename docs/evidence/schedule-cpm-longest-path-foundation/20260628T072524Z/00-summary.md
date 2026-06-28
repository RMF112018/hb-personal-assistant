# Schedule CPM Longest Path Foundation — Phase 5

Generated: 20260628T072524Z (UTC)
Branch: feat/schedule-cpm-longest-path-foundation
Base commit: 4e2706e4 (Phase 4 `feat/schedule-cpm-float-foundation`, committed + pushed, NOT on origin/main → branched from the Phase 4 commit; stacked P1→2→3→4→5)
Schema: v86 → **v87** (TWO new tables + run columns; table_count **475 → 477**)

## Implemented
Deterministic application-computed **longest path** identification, derived from application-owned Phase 2/3/4 results (read through the Phase 4 float run, which carries the combined early/late/float fields):
- `construction/analytics/schedule_cpm_longest_path.py` (new) — pure, SQL-free: `compute_longest_path` (endpoint selection + controlling-predecessor backtrace + summary).
- `construction/analytics/schedule_cpm_service.py` — added `run_longest_path(svk)` (reads the persisted float run; writes a NEW longest-path run; prior runs untouched).
- `store/schedule_cpm_tables.py` — V87 DDL (2 new tables) + run-column dict.
- `store/schedule_cpm_repository.py` — `get_float_run`, `replace_longest_path_run`, `insert/list_paths`, `insert/list_path_activities`, path-summary columns in run SELECTs.
- `store/migrator.py` — v87 (CREATE tables + column-guarded run-column reconcile); LATEST 86→87.
- `table_lifecycle_status_contract.json` 475→477 + 2 entries; 23 count-assert test files bumped 475→477 (lockstep).
- `tests/test_schedule_cpm_longest_path.py` (new) — 16 unit + 5 integration.

## Result
- Endpoint = max computed early finish (tie → larger ES → lower topo index → smallest id). Backtrace = controlling predecessor whose persisted Phase 2 candidate (`candidate_successor_early_start_offset`) equals the successor's early start within 1e-6 (reconstructed from offsets+type+lag when absent); tie → larger pred EF → larger pred ES → lower topo → smallest id → smallest ref. Stops at the anchor-driven open start (status `computed`).
- Separate longest-path run (`calculation_type='longest_path'`, `cpm_recalculation_status='longest_path_only'`, `source_run_id`=float run). Prior runs untouched (proven by test). Persists ONE `schedule_cpm_paths` row + ordered `schedule_cpm_path_activities` rows.
- Conservative degradation: unsupported/unreconstructable incoming types are recorded as caveats; if no supported candidate controls the activity's early value (and it isn't an anchor start), the backtrace STOPS with `unsupported_relationship_type`/`degraded_partial_backtrace` (partial chain still persisted).
- Blocks (no path rows) on fatal graph diagnostics, missing forward run, or missing float run.

## Explicitly NOT implemented
This is a LONGEST-PATH BASIS, not a critical-path declaration. No `is_critical`, no computed critical flag, no near-critical path, no float threshold, never labels the longest path "critical path". No source critical/driving-path/float/early/late field read for logic or overwritten. DCMA critical-path metric unchanged (still NOT_MEASURABLE_RECALC). No frontend/API.
