# Phase A1 — Project Schedule Import Center + CPM Recompute

**Branch:** `feat/project-schedule-import-center-cpm`  
**Base commit:** `f6ddaf22a83546be47f6c49b7a31e259b4acf10d`  
**Schema:** V92 (no migration added)

## Delivered

- Project-scoped import routes under `/api/projects/{key}/schedule/import-*`
- `ProjectScheduleImportPipelineService` orchestration + 11-stage pipeline status
- `ScheduleCpmRecomputeService` synchronous six-step CPM chain on every import commit
- Project import UI at `/projects/:projectKey/schedule/import`
- Hub "Import Schedule" CTA + project-native import URLs
- Narrative credibility repair (zero-day movement, WBS context, driver context metadata)

## CPM wiring

- **Entrypoint:** `ScheduleCpmRecomputeService.recompute()` → `ScheduleCpmGraphService` chain
- **Mode:** synchronous, immediately after successful `ScheduleImportService.commit()`
- **Standalone `/schedules/imports`:** upgraded via shared `commit()` path

## Validation

- Backend: `tests/test_project_schedule_import_pipeline.py` + schedule import/CPM/hub/narrative regressions
- Frontend: `ProjectScheduleImportPage.test.tsx`, `ProjectSchedulePage.test.tsx`, `ScheduleImportsPage.test.tsx`
- `npm run typecheck` passed