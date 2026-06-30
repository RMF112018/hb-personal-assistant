# Repo-Truth Audit — Schedule Controls Phase 6

## Base

- **main SHA:** `13bc00b7d2419b254f909a6963fc8bd450713162`
- **Branch:** `feature/schedule-controls-analytics-phase6-20260630T224348Z`
- **Phase 5 merged:** PR #233 (`8e9e4999` review workbench alignment)

## Schedule route map (pre-Phase 6)

| Route | as_of | comparison_basis | Notes |
|-------|------:|------------------|-------|
| GET `/schedule` | yes | n/a | Full hub summary |
| GET `/schedule/controls` | **missing** | **missing** | **Phase 6 adds** |
| GET `/schedule/review-items` | yes | yes | Live preview merge |
| POST `/schedule/review-items` | yes | yes | Sync prior_update only |
| GET `/schedule/metrics/trends` | yes | n/a | Trend charts (phases 1–8B) |
| GET `/schedule/drilldowns` | yes | n/a | Activity lists |

## Existing analytics inventory

- **Summary service:** `command_summary`, `change_impact`, `remaining_health`, `computed_cpm`, `review_workbench` preview
- **Review workbench:** cue taxonomy, evidence enrichment, advisory language QA (`validate_review_cue_text`)
- **Trend layer:** `ProjectScheduleTrendAggregationService` + `ProjectScheduleDashboardVisualizations` (ControlsOverview + charts)
- **CPM observability:** `ScheduleCpmImportObservabilityRepository.get_latest_for_schedule_version`
- **Private context assembler:** `_review_workbench_context` (version resolution + intelligence inputs)

## Frontend inventory

- **Top hub:** schedule story, trust banner, review workbench preview, driver section
- **Lower block:** `ControlsOverview` + trend panels under heading "Schedule Controls" (renamed in Phase 6)
- **Driver basis:** local `comparisonBasis` in `DriverEvidenceSection` (lifted to page level in Phase 6)

## Gaps addressed in Phase 6

1. No consolidated PM-triage controls contract (`GET /schedule/controls`)
2. No compact top-controls panel near page top
3. CPM observability not PM-summarized on hub
4. No `validate_controls_text` guardrails
5. No shared page-level comparison basis between controls and drivers

## Public context method decision

Added `ProjectScheduleSummaryService.build_schedule_hub_context()` as a narrow public wrapper over `_review_workbench_context`. **Why:** that private helper is the established composition point for version resolution and schedule intelligence assembly; duplicating it in controls would risk drift across hub, workbench, and controls.

## Out of scope (explicit)

- Parser, CPM algorithm, import pipeline changes
- Baseline disposition persistence or baseline sync semantics
- Rewriting ControlsOverview, trend aggregation, or metric contracts
- HTML source support, historical duplicate-row backfill

## Files changed (planned)

- `project_schedule_controls_service.py` (new)
- `project_schedule_summary_service.py` (`build_schedule_hub_context`)
- `project_schedule_narrative_qa.py` (`validate_controls_text`)
- `api.py` (GET `/schedule/controls`)
- `ScheduleControlsPanel.tsx` (new)
- `ProjectSchedulePage.tsx`, `api.ts`, `ProjectScheduleDashboardVisualizations.tsx` (heading only)
- `tests/test_project_schedule_controls_service.py` (new)
