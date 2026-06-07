# Component and File Plan

## Core files likely touched

- `frontend/src/index.css`
- `frontend/src/layouts/AppShell.tsx`
- `frontend/src/layouts/SupportNavigation.tsx`
- `frontend/src/navigation/navigationModel.ts`
- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/AdminDataConfidencePage.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/hooks/useOnboardingReadiness.ts`

## New/refactored component inventory

## Layout Components
- `AppTopBar`
- `Sidebar`
- `SidebarFooter`
- `DataQualityIndicator`
- `PrimaryPageLayout`

## Dashboard Components
- `DashboardGrid`
- `DashboardCard`
- `SectionCard`
- `StatusSummaryRow`

## Shared State Components
- `EmptyState`
- `ErrorState`
- `LoadingState`
- `TechnicalDetails`

## Copy Helpers
- `statusCopy.ts`
- `errorCopy.ts`

## Hooks
- `useDataQualitySummary`
- `useOnboardingReadiness normalized accounts update`

## Page Refactors
- `TodayPage`
- `ProjectsPage`
- `MyItemsPage`
- `SettingsPage`
- `AdminDataConfidencePage`

## Implementation notes

- Prefer extracting components under existing folder conventions. If the repo lacks `components/layout` or `components/common`, create narrowly-scoped folders consistent with current naming.
- Keep route and API type changes backwards-compatible unless tests prove dead code.
- For page refactors, preserve existing data-fetch hooks and API response assumptions unless a prompt explicitly updates a hook to an already-existing normalized route.
- Avoid duplicating card shell styles in each page. Use shared primitives.
