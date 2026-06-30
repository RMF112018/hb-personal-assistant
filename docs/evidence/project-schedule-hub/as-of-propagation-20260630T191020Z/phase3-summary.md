# Phase 3 Schedule as_of Propagation Summary

## Base and prerequisites
- Worktree: `/Users/bobbyfetting/hb-personal-assistant-worktrees/feature/schedule-as-of-propagation-20260630T191020Z`
- Branch: `feature/schedule-as-of-propagation-20260630T191020Z`
- Current base after rebase: `origin/main` at `112ff008c830fa3c5c2452f113d444512e127d56`
- Initial prerequisite merge present: `9181d65a800b8836be883de5c4da57bb76f71837`
- Prerequisites verified reachable from `origin/main`: `9181d65a`, `3a84aab2`, `a787d709`
- Evidence: `prerequisite-proof.txt`

## Implementation
- Backend summary route now accepts canonical query parameter `as_of`, rejects malformed input with `400 invalid_as_of_date`, and forwards the parsed date to `ProjectScheduleSummaryService.build_summary`.
- Baseline GET/PUT now accept `as_of`; read context and post-selection summary refresh preserve the active date.
- `ProjectScheduleSummaryService.build_drilldown(..., drilldown_type="upstream_cues")` now calls `build_summary(project_key, as_of=as_of)`.
- Frontend summary and baseline helpers accept `options?: { asOf?: string | null }` and emit backend `as_of` only for non-empty values.
- `ProjectSchedulePage` uses narrow URL `as_of` state, adds a minimal `As-of date` input, includes `asOf || latest` in date-sensitive query keys, and forwards the same selected date to summary, baseline, trend, driver, drilldown, workbench-link, focused-link, and export flows.

## Tests and proof
- Backend route/service coverage: summary accept/reject/forward, historical version resolution, upstream cues historical context, baseline GET/PUT propagation, review/trend/export route propagation.
- Frontend page coverage: summary, baseline, trends, drilldown, and export helpers receive selected `asOf`; latest/current requests pass `undefined`; default PM-facing view does not introduce raw internal IDs.
- Frontend API-helper coverage: summary/baseline omit `as_of` for empty values and emit it for non-empty `asOf`; trend/drilldown/review use the same `asOf` option name.
- Route map and acceptance proof: `route-map-before-after.md`, `as-of-acceptance-proof.md`.

## Validation after rebase
- `pytest-focused-backend.txt`: 48 passed.
- `pytest-schedule-as-of.txt`: 5 passed.
- `py-compile.txt`: passed with no output.
- `scripts-test-schedule.txt`: 323 passed, 2 deselected.
- `npm-typecheck.txt`: passed.
- `vitest-project-schedule-page-api.txt`: 14 passed across focused Project Schedule page/API helper tests.
- `vitest-api-target-probe.txt`: `npm run test -- api` is valid in this repo and passed 17 tests.

## Final status before amend
See `git-status-final.txt`, `git-diff-stat-final.txt`, `git-diff-check.txt`, and `git-head-final.txt`.
