# Project Schedule Hub Phase 3 Closeout

## Scope

Schedule Driver Analysis and Causal-Sequence Storytelling — advisory prioritization for PM review.

## Deliverables

- `project_schedule_driver_analysis_service.py` — candidate driver scoring, bounded BFS successor chains, logic/duration/milestone rollups, PM narrative builder
- Hub field `change_driver_analysis` with preview drilldowns
- Story v3: `primary_driver_narrative`, `top_review_sequence`; replaces generic count text in `primary_change_driver` when drivers available
- `GET /api/projects/{project_key}/schedule/drivers` — typed drilldowns (`drivers`, `impacted_successors`, `logic_changes`, `duration_changes`, `milestone_impacts`)
- Frontend "Where To Look First" card + tabbed evidence tables
- Tests: `test_project_schedule_driver_analysis.py`, hub/drilldown updates, `ProjectSchedulePage.test.tsx`

## Advisory posture

All outputs use sequence-cue language ("candidate driver," "appears connected," "review this sequence first"). No causation claims.

## Phase 1/2 non-regression

Change-impact summary counts and trust/baseline/drilldown behavior unchanged. Story may show driver narrative when comparison is available.

## Validation

See `tests/validation-suite.txt` and `tests/frontend-project-schedule-page.txt`.