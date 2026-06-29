# Project Schedule Hub Phase 4 Closeout

## Scope

Schedule Analysis Workbench and PM Action Workflow — persisted review queue, disposition carry-forward, driver detail panel, memo export, and dual-basis driver analysis wired into the hub envelope.

## Deliverables

- V91 `project_schedule_review_items` schema, migrator, repository CRUD
- `project_schedule_review_service.py` — queue sync, preview merge, workbench envelope
- `project_schedule_memo_service.py` — Markdown/HTML memo export from hub read model
- `project_schedule_driver_analysis_service.py` — `build_hub_analysis()`, `build_driver_detail()`
- Hub wiring in `project_schedule_summary_service.py` — `review_workbench`, dual-basis `change_driver_analysis`
- API routes: `GET/POST/PATCH .../review-items`, `GET .../drivers/{id}/detail`, `GET .../schedule/export`
- Frontend: `ProjectScheduleWorkbenchPage`, `ProjectScheduleDriverDetailPage`, hub links
- Wave 0 UX: `as_of` threading, operator role gate on workbench sync, workbench smoke tests

## Architecture decisions

1. Hub GET is read-only — `build_preview()` only, no upsert on GET.
2. Persistence is operator-gated — POST sync requires operator role.
3. Stable item keys carry disposition: `driver:{id}`, `milestone:{id}`, etc.
4. `change_driver_analysis` shape: `{ available, advisory_posture, prior_update, baseline }`.
5. Public envelopes strip `schedule_version_key` / `project_key` from workbench items.

## Advisory posture

All outputs use sequence-cue language. No causation claims. Memo footer and UI disclaimers preserved.

## Phase 1–3 non-regression

Change-impact counts, trust/baseline/drilldowns, and driver analysis behavior unchanged. TWNU18→TWNU19 canonical counts must hold with `as_of=2026-07-03`.

## Validation

See `tests/validation-suite.txt` and `tests/frontend-project-schedule-page.txt`.