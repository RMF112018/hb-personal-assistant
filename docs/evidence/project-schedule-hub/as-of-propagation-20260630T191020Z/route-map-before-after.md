# Phase 3 as_of Route Map

## Backend routes inspected
- `src/hb_assistant/construction/analytics/api.py::project_schedule`: changed. Adds `as_of`, validates malformed values as `400 invalid_as_of_date`, and forwards `as_of_date` into `ProjectScheduleSummaryService.build_summary`.
- `api.py::project_schedule_drilldowns`: already accepted `as_of` and forwarded it to `build_drilldown`. Service bug fixed for the `upstream_cues` branch.
- `api.py::project_schedule_drivers`: already accepted `as_of` and forwarded it to `build_driver_drilldown`.
- `api.py::project_schedule_driver_detail`: already accepted `as_of` and forwarded it to `build_driver_detail`.
- `api.py::project_schedule_review_items_get`: already accepted `as_of` and forwarded it to `build_review_items`. Added route-spy regression coverage.
- `api.py::project_schedule_review_items_sync`: already accepted `as_of` and forwarded it to `sync_review_workbench`.
- `api.py::project_schedule_metric_trend`: already accepted `as_of` and forwarded it to `build_trend`.
- `api.py::project_schedule_metric_trends`: already accepted `as_of` and forwarded it to `build_trends`. Added route-spy regression coverage.
- `api.py::project_schedule_export`: already accepted `as_of` and forwarded it to `build_export`. Added route-spy regression coverage.
- `api.py::project_schedule_baseline_get`: changed. Adds `as_of`, validates malformed values as `400 invalid_as_of_date`, and uses that date for summary/baseline context.
- `api.py::project_schedule_baseline_put`: changed. Adds `as_of`, validates malformed values as `400 invalid_as_of_date`, and preserves it in the post-selection summary refresh.

## Backend services inspected
- `project_schedule_summary_service.py::ProjectScheduleSummaryService.build_summary`: already supports `as_of`.
- `ProjectScheduleSummaryService.build_drilldown`: changed only for `upstream_cues`; the prior implementation called `build_summary(project_key)` and now passes `as_of=as_of`.
- `build_export`, `build_review_items`, `sync_review_workbench`, and trend aggregation calls already accepted/used `as_of` via their existing route boundaries.

## Frontend files inspected
- `frontend/src/lib/api.ts::getProjectScheduleSummary`: changed to accept `options?: { asOf?: string | null }` and emit backend `as_of` only when non-empty.
- `frontend/src/lib/api.ts::getProjectScheduleBaseline`: changed to accept `options?: { asOf?: string | null }` and emit backend `as_of` only when non-empty.
- Existing trend, driver, drilldown, review, sync, driver detail, and export helpers already used `asOf` and emitted `as_of`.
- `frontend/src/pages/ProjectSchedulePage.tsx`: changed to read narrow URL `as_of` state, add a minimal `As-of date` input, include the selected date in date-sensitive query keys, request summary first with the selected date, and pass the same selected date to baseline, trends, drivers, drilldowns, focused links, workbench links, and export. Empty/latest omits `as_of`.
