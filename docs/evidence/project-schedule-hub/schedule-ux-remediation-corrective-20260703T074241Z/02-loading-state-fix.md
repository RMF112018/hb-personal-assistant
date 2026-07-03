# Loading state fix

## Problem

`ProjectSchedulePage` used `isLoading` alone to gate child panels. With `as_of` changes, React Query refetched while `keepPreviousData` retained prior payloads. Children rendered final "unavailable" labels against stale identity.

## Fix

### Query keys (strict dimensions)

All schedule-dependent queries include:

- `projectKey`
- `asOf` via `scheduleQueryKeySuffix(asOf)` (`'latest'` when absent)
- `comparisonBasis` where the endpoint accepts it (controls, workbench)

Baselines key unified:

`['project', 'schedule', projectKey, 'baselines', asOf || 'latest']`

### `keepPreviousData` + identity guard

- All overview queries use `placeholderData: keepPreviousData`
- `isScheduleResponseStale(payload, requestAsOf, isFetching)` compares `payload.as_of_date` to requested `as_of`
- Page-level `summaryStale` drives `schedule-refreshing-banner` (`data-testid="schedule-refreshing-banner"`)
- Children receive `summaryFetching`, `trendFetching`, `controlsFetching`, `trendDataStale`

### Child panel behavior

| Component | Change |
|-----------|--------|
| `ProjectScheduleDashboardVisualizations` | `metricPanelUiState` — no final unavailable while loading/refreshing/stale |
| `ScheduleControlsPanel` | `fetching` prop suppresses premature empty states |
| `ScheduleBaselineSelector` | `fetching` prop; no silent `null` during fetch |
| `ProjectScheduleWorkbenchPage` | `YYYY-MM-DD` validation; aligned baselines query key |

## Files changed

- `frontend/src/pages/ProjectSchedulePage.tsx`
- `frontend/src/pages/ProjectScheduleWorkbenchPage.tsx`
- `frontend/src/components/projects/ProjectScheduleDashboardVisualizations.tsx`
- `frontend/src/components/project-schedule/ScheduleControlsPanel.tsx`
- `frontend/src/components/project-schedule/ScheduleBaselineSelector.tsx`
- `frontend/src/lib/scheduleDataState.ts`

## Test coverage

`ProjectSchedulePage.test.tsx` — refreshing banner and unavailable-not-shown-during-fetch assertions (26 tests total across corrective suite).
