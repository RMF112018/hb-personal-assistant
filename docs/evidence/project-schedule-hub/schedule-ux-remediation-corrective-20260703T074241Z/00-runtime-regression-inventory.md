# Runtime regression inventory

**Branch / worktree:** `fix/schedule-ux-nav-polish-20260702T154747Z`  
**Prior HEAD:** `8a293bf76bce55ae5a395845b9e3b87f3c8f9b16`  
**Corrective evidence package:** `schedule-ux-remediation-corrective-20260703T074241Z`  
**Prior remediation package (as-run baseline only):** `schedule-ux-remediation-20260702T154754Z`

## Observed defects (pre-corrective)

| # | Symptom | Classification | Notes |
|---|---------|----------------|-------|
| 1 | Baseline management buried below trends; no direct nav entry | UX regression | `ScheduleBaselineSelector` rendered after visualizations; no dropdown item |
| 2 | Changing `as_of` shows "Trend data not available" / "CPM unavailable" while fetch in flight | Async state regression | Page gated on `isLoading` only; retained data treated as final |
| 3 | Old schedule metrics shown briefly after `as_of` change | Stale query-key / retained-data identity bug | Missing identity guard with `keepPreviousData` |
| 4 | Shell nav dropped `?as_of=` when switching schedule sub-pages | UX regression | Import and analytical routes shared links without selective preservation |
| 5 | CPM/trend empty copy identical for loading, missing payload, and true unavailability | UX + async state | No reason-aware taxonomy |
| 6 | Copied DB CPM completeness varies by resolved version | Copied DB / data-readiness | `as_of=2026-06-22` resolves to version without full CPM runs at API; `as_of=2026-06-29` has full runs |
| 7 | Prior evidence screenshots not from running localhost app | Evidence gap | Corrective package requires real runtime captures only |

## Corrective scope

- Frontend query keys, loading/refreshing gates, identity guard, baseline route + nav, state taxonomy helpers
- No CPM engine changes, no live DB/import/vault, no push

## Data source for validation

Copied DB only: `/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite`
