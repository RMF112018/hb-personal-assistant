# Phase 8A Selected Baseline Workflow Repo Truth

## Current Branch, HEAD, Status

- Branch: detached HEAD in the local workspace.
- HEAD: `9e76158a7861b92a0670d782790da03d210e0e99`.
- Existing local work includes Phase 5, Phase 6, and Phase 7 schedule-controls changes. Phase 8A must preserve that work.

## Existing Baseline Tables

- `project_schedule_baseline_selections` exists in `src/hb_assistant/store/project_schedule_hub_tables.py`.
- Columns:
  - `selection_id`
  - `project_key`
  - `current_schedule_version_key`
  - `selected_baseline_schedule_version_key`
  - `selection_status`
  - `selected_by_operator`
  - `selected_at`
  - `selection_note`
  - `created_at`
  - `updated_at`
- The table has a partial unique active-selection index on `(project_key, current_schedule_version_key, selection_status)` where `selection_status='active'`.
- The existing repository supersedes prior active selections before inserting a new active selection.
- There is no persisted recompute status column for selected-baseline workflow readiness.

Related imported baseline tables already exist:

- `schedule_baseline_projects`
- `schedule_baseline_activities`
- `schedule_baseline_relationships`
- `schedule_baseline_activity_crosswalk`
- `schedule_baseline_health_facts`

Phase 8A treats selected baseline as a committed schedule version key. It does not reinterpret a baseline project key as a schedule version key.

## Existing Routes And Auth

- `GET /api/projects/{project_key}/schedule/baseline`
  - Viewer-readable.
  - Currently returns `available`, raw `selection`, and `baseline_summary`.
- `PUT /api/projects/{project_key}/schedule/baseline`
  - Operator/admin-gated through `require_operator_role`.
  - Currently accepts `current_schedule_version_key`, `selected_baseline_schedule_version_key`, and optional `selection_note`.
  - Currently persists via `ProjectScheduleHubRepository.set_baseline_selection`.

## Existing Summary Behavior

- `ProjectScheduleSummaryService._baseline_summary` reads the active baseline selection from `project_schedule_baseline_selections`.
- Without a selection, status is `no_selection` or `original_only`.
- With any active selection, current behavior marks the baseline state as `ready`, compares current to selected baseline with `ProjectScheduleComparisonService.compare_versions`, and surfaces that comparison only under `baseline_summary`.
- Prior-update comparison remains separate under `change_impact`.

## Existing Phase 6 Trend Behavior

- `ProjectScheduleTrendAggregationService` supports only metrics in `SUPPORTED_TREND_METRICS`.
- `schedule_compression_ratio` exists in the Phase 5 formula contract with readiness `ready_after_baseline_selection`.
- It is currently not in `SUPPORTED_TREND_METRICS`, so Phase 6 returns `metric_not_trend_ready` before any selected-baseline-specific readiness can run.

## Existing Frontend Behavior

- `ProjectSchedulePage` requests Phase 6 batch trends using the resolved schedule summary as-of/data-date context.
- `ProjectScheduleDashboardVisualizations` renders supported trend payloads and blocked cards.
- `schedule_compression_ratio` currently appears as a generic blocked card with the reason `Requires selected baseline`.
- The frontend does not compute baseline formulas.

## Phase 8A Proven Gaps

- Baseline PUT lacks validation that current and selected baseline versions are committed, belong to the same project, are not the same version, are not future-dated relative to current, and match schedule identity when identity evidence exists.
- Baseline GET does not return a full selected-baseline readiness envelope.
- Hub summary treats any active baseline selection as ready even when matching/duration facts are not proven.
- `schedule_compression_ratio` cannot return selected-baseline readiness because the trend service blocks it before metric-specific handling.
- Frontend blocked-card copy cannot show selected-baseline label/date or recompute/readiness status when the backend has that state.
