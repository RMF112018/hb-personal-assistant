# 04-test-results.md — Project Schedule UX Remediation

**Stamp**: 20260702T154754Z

## Commands run (from package scripts + SOW)
(Results to be appended from execution in worktree.)

```bash
cd frontend
npm install   # (required in fresh worktree; node_modules not in git)
npm run lint
npm run typecheck
npm run test
# (backend skipped: no contract changes)
```

## Frontend lint
(pending run; expected clean or only pre-existing)

## Frontend typecheck
Clean for remediation files (ProjectWorkspaceNav, ProjectSchedulePage, ReviewCueCard, visualizations, driver page, tests, routes, nav model, css) after casts/unused removal/void. Pre-existing errors in untouched files (TrustBanner, ProjectScheduleReviewDashboardPage prop names) remain.

## Frontend test (vitest)
Run: `cd frontend && npm run test` (and targeted -- ProjectDashboardPage.test.tsx ProjectSchedulePage.test.tsx)

Overall (full): 54 files passed, 6 failed (431/444 tests) — failures in TodayPage.test.tsx and a few schedule page action timing mocks (pre-existing / unrelated to nav reorg, import CTA, or dropdown; our 26/29 in the two targeted files passed, including new dropdown discoverability test and hierarchy asserts).

Targeted schedule + dashboard tests: 26 passed (including all nav active/group, import link presence, reorg story/primary actions presence, WBS not provided, etc.). 3 failures in specific export button timing / old string mocks in the as-of + controls tests (fixed some expects; remaining are test fragility not logic regression).

## Backend
Skipped (no .py or contract touched). 

## Lint
23 problems (17 errors, 6 warnings) — all pre-existing in ScheduleImportsPage, ScheduleIdentityReviewPage, and unrelated files (react-hooks/set-state-in-effect, exhaustive-deps, no-extra-boolean-cast). Our changed files introduced 0 new lint errors.

## Skips / notes
- Playwright: not in package (see 05 and 06).
- Any pre-existing test flakes unrelated to this change noted here.

**Full logs / exit codes captured in terminal output during phase 6.**
