# Phase 7 Repo-Truth Audit — Multi-Baseline Schedule Controls

**Audit date:** 2026-06-30  
**Base commit (origin/main):** `0eb5f2846252f1900f5f4700c13aedcf9336cc16`  
**Worktree branch:** `feature/schedule-multi-baseline-controls-phase7-20260630T231240Z`  
**Schema version at audit:** `LATEST_SCHEMA_VERSION = 95` → Phase 7 adds **v96**

## Phase 6 prerequisite: PRESENT

| Artifact | Location |
|---|---|
| `ProjectScheduleControlsService.build_controls` | `src/hb_assistant/construction/analytics/project_schedule_controls_service.py` |
| `GET /api/projects/{project_key}/schedule/controls` | `src/hb_assistant/construction/analytics/api.py` L1218 |
| `validate_controls_text` | `src/hb_assistant/construction/analytics/project_schedule_narrative_qa.py` |
| `ScheduleControlsPanel` | `frontend/src/components/project-schedule/ScheduleControlsPanel.tsx` |
| Controls Trend Analytics rename | `frontend/src/components/projects/ProjectScheduleDashboardVisualizations.tsx` |
| Phase 6 tests | `tests/test_project_schedule_controls_service.py` |

## Route map

| Route | Method | Role | Purpose |
|---|---|---|---|
| `/api/projects/{project_key}/schedule/controls` | GET | viewer | PM controls (Phase 6; extended Phase 7) |
| `/api/projects/{project_key}/schedule/baseline` | GET/PUT | viewer/operator | **Legacy** single baseline per current version (V90) |
| `/api/projects/{project_key}/schedule/baselines` | GET/PUT | viewer/operator | **New** three named project-level slots (v96) |
| `/api/projects/{project_key}/schedule/review` | GET/POST | viewer/operator | Review workbench (`prior_update` \| `baseline`) |

## Current `comparison_basis` vocabulary

- **Controls API (Phase 6):** `prior_update` \| `baseline` (whitelist in controls service + api route)
- **Review workbench:** `prior_update` \| `baseline` (unchanged in Phase 7)
- **Driver hub keys:** `prior_update`, `baseline` in `change_driver_analysis`
- **Phase 7 controls additions:** `current_contract_baseline`, `previous_progress_update_baseline`, `secondary_progress_update_baseline`
- **Backend BC:** generic `baseline` remains accepted on controls API; not exposed in Phase 7 UI

## Legacy V90 vs named-slot model

See companion doc: [`legacy-vs-named-baseline-models.md`](legacy-vs-named-baseline-models.md).

**Persistence recommendation:** New table `project_schedule_named_baseline_slots` at schema v96. Do not alter `project_schedule_baseline_selections` (V90).

## Version resolution

- Current/as-of: `ProjectScheduleSummaryService._resolve_current` over `_hub_project_versions`
- Prior update: `_resolve_previous`
- Named baseline eligibility: version must belong to project, `schedule_data_date` ≤ current as-of data date, and **must not equal current/as-of schedule version key**

## Comparison machinery

- Reuse `ProjectScheduleDriverAnalysisService.build_hub_analysis(baseline_key=...)`
- Reuse `_baseline_summary` comparison logic via new `build_baseline_summary_for_version` helper with explicit version key
- Review preview internally uses `comparison_basis=baseline` for named slots; API response preserves named basis

## Workbench link boundary (Phase 7 amendment)

Named baseline controls must **not** emit Review Workbench `review_item` links or driver links with unrecognized basis values. Workbench only supports `prior_update` \| `baseline` tied to V90 legacy selection — no silent mapping from named slots.

## Files expected to change

- Store: `project_schedule_named_baseline_tables.py`, `project_schedule_named_baseline_repository.py`, `migrator.py`
- Analytics: `project_schedule_baseline_vocabulary.py`, `project_schedule_named_baseline_service.py`, `project_schedule_controls_service.py`, `project_schedule_summary_service.py`, `project_schedule_narrative_qa.py`, `api.py`
- Frontend: `api.ts`, `ScheduleBaselineSelector.tsx`, `ScheduleControlsPanel.tsx`, `ProjectSchedulePage.tsx`, tests
- Tests: `tests/test_project_schedule_multi_baseline_controls.py`, updates to hub API / page tests
- Evidence: this directory

## Files explicitly out of scope

- CPM algorithm, parser, import pipeline, trend chart system
- Review workbench route/handler changes
- V90 `project_schedule_baseline_selections` schema or `/schedule/baseline` behavior
- Auto contract baseline detection, legal/claim narratives

## Test plan

1. New `tests/test_project_schedule_multi_baseline_controls.py` — 20 cases from Phase 7 prompt
2. Phase 6 controls tests remain green (prior_update + legacy baseline BC)
3. `tests/test_project_schedule_baseline_selection.py` unchanged (legacy)
4. Frontend: selector, split comparison basis, API client tests

## Implementation risks

1. Shared page state — mitigated by splitting `controlsComparisonBasis` vs `workbenchComparisonBasis`
2. Duplicate validation — validate against **post-update** slot state per amendment
3. `frontend/src/lib` gitignore — use `git add -f` if needed
