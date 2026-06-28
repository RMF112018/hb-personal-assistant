# Schedule CPM Backward Pass Foundation — Phase 3

Generated: 20260627T231235Z (UTC)
Branch: feat/schedule-cpm-backward-pass-foundation
Base commit: 404c6b84 (Phase 2 `feat/schedule-cpm-forward-pass-foundation`, committed + pushed, NOT on origin/main → branched from the Phase 2 commit)
Schema: v84 → **v85** (additive COLUMNS only; no new tables; table_count unchanged at 475)

## Implemented
Deterministic CPM **backward pass** (late start / late finish only) over the same acyclic graph and the persisted Phase 2 forward-pass results:
- `construction/analytics/schedule_cpm_backward_pass.py` (new) — pure, SQL-free: `compute_backward_pass` (reverse-topo) + `resolve_finish_anchor`; reuses Phase 2 constants/helpers.
- `construction/analytics/schedule_cpm_service.py` — added `run_backward_pass(svk)` (reads the persisted forward run; writes a NEW backward run; forward run untouched).
- `store/schedule_cpm_tables.py` — V85 additive column dicts for the 3 shared CPM tables.
- `store/schedule_cpm_repository.py` — `get_forward_pass_run`, `replace_backward_pass_run`, late columns in SELECTs.
- `store/migrator.py` — v85 column-existence-guarded reconcile; LATEST 84→85.
- `tests/test_schedule_cpm_backward_pass.py` (new) — 18 unit + 4 integration.

## Result
- FS/SS/FF/SF + lag handled in reverse; offsets authoritative, ISO dates derived (calendar-day, same Phase 2 simplification).
- Separate backward run (`calculation_type='backward_pass'`, `cpm_recalculation_status='backward_pass_only'`); forward-pass run rows are byte-for-byte unchanged (proven by test).
- Finish-anchor precedence: imported scheduled finish (`finish_date`) → imported planned finish (`planned_finish`) → max forward early-finish offset → block `missing_finish_anchor`. Earlier-than-forward-finish records caveat `finish_anchor_before_forward_pass_finish` (does not fail).
- Blocks (no result rows) on fatal graph diagnostics, missing forward-pass run, or missing finish anchor.

## NOTE on the minimal.xer sample
The fixture's imported `finish_date` (2026-03-10) precedes its data-date start anchor (2026-06-01), so the run correctly selects `source_scheduled_finish` and records the `finish_anchor_before_forward_pass_finish` caveat with negative offsets — an honest, internally consistent result (terminal LF == anchor, LS == LF − duration), exactly the caveat path the spec requires.

## Explicitly NOT implemented
Float (total/free/interfering/independent), longest path, critical path, calendar/weekend/holiday engine, frontend/API. No source-export field is read for logic or overwritten. DCMA critical-path metric unchanged (still NOT_MEASURABLE_RECALC).
