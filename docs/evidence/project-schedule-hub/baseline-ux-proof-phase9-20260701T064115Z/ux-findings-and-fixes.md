# UX Findings and Fixes

## Finding: Controls GET silently coerced unknown comparison_basis
**Impact:** PM could receive prior_update controls while believing an invalid basis was selected.  
**Fix:** `validate_controls_comparison_basis` raises; API returns `400 invalid_comparison_basis`.  
**Files:** `project_schedule_baseline_vocabulary.py`, `api.py`  
**Test:** `test_controls_get_unknown_basis_returns_400`

## Finding: Hub workbench links dropped controls comparison context
**Impact:** Deep navigation lost named basis.  
**Fix:** `workbenchHref()` includes named `comparison_basis`; hub Open Workbench/Queue/focus links use helper.  
**Files:** `ProjectSchedulePage.tsx`, `scheduleBaselineLabels.ts`

## Finding: Workbench basis toggle not reflected in URL
**Impact:** Refresh lost named selection.  
**Fix:** `setSearchParams` on basis toggle.  
**Files:** `ProjectScheduleWorkbenchPage.tsx`

## Finding: Raw schedule version key in baseline selector
**Impact:** PM saw internal IDs.  
**Fix:** Removed parenthetical version key from primary line.  
**Files:** `ScheduleBaselineSelector.tsx`

## Finding: Driver detail showed raw comparison_basis enum
**Impact:** PM-unfriendly labels.  
**Fix:** `labelForComparisonBasis` + `baseline_context` display.  
**Files:** `ProjectScheduleDriverDetailPage.tsx`, `scheduleBaselineLabels.ts`

## Finding: Driver unavailable back link dropped as_of
**Fix:** Preserve `as_of` in EmptyState link.  
**Files:** `ProjectScheduleDriverDetailPage.tsx`

## Finding: Baseline save did not refresh workbench
**Fix:** Invalidate review-items queries on baseline mutation.  
**Files:** `ScheduleBaselineSelector.tsx`

## Finding: Inconsistent driver link query params
**Fix:** `driverDetailHref` emits both `basis` and `comparison_basis`.  
**Files:** `ReviewCueCard.tsx`, `scheduleBaselineLabels.ts`
