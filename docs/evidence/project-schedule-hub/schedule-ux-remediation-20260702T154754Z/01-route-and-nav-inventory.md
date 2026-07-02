# 01-route-and-nav-inventory.md — Project Schedule UX Remediation

**Stamp**: 20260702T154754Z  
**Branch / Worktree**: fix/schedule-ux-nav-polish-20260702T154747Z @ /Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-ux-nav-polish-20260702T154747Z  
**HEAD**: e5e5efe21489e0afaab2cf1ded0db74622f6fdf6  
**Purpose**: Detailed pre-change inventory of routes, shell nav, active behavior, keyboard/ARIA, and the target post-remediation state.

## In-Scope Routes (exact, from routes.tsx)
```tsx
{ path: 'projects/:projectKey/schedule', element: <ProjectSchedulePage /> },
{ path: 'projects/:projectKey/schedule/import', element: <ProjectScheduleImportPage /> },
{ path: 'projects/:projectKey/schedule/workbench', element: <ProjectScheduleWorkbenchPage /> },
{ path: 'projects/:projectKey/schedule/driver-detail', element: <ProjectScheduleDriverDetailPage /> },
{ path: 'projects/:projectKey/schedule/drivers/:activityId', element: <ProjectScheduleDriverDetailPage /> },
```
- Note: Both driver-detail and drivers/:activityId resolve to the same page component (which extracts activityId from path param or `?activity_id=` query via useSearchParams + useParams).
- No index route exists for bare `/projects/:projectKey/schedule/drivers` (would not match the `:activityId` segment and falls to the catch-all 404).

## Full Relevant Route Context (project shell + global schedule)
- Project workspace children under `/projects/:projectKey/*` use `ProjectWorkspaceShell` (header + `ProjectWorkspaceNav` + children).
- Global schedule intelligence lives at `/schedules/*` (separate chrome via `SchedulePageChrome` / `ScheduleSubnav`).
- Legacy redirects: `/forecasting/schedules/...` → `/schedules/...`.
- Title resolution in `navigationModel.ts` already special-cases `path.includes('/schedule') && path.startsWith('/projects/')` → 'Project • Schedule'.
- No other top-level tabs own schedule content.

## Current Shell Nav Implementation (ProjectWorkspaceNav.tsx — the "Schedule tab")
```tsx
const items = [
  { to: base, label: 'Overview' },
  { to: `${base}/forecasting`, label: 'Forecasting' },
  { to: `${base}/schedule`, label: 'Schedule' },
  { to: `${base}/staffing`, label: 'Staffing' },
  { to: `${base}/exposures`, label: 'Exposures' },
];
<nav className="subnav" aria-label="Project workspace sections">
  {items.map(item => {
    const active = location.pathname === item.to;
    return <Link to={item.to} className={active ? 'active' : ''} aria-current={active ? 'page' : undefined}>...</Link>;
  })}
</nav>
```
- **Flat only**. No children, no dropdown, no grouping.
- Active is *exact* `===` (no subtree match). Consequence: /schedule/import, /workbench, /driver-detail etc. do not activate the Schedule item.
- Styles (index.css): `.subnav { flex gap-1 border-b ... } .subnav a { px-3 py-1 text-sm rounded } .subnav a.active { bg accent tint; color accent }`
- ARIA present on the nav and on active links (good starting point).
- No keyboard menu pattern, no aria-haspopup/expanded for Schedule.

## Post-Remediation Target for Nav (dropdown / grouped)
- The "Schedule" entry becomes a trigger (button) that opens a menu.
- Menu items (direct links, in priority/workflow order):
  1. Schedule Overview — `/projects/:projectKey/schedule`
  2. Import Schedule — `/projects/:projectKey/schedule/import`
  3. Review Workbench — `/projects/:projectKey/schedule/workbench`
  4. Driver Detail — `/projects/:projectKey/schedule/driver-detail`
  5. Activity Drivers — `/projects/:projectKey/schedule/drivers` (new index route + friendly page state)
- The Schedule *trigger* must be visually active (active class + appropriate aria) whenever any of the above paths (or /drivers/:id) is current.
- Keyboard: focusable trigger (Enter/Space toggles), ESC closes, outside click closes, menu items are focusable Links (tab order natural).
- ARIA: trigger `aria-haspopup="menu" aria-expanded={open}`, menu container `role="menu" aria-label="Schedule"`, items `role="menuitem"` (or semantic <a> inside).
- Desktop: popup below trigger (absolute, z, bg matching cards).
- Mobile/responsive fallback: popup still works (subnav already wraps); no requirement for full bottom-sheet unless it degrades badly.
- Non-Schedule tabs untouched.
- Role-gated surfaces (e.g. baseline edit selects) remain visible; only edit controls are disabled or read-only labeled (existing behavior preserved).

## New Route Addition (minimal)
In routes.tsx (inside the `projects/:projectKey` children, before the `drivers/:activityId` entry):
```tsx
{
  path: 'projects/:projectKey/schedule/drivers',
  element: <ProjectScheduleDriverDetailPage />,
},
```
- The existing `drivers/:activityId` stays for direct deep links and any legacy hrefs that use path params.
- `ProjectScheduleDriverDetailPage` will be enhanced (Phase 1/2) to render a friendly "Activity Drivers" index/empty state when no activityId is present (instead of generic unavailable). It already gracefully handles missing ID by skipping the query and showing an EmptyState.

## Active State Behavior — Before vs Target
- Before: only exact `/schedule` lights up the tab.
- Target: any path starting with `/projects/:key/schedule` (including import, workbench, driver-detail, drivers, drivers/xxx) lights the Schedule group/trigger as active. Individual menu items can also indicate their own active state when open (nice-to-have).

## Keyboard / Accessibility Notes (current + target)
Current (good seeds):
- Focus-visible rules global.
- aria-label on nav, aria-current on active.
- Native controls elsewhere have labels.

Target additions (implemented in the dropdown):
- Button trigger + useEffect for Escape + mousedown-outside (exact pattern from ForecastMonthlyExportMenu.tsx which is already audited for a11y).
- Proper menu roles.
- All links remain reachable by Tab when menu open.
- No new focus traps needed (simple menu).
- Will verify in tests (userEvent + queries for roles).

## Other Nav Surfaces (for completeness — out of primary scope but checked)
- `ProjectSubNav.tsx`: used for "all" portfolio views (Meetings/Field Ops/Cost + Schedule Review Dashboard). Unaffected.
- `MainNavigation.tsx` + `PRIMARY_NAV`: top-level "Schedules" (global) + children. Unaffected; project schedule stays contextual.
- `SchedulePageChrome.tsx` / global subnav: for /schedules/* only. Unaffected.
- Title resolver already handles the project schedule subtree (will lightly extend for new sub-pages like "Activity Drivers").

## Import / Workbench / Driver Entry Points (current discoverability)
- Import: route exists + page exists; only reached via manual URL or small badge/modal from Overview.
- Workbench: route + page + header link from Overview + preview card.
- Driver Detail: reached from driver tables/links inside Overview "Where To Look First", Workbench "Open Driver Detail", focused ?driver param, and (rarely) direct /drivers/:id.
- No shell-level persistent entry for any of them today.

## Inventory of Components That Will Need Updates (high level)
(See 02-implementation + 03 for exact diffs later.)
- Nav: ProjectWorkspaceNav.tsx (new)
- Routes: routes.tsx (add 1 route)
- Overview: ProjectSchedulePage.tsx (reorg + CTA changes + fallback text + WBS)
- Driver page: ProjectScheduleDriverDetailPage.tsx (no-ID friendly state + possibly title)
- Card: ReviewCueCard.tsx (badge + action polish)
- Viz: ProjectScheduleDashboardVisualizations.tsx (unavailable + density)
- Baseline: ScheduleBaselineSelector.tsx (copy)
- Labels (minor): scheduleBaselineLabels.ts (optional helpers)
- Tests: ProjectDashboardPage.test.tsx, ProjectSchedulePage.test.tsx (and possibly driver/workbench tests for new states)
- CSS: index.css (minimal dropdown menu styles)
- Evidence only: all new 0x-*.md + screenshots (no source)

## Summary of Gaps This Remediation Closes
- No grouped/dropdown nav for the Schedule module.
- No persistent top-level discoverability for Import, Workbench, Drivers.
- Active state not preserved on nested routes.
- PM workflow buried under technical controls.
- Jargon + overload in cards/charts/fallbacks.
- Dead-end risk for Activity Drivers nav item.

All of the above directly map to the Primary Outcomes and In-Scope Routes in the SOW.

**Inventory complete. No changes made yet. Ready for Phase 1 implementation.**
