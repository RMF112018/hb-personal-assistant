# Evidence — Schedule Project Association UI + API

**Branch:** `feature/schedule-project-association-ui`
**Base:** `origin/main` @ `69bb5737` (PR #91 critical path)
**Date stamp:** 20260622T145503Z

## What shipped

- **Backend catalog:** `schedule_project_catalog.py` lists import-selectable projects from
  `procore_ep_projects` and browse-time union with schedule import keys.
- **Import validation:** `project_key` required on preview/commit; unknown keys return 422;
  removed hardcoded `tropical` default.
- **API scoping:** optional `project_key` on version/quality routes with scope enforcement;
  enriched DTOs with `project_key`, `project_display_name`, quality posture fields.
- **Frontend:** `ScheduleProjectPicker` + project param hook; imports require project selection;
  versions/quality/activities/cost/diff pages show project context and filters.

## Proof files

- `backend_tests.txt` — project association + import + quality (**25 passed**); full
  `tests/test_schedule_*.py` (**67 passed**).
- `frontend_proof.txt` — ScheduleImports/Routes/QualityPage vitest (**18 passed**); `npm run build`
  clean.
- `git_state.txt` — branch, diff stat, and working tree snapshot at closeout.

## Notes

- No new SQLite migration; uses existing `project_key` columns.
- `frontend/src/lib/errorCopy.ts` force-added (root `lib/` gitignore pattern) for build unblock.
- ruff clean on new/changed analytics modules in scope for this feature.