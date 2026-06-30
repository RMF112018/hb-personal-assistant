# Frontend Import UX — Before

## Existing controls

- `ProjectSchedulePage`: link to `/projects/:key/schedule/import` (not modal)
- `ProjectScheduleImportPage`: minimal upload/preview/commit without package details
- `ScheduleImportsPage`: full global import UX with package preview, supersede, error codes

## API helpers

All four project-scoped helpers existed in `api.ts` (untyped).

## Missing UX

- Hub modal import entry
- PM-first package preview on project path
- Supersede/duplicate confirm on project path
- Collapsed technical details
- asOf-aware refresh after import
- Shared flow between hub and route
