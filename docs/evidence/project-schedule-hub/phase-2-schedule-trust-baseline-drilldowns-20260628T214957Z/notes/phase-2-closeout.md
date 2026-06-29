# Project Schedule Hub Phase 2 Closeout

## Scope

Schedule Trust, Baseline Control, and PM Review Drilldowns for the Project Schedule Hub.

## Deliverables

- V90 schema: `project_schedule_series_membership`, `project_schedule_baseline_selections`
- Schedule trust envelope with fail-closed hub resolver (`is_hub_eligible`)
- User-selected baseline persistence and baseline summary
- Bounded drilldown API (`GET /api/projects/{project_key}/schedule/drilldowns`)
- Hub fields: `schedule_trust`, `identity_review`, `baseline_summary`, `review_drilldowns`, `trend_series`, `source_float_summary`, `computed_cpm_summary`
- Story v2: `what_changed`, `why_it_matters`
- Identity review accept/exclude via series membership API
- Frontend trust banner, baseline card, drilldown expand, split float/CPM, trend metrics
- Regression tests for trust, baseline, drilldowns, hub API, CPM

## Bugs fixed during closeout

1. `build_drilldown` now accepts `as_of` to align version resolution with hub summary
2. Import guardrail moved post-commit to avoid nested-transaction lock failures
3. Drilldown count reconciliation test passes with explicit `as_of`

## Phase 1 non-regression (TWNU18 → TWNU19)

Must remain:
- 461 later / 76 earlier / 537 changed / 98 new
- 378 worsened / 122 improved / 6 milestones
- Forecast 2026-11-03 @ 0 days delta
- 712 remaining / 711 source negative float / 613 CPM critical

## Validation

- Backend: `tests/test_schedule_trust_resolver.py`, `tests/test_project_schedule_baseline_selection.py`, `tests/test_project_schedule_hub_drilldowns.py`, `tests/test_project_schedule_hub_api.py`, `tests/test_schedule_cpm_api.py`, `tests/test_schedule_health_cpm_aggregation.py`
- Frontend: `ProjectSchedulePage.test.tsx`, `npm run typecheck`

See `tests/validation-suite.txt` and `tests/frontend-project-schedule-page.txt`.