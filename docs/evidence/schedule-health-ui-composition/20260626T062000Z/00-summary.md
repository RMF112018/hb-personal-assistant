# Schedule Health UI Composition Summary

## Branch / Base

- Branch: `fix/schedule-health-ui-composition-20260626000000`
- Base ref: `origin/main`
- Base commit: `185de7ff54520f5a4299300d914e21604a22f295`
- Base commit title: `feat(schedule): add import health foundation (#151)`

## Changed Surface

- Preserved `/schedules/quality` and changed its visible page concept to `Schedule Health`.
- Added `/schedules/health` as an alias to the same page.
- Added frontend `getScheduleHealthData(scheduleVersionKey, projectKey?)` API client and tolerant response types.
- Refactored `ScheduleQualityPage` to use V75 health-data as the primary page contract.
- Kept legacy quality details as supporting DCMA/source/GAO tables.

## Files Changed

- `frontend/src/app/routes.tsx`
- `frontend/src/components/schedule/SchedulePageChrome.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/sourcesApi.test.ts`
- `frontend/src/navigation/navigationModel.ts`
- `frontend/src/navigation/navigationModel.test.ts`
- `frontend/src/pages/ScheduleQualityPage.tsx`
- `frontend/src/pages/ScheduleQualityPage.test.tsx`
- `frontend/src/pages/ScheduleRoutes.test.tsx`
- `docs/evidence/schedule-health-ui-composition/20260626T062000Z/*`

## Validation Summary

- V75 gate: passed.
- `cat frontend/package.json`: scripts confirmed: `test`, `typecheck`, `lint`.
- `bash -n scripts/test-schedule.sh`: passed.
- `scripts/test-schedule.sh`: `131 passed, 2 deselected, 1 warning`.
- Frontend typecheck via existing dependency symlink: passed.
- Focused Vitest: `31 passed`.
- Touched-file ESLint: passed.
- Full frontend Vitest: failed in unrelated `MyItemsPage` and `TodayPage` fallback-text tests; Schedule Health tests passed.
- Full frontend ESLint: failed in unrelated existing files; touched-file lint passed.

## Screenshot Status

Screenshot capture was attempted with Vite and the in-app browser. Vite started successfully on `http://127.0.0.1:5178/`, but the browser API did not expose request interception and direct Node mock API launch on port 8000 was blocked by command policy. Screenshot evidence is therefore blocked in this environment rather than fabricated.
