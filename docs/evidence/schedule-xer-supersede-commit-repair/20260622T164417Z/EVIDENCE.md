# Schedule XER supersede commit repair

**UTC:** 20260622T164417Z  
**Branch:** feature/schedule-project-association-ui (PR #93)

## Problem (before fix)

Live operator flow on `tropical` + `TWNU18.xer`:

1. Normal preview → `409 duplicate_schedule_version` (expected)
2. Preview supersede → `200 OK` (expected)
3. Commit via main preview button → `409 Conflict` (bug)

Root cause: frontend cleared duplicate state after supersede preview and called commit with `confirm_supersede=false`.

## Fix summary

- **Frontend:** `previewIsSupersede` state preserves supersede intent from preview through commit; button label and notice reflect supersede mode.
- **Backend:** Preview cache stores `confirm_supersede`; commit validates cache vs request and returns structured errors (`schedule_supersede_confirmation_required`, `schedule_supersede_state_mismatch`).
- **Response:** Commit includes `supersede_performed: true` when supersede occurs.

## After-fix live API proof (`tropical` + `TWNU18.xer`)

| Step | Status | Notes |
|------|--------|-------|
| Normal preview | 409 | `duplicate_schedule_version` |
| Supersede preview | 200 | `import_id` cached with supersede intent |
| Commit without `confirm_supersede` | 409 | `schedule_supersede_confirmation_required` |
| Supersede commit | 200 | `supersede_performed: true`, `superseded_import_id: d57d46b5dcdc` |

See `live_api_flow.json`.

## DB proof (`tropical|1069|2026-05-26 08:00`)

- New import `26140a04d72d` → `committed`
- Prior import `d57d46b5dcdc` → `superseded` / `superseded_by_operator`
- Activity rows: 1378 with `duration_unit=hour` on all rows; 733 actual_start; 701 actual_finish; 269 driving_path_flags

See `live_db_proof.txt`.

## Validation

| Check | Result |
|-------|--------|
| `pytest tests/test_schedule_import_api.py` | pass (see `summary.json`) |
| `npm test -- ScheduleImports ScheduleRoutes ScheduleQualityPage` | pass (see `summary.json`) |
| `npm run build` | pass (see `summary.json`) |
| Sensitive scan | `hygiene_summary.json` (full scan output omitted — large) |

## Hygiene

No tokens, PEMs, full mail bodies, or raw delta links in evidence artifacts.