# Schedule CPM Forward Pass Foundation — Phase 2

Generated: 20260627T214225Z (UTC)
Branch: feat/schedule-cpm-forward-pass-foundation
Base commit: 0d927c9e (Phase 1 `feat/schedule-cpm-graph-foundation`, committed locally, NOT on origin/main → branched from the Phase 1 commit)
Schema: v83 → **v84**; table_count 473 → **475**

## Implemented
Deterministic CPM **forward pass** (early start / early finish only) over the Phase 1 acyclic graph:
- `construction/analytics/schedule_cpm_forward_pass.py` (new) — pure, SQL-free: typed models
  (`ForwardPassActivity`, `ForwardPassRelationship`, `ForwardPassResult`) + `compute_forward_pass`.
- `construction/analytics/schedule_cpm_service.py` — added `run_forward_pass(svk)` + anchor resolution.
- `store/schedule_cpm_tables.py` — V84 DDL (2 result tables) + guarded run-column additions.
- `store/schedule_cpm_repository.py` — result insert/list + `replace_forward_pass_run`; `deterministic_cpm_run_id(kind=)`.
- `store/migrator.py` — v84 migration (additive tables + column-existence-guarded reconcile); LATEST 83→84.
- `tests/test_schedule_cpm_forward_pass.py` (new) — 15 unit + 3 integration.

## Result
- FS/SS/FF/SF + lag handled; offsets authoritative, ISO dates derived (calendar-day, documented simplification).
- Run records `calculation_type='forward_pass'`, `cpm_recalculation_status='forward_pass_only'` (never "complete").
- Anchor precedence: data_date → min activity planned_start → min activity start_date → block `missing_start_anchor`.
- Blocks (no result rows) on fatal graph diagnostics (cycle / missing endpoint / self relationship) or missing anchor.

## Explicitly NOT implemented
Backward pass, late dates, any float, longest/critical/near-critical path, calendar/weekend/holiday engine,
frontend/API changes. No source-export field is read for logic or overwritten. DCMA critical-path metric unchanged.
