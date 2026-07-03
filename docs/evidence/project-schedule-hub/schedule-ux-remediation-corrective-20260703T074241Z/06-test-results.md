# Test results

**Date:** 2026-07-03  
**Worktree:** `fix/schedule-ux-nav-polish-20260702T154747Z`

## Targeted vitest (corrective scope)

```bash
cd frontend
npm run test -- --run \
  src/pages/ProjectSchedulePage.test.tsx \
  src/lib/scheduleDataState.test.ts \
  src/components/projects/ProjectWorkspaceNav.test.tsx
```

**Result:** 3 files, **26 tests passed**, 0 failed

| File | Tests |
|------|-------|
| `src/lib/scheduleDataState.test.ts` | 3 |
| `src/components/projects/ProjectWorkspaceNav.test.tsx` | 3 |
| `src/pages/ProjectSchedulePage.test.tsx` | 20 |

Key assertions: Manage Baselines in dropdown + Primary Actions; refreshing banner; unavailable not shown during fetch; query key dimensions.

## Typecheck

```bash
npm run typecheck
```

**Result:** Failed — **pre-existing errors, not introduced by this pass**

| File | Errors |
|------|--------|
| `src/components/project-schedule/TrustBanner.tsx` | TS2322 (unrelated) |
| `src/pages/ProjectScheduleReviewDashboardPage.tsx` | TS2322 PrimaryPageLayout / EmptyState props (unrelated) |

No typecheck errors in touched corrective files.

## Lint

```bash
npm run lint
```

**Result:** 20 problems (14 errors, 6 warnings) — **all pre-existing** in unrelated files (`ScheduleImportsPage.tsx`, `ScheduleIdentityReviewPage.tsx`, etc.). No new lint errors in corrective files.

## Backend tests

Not run — no backend code changed in this corrective pass.
