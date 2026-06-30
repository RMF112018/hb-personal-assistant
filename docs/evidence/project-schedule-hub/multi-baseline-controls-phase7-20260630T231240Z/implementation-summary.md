# Phase 7 Implementation Summary

## Schema
- Added v96 table `project_schedule_named_baseline_slots` (next available migrator version at implementation time).

## Backend
- `project_schedule_baseline_vocabulary.py` — slot keys, labels, controls comparison basis helpers.
- `project_schedule_named_baseline_repository.py` + `project_schedule_named_baseline_service.py` — project-level slot persistence and validation.
- `GET/PUT /api/projects/{project_key}/schedule/baselines` — viewer read, operator write.
- Extended controls service for named comparison modes, `baseline_context`, explicit comparison labels, and no workbench deep links for named baselines.
- Legacy V90 `/schedule/baseline` and generic `comparison_basis=baseline` on controls API preserved for compatibility.

## Frontend
- `ScheduleBaselineSelector` for operator slot assignment.
- `ScheduleControlsPanel` exposes Prior Update + three named baselines (generic baseline hidden from primary UI).
- Split `controlsComparisonBasis` vs `workbenchComparisonBasis` on `ProjectSchedulePage`.

## Evidence
- See `legacy-vs-named-baseline-models.md` for V90 vs v96 boundary.
