# 00-baseline.md — Project Schedule UX Remediation Baseline (Phase 0)

**Stamp (UTC)**: 20260702T154754Z  
**Evidence dir**: `docs/evidence/project-schedule-hub/schedule-ux-remediation-20260702T154754Z/`  
**Branch**: `fix/schedule-ux-nav-polish-20260702T154747Z`  
**Worktree**: `/Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z`  
**Base HEAD (at worktree creation + all baseline recording)**: `e5e5efe21489e0afaab2cf1ded0db74622f6fdf6` (origin/main @ Merge pull request #267 from RMF112018/validation/schedule-clean-db-full-20260702T124718Z)  
**Local git status at recording (clean)**: (no output from `git status --short`)  
**Date of baseline**: 2026-07-02 (today per session)  
**Operator**: Bobby Fetting  
**Repo root in worktree**: /Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z

## Explicit Safety Statement (before any code change)
- No live DB path was used for any read or write.
- No schedule import (live or otherwise) was performed.
- No mutation of the live Obsidian vault occurred.
- All commands so far: readonly git + mkdir under docs/evidence (new tree) + venv activate + PYTHONPATH export.
- Validation DB (if needed later): will be a *copy* only under /tmp/hb-personal-assistant-schedule-ux/... per SOW.
- This baseline was recorded with zero edits to source.

## Starting Procedure Executed (verbatim)
```bash
cd /Users/bobbyfetting/hb-personal-assistant || exit 1
git fetch origin --prune
BRANCH="fix/schedule-ux-nav-polish-$(date -u +%Y%m%dT%H%M%SZ)"
WORKTREE="/Users/bobbyfetting/hb-personal-assistant-worktrees/$BRANCH"
git worktree add "$WORKTREE" -b "$BRANCH" origin/main
cd "$WORKTREE" || exit 1
source /Users/bobbyfetting/hb-personal-assistant/.venv/bin/activate
unset PYTHONPATH
export PYTHONPATH="$PWD/src:$PWD/subrepos/construction-financial-review/src"
# then git status/rev/log + mkdir evidence
```
- All succeeded. Venv Python 3.14.5 active. PYTHONPATH includes worktree src + subrepos/cfr.
- Worktree is isolated (edits here do not affect the /Users/bobbyfetting/hb-personal-assistant checkout).

## Current Schedule Route Inventory (from frontend/src/app/routes.tsx in worktree)
Exact project-scoped routes (the in-scope surface per SOW):
- `/projects/:projectKey/schedule` → `ProjectSchedulePage` (Overview)
- `/projects/:projectKey/schedule/import` → `ProjectScheduleImportPage`
- `/projects/:projectKey/schedule/workbench` → `ProjectScheduleWorkbenchPage`
- `/projects/:projectKey/schedule/driver-detail` → `ProjectScheduleDriverDetailPage`
- `/projects/:projectKey/schedule/drivers/:activityId` → `ProjectScheduleDriverDetailPage` (shares component; uses path param or ?activity_id= query)

Additional context (not primary for this remediation but present):
- Global `/schedules/*` family (imports, versions, activities, quality, cpm, etc.) with redirects from legacy forecasting-nested paths.
- `/projects/all/schedule/review` (portfolio review dashboard, uses different subnav).

No existing index route at `/projects/:projectKey/schedule/drivers` (without :activityId). Visiting a bare `/drivers` segment falls through to 404/not-found (no matching route).

## Current Shell Navigation Behavior (ProjectWorkspaceNav + shell)
File: `frontend/src/components/projects/ProjectWorkspaceNav.tsx`
- Flat list of 5 `<Link>` items inside `<nav className="subnav" aria-label="Project workspace sections">`:
  - Overview → /projects/:key
  - Forecasting → /projects/:key/forecasting
  - Schedule → /projects/:key/schedule   (exact match only for .active + aria-current="page")
  - Staffing, Exposures
- Active logic: `location.pathname === item.to` (strict; no startsWith for children).
- Result: on /schedule/import or /workbench the "Schedule" item does *not* render as active.
- Used exclusively inside `ProjectWorkspaceShell` (which also renders header + children).
- No dropdown, no grouping, no ARIA menu roles for Schedule.
- Other project subnavs (ProjectSubNav for "all" views) are also flat.
- Main sidebar (MainNavigation + navigationModel) treats project schedule as *contextual* (title resolver catches `/schedule` under /projects/ as "Project • Schedule").

## Current Import Discoverability
- Dedicated route + page exists (`ProjectScheduleImportPage` + `ScheduleImportFlow variant="page"`).
- On Overview (`ProjectSchedulePage`):
  - Loaded state: small `.badge` "Import schedule package" button in header actions → opens `ForecastDialog` + modal flow (not the route).
  - No-schedule state: `EmptyState` action button "Import schedule package" → same modal.
  - No prominent persistent link or card to the `/import` route from Overview.
- Dropdown nav does not exist, so no "Import Schedule" entry in shell.
- Links inside import results point back to `/schedule` (overview) and `/workbench`.
- Discoverability relies on header badge (low visual weight) or empty state.

## Current Workbench Discoverability
- Dedicated route + page exists.
- On Overview: "Open Workbench" `.badge` Link (uses `workbenchHref` helper) + small "Review Workbench" preview card with "Open Queue" link.
- No shell-level direct entry except the flat Schedule tab (which doesn't stay active).
- Workbench itself has "Back to Schedule" links.

## Current Schedule Overview Section Order (from ProjectSchedulePage.tsx render)
(Approximate top-to-bottom in loaded state; no-schedule early-returns a minimal empty + import button.)
1. New-import banner (conditional) + header row (`<h3>Schedule</h3>`, as-of/date picker, "Import schedule package" badge, "Open Workbench" link, "Export Memo" conditional).
2. Focused review link card (if ?driver or ?review params).
3. `<TrustBanner>` (identity/analytics trust).
4. `<ScheduleControlsPanel>` (comparison basis buttons + heavy quality/controls/scorecard/technical).
5. `<ScheduleBaselineSelector>` ("Baseline Anchors" SectionCard with slots).
6. Schedule Story card (headline, synopsis, metrics grid including "Float Pressure" with "source-export negative float" helper).
7. Viz card: `<ProjectScheduleDashboardVisualizations>` ("Controls Trend Analytics" + many recharts + "Schedule Health / Feasibility" + "Execution Reliability" + legacy trend/driver/milestone/float cards).
8. Review Workbench preview card (if available) + "Open Queue".
9. "Where To Look First" (driver metrics + `<DriverEvidenceSection>` with tabs/tables).
10. 2-col: Source Float (Export), Computed CPM.
11. Conditional "Baseline Comparison".
12. 3-col grid: Remaining-Work Health, "What Changed" (with DrilldownPanels), Critical Path.
13. 2-col: "Review Next" (actions), "Trends".
14. `<TechnicalDetails summary="Technical evidence">` (links + note; collapsed by default).
- Lots of overlapping "What Changed", health, driver, review, trend, and technical content competing for attention above the fold. PM story is present but buried after controls/baselines.

## Discovered Test / Validation Commands (from package manifests in worktree)
- Frontend (cd frontend):
  - `npm run lint`
  - `npm run typecheck` (tsc -b)
  - `npm run test` (vitest run) / `npm run test:watch`
  - `npm run build`
  - `npm run smoke:frontend`
- Root / schedule domain:
  - `./scripts/test-schedule.sh` (curated fast pytest bundle, sets PYTHONPATH + uses .venv python; many schedule_* tests)
  - `pytest tests/test_schedule*.py ...` (manual)
- Evidence/visual helpers (prior art):
  - `frontend/e2e/helpers/scheduleLoadedState.ts` + python capture scripts that temp `npm install playwright` + node script for shots (used in phase12, phase11 evidence).
  - DB copy pattern: `cp "$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" /tmp/.../copy.sqlite ; export HB_ASSISTANT_DB_PATH=...`
- Other: ruff/mypy on py side (not primary here), `hb-assistant` CLI.

No Playwright in package.json devDeps or lock (confirmed).

## Key Files Inspected for Baseline (worktree paths, readonly reads + greps)
- frontend/src/app/routes.tsx (full route table)
- frontend/src/components/projects/ProjectWorkspaceShell.tsx + ProjectWorkspaceNav.tsx + ProjectWorkspaceHeader.tsx + ProjectSubNav.tsx
- frontend/src/pages/ProjectSchedulePage.tsx (full + sections), ProjectScheduleImportPage.tsx, ProjectScheduleWorkbenchPage.tsx, ProjectScheduleDriverDetailPage.tsx (and .test.tsx variants)
- frontend/src/components/project-schedule/* (ReviewCueCard.tsx, ScheduleBaselineSelector.tsx, ScheduleControlsPanel.tsx + test, TrustBanner.tsx, ScheduleImportFlow.tsx + siblings)
- frontend/src/components/projects/ProjectScheduleDashboardVisualizations.tsx + projectScheduleDashboardData.ts
- frontend/src/lib/api.ts (schedule methods), scheduleBaselineLabels.ts (labels + href helpers) + .test.ts
- frontend/src/navigation/navigationModel.ts + layouts/MainNavigation.tsx + AppShell.tsx
- frontend/package.json (scripts), frontend/src/index.css (subnav)
- pyproject.toml, scripts/test-schedule.sh, scripts/smoke-local.sh
- Multiple prior evidence bundles under docs/evidence/project-schedule-hub/ (for route/screenshot patterns, copied-DB usage, tropical data shape)
- Grep across frontend/src for "subnav", "Schedule", "dropdown", "ProjectWorkspaceNav", "Not yet available", "WBS not in source", badge counts in cards, etc.

## Screenshot Package Inventory (this task)
- No new screenshot tarball or package attached in the current user_query / session context.
- Baseline relies on code truth + prior evidence screenshots (e.g. baseline-pm-readiness-phase12-20260701T081419Z/screenshots/, driver-route-encoding-phase11-..., named-baseline-... trees). These show current overloaded state (dense controls early, badge-heavy workbench, flat nav).
- All new screenshots will be captured fresh in this evidence tree under `screenshots/` during Phase 6 (using copied DB + tropical route) and inventoried in `02-screenshot-inventory.md`.

## Next (per plan)
- Write `01-route-and-nav-inventory.md` (detailed file-by-file + current vs target).
- Proceed to Phase 1 edits only after baseline artifacts written and this note committed in evidence.
- All subsequent commands will be run from the worktree with the exported env.

**Baseline complete. No source mutations yet. Ready for implementation phases.**
