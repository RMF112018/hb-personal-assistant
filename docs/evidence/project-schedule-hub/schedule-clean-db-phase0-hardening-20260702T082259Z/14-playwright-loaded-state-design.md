# Loaded-state recipe helper design

`frontend/e2e/helpers/scheduleLoadedState.ts` provides dependency-neutral loaded-state recipes and proof JSON builders.

## Scope

- No Playwright dependency in Phase 0
- Vitest unit tests validate recipe coverage and proof shape
- Future evidence capture scripts can import recipes without `package.json` churn

## Recipes

`schedule_hub`, `schedule_import`, `schedule_controls`, `schedule_workbench`, `schedule_review_dashboard`, `driver_detail`
