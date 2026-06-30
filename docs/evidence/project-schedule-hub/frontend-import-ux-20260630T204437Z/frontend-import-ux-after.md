# Frontend Import UX — After

## New controls

- **Import schedule package** button on `ProjectSchedulePage` opens `ForecastDialog` with `ScheduleImportFlow`
- `/projects/:key/schedule/import` thin wrapper around same `ScheduleImportFlow`
- `no_schedule` empty state uses hub button (not global imports link)

## New components (`frontend/src/components/project-schedule/`)

- `scheduleImportTypes.ts`, `scheduleImportErrors.ts`
- `ScheduleImportPreviewPanel`, `ScheduleImportTechnicalDetails`, `ScheduleImportCommitResult`, `ScheduleImportFlow`

## Import flow

idle → preview → commit → status/retry with supersede path on duplicate

## Preview state

PM-first: files, counts, baselines, equivalence, warning counts; technical JSON collapsed

## Commit/status state

Success / partial / failed with CPM retry when failed

## asOf interaction

Latest: invalidate `['project','schedule', projectKey]`; historical: banner + View latest

## Remaining gaps

- Full HTML source support
- Review workbench alignment
- Historical migration/backfill
- Manual PM UX polish
