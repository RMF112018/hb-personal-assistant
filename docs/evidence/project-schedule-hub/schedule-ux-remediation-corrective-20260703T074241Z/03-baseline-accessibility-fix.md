# Baseline accessibility fix

## Problem

Baseline management (`ScheduleBaselineSelector`) was rendered below trend visualizations. "Manage Baselines" was not in the Schedule dropdown. Operators had to scroll past charts to reach comparison anchors.

## Fix

### Dedicated route

`/projects/:projectKey/schedule/baselines` → `ProjectScheduleBaselinesPage.tsx`

Renders `ScheduleBaselineSelector` as the primary surface with `as_of` context preserved.

### Layout reorder (overview)

1. PM Story  
2. Primary Actions — Import, **Manage Baselines**, Workbench, Export  
3. Baseline / Comparison Context (`#baseline-management`)  
4. Schedule Controls  
5. Trends / visualizations  
6. Workbench preview, drivers, technical CPM  

### Navigation

`ProjectWorkspaceNav.tsx`:

- Schedule dropdown includes **Manage Baselines** → `/schedule/baselines`
- `scheduleNavHref()` preserves `as_of` and `comparison_basis` on analytical routes
- Import route strips analytical params (`mode: 'import'`)

### Runtime functional check (copied DB, read-only)

Against copied DB with operator role:

- Dropdown shows Manage Baselines (`02-schedule-dropdown-open-manage-baselines.png`)
- Dedicated baselines page loads selector (`03-baseline-management-visible.png`)
- Primary Actions link visible on overview (`01-overview-top-asof-2026-06-22.png`)

**No baseline mutations** were performed during this corrective pass.

## Files changed

- `frontend/src/pages/ProjectScheduleBaselinesPage.tsx` (new)
- `frontend/src/app/routes.tsx`
- `frontend/src/pages/ProjectSchedulePage.tsx`
- `frontend/src/components/projects/ProjectWorkspaceNav.tsx`
- `frontend/src/lib/scheduleNavLinks.ts`
