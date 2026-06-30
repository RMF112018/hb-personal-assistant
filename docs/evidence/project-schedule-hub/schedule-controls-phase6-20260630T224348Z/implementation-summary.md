# Implementation Summary — Phase 6

## Backend

- **New** `ProjectScheduleControlsService.build_controls()` composes review preview cues, section summaries, CPM observability, and provenance.
- **New** `GET /api/projects/{project_key}/schedule/controls?as_of&comparison_basis`
- **New** `ProjectScheduleSummaryService.build_schedule_hub_context()` public wrapper (documented delegation to `_review_workbench_context`)
- **New** `validate_controls_text()` in narrative QA
- Baseline controls are **read-only live preview**; no baseline sync/disposition persistence added

## Frontend

- **New** `ScheduleControlsPanel` — compact triage panel after trust banner
- **Lifted** `comparisonBasis` to `ProjectSchedulePage` shared with `DriverEvidenceSection`
- **Renamed** lower visualization heading to **Controls Trend Analytics** only
- **New** `getProjectScheduleControls` API helper

## Proof type

- Backend/frontend tests use **fixture databases** (`_seed_driver_chain`, comparable versions)
- Not production/local DB proof unless separately captured

## Not modified

- Parser, CPM algorithm, import UX, trend aggregation, metric contracts, ControlsOverview internals
