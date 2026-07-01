# Repo-Truth Audit

**STAMP:** 20260701T075049Z  
**origin/main:** 76a2eefa (PR #242 Phase 10 merged)

## Phase 10 gate

PASS — `docs/evidence/project-schedule-hub/real-db-baseline-proof-phase10-20260701T072640Z/` documents FAB/DEL-10 → HTTP 401.

## Root cause

- Backend route `GET .../drivers/{activity_id}/detail` — single path segment; `/FAB/DEL-10/detail` does not match.
- Unmatched requests hit MCP `app.mount("/", ...)` → `401 unauthorized`.
- Controls links embed raw `activity_id` in frontend path ([`project_schedule_controls_service.py`](src/hb_assistant/construction/analytics/project_schedule_controls_service.py) L422-424).
- Frontend route `:activityId` single segment; `driverDetailHref` encodes in path (brittle).

## Frontend conflict behavior (pre-fix)

`resolveDriverComparisonBasis` silently fell back to `prior_update` on basis/comparison_basis conflict — **removed in Phase 11**.

## Files to change

- `api.py`, `project_schedule_controls_service.py`, `project_schedule_driver_analysis_service.py`
- `routes.tsx`, `ProjectScheduleDriverDetailPage.tsx`, `scheduleBaselineLabels.ts`, `api.ts`
- Tests listed in Phase 11 prompt

## Out of scope

Parser, CPM, import, trends, disposition, V90 sync, schema changes.
