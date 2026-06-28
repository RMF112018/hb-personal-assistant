# Schedule CPM Float Foundation — Phase 4

Generated: 20260628T065527Z (UTC)
Branch: feat/schedule-cpm-float-foundation
Base commit: a056cf7d (Phase 3 `feat/schedule-cpm-backward-pass-foundation`, committed + pushed, NOT on origin/main → branched from the Phase 3 commit; stacked Phase 1→2→3→4)
Schema: v85 → **v86** (additive COLUMNS only; no new tables; table_count unchanged at 475)

## Implemented
Deterministic CPM **total float** and **free float** derived solely from the application-owned early/late offsets persisted by Phases 2–3:
- `construction/analytics/schedule_cpm_float.py` (new) — pure, SQL-free: `compute_float` (total + free float, statuses/provenance).
- `construction/analytics/schedule_cpm_service.py` — added `run_float_calculation(svk)` (reads the persisted backward run; writes a NEW float run; forward/backward runs untouched).
- `store/schedule_cpm_tables.py` — V86 additive column dicts for the 3 shared CPM tables.
- `store/schedule_cpm_repository.py` — `get_backward_pass_run` (+ shared `_get_latest_run`), `replace_float_run`, float columns in SELECTs.
- `store/migrator.py` — v86 column-existence-guarded reconcile; LATEST 85→86.
- `tests/test_schedule_cpm_float.py` (new) — 19 unit + 5 integration.

## Result
- Total float = late−early offsets (start-based, cross-checked vs finish-based within 1e-6; mismatch → `inconsistent_start_finish_float` keeping the start-based value). Negative & fractional preserved; never clamped.
- Free float = min successor early-start/finish constraint (FS/SS/FF/SF), only when all successor relationships are supported with successor early values; terminal → NULL + `not_applicable_terminal_activity`. Relationship-level `free_float_candidate` persisted.
- Separate float run (`calculation_type='float'`, `cpm_recalculation_status='forward_backward_float_only'`, `source_run_id`=backward run). Forward & backward run rows unchanged (proven by test).
- Blocks (no result rows) on fatal graph diagnostics, missing forward run, or missing backward run.

## NOTE on the minimal.xer sample
Inherits the Phase 3 caveat (fixture `finish_date` precedes its data-date anchor), so both chain activities carry total float −98 (negative, internally consistent: ls−es = lf−ef), status `computed`. Honest, not clamped.

## Explicitly NOT implemented
Critical path, longest path, near-critical path; no activity marked critical (zero total float is NOT criticality here). No source-export float/early/late/critical/driving-path field read for logic or overwritten. DCMA critical-path metric unchanged (still NOT_MEASURABLE_RECALC). No frontend/API.
