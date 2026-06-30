# Phase 8 Frontend Proof

## Typecheck
`npm run typecheck` — pass

## Tests
- `ProjectScheduleWorkbenchPage.test.tsx` — 4 passed (operator sync still uses prior_update default)
- `ProjectSchedulePage.test.tsx` — 17 passed (controls + named baseline selector unchanged)

## UX changes
- Workbench reads `comparison_basis` from URL (controls deep links)
- Named baseline buttons sourced from `/schedule/baselines` selected slots
- Operator auto-sync skipped for named basis (read-only preview)
- Driver detail accepts `basis` or `comparison_basis`; workbench link preserves named basis + as_of
