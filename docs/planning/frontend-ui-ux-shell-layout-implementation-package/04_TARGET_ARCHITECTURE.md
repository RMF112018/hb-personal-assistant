# Target Architecture

## Shell target

```text
html/body/#root
  height: 100%
  overflow: hidden

AppShell
  height: 100dvh
  overflow: hidden
  display: flex

Sidebar
  width: fixed on desktop
  height: 100dvh
  flex-shrink: 0
  display: flex column
  overflow: hidden

SidebarTop
  brand / app identity

SidebarNavRegion
  primary navigation
  overflow-y: auto only if nav itself exceeds available space
  min-height: 0

SidebarFooter
  pinned below nav region
  DataQualityIndicator
  SupportActions: Settings, Admin/Data Health when allowed

MainPanel
  flex: 1
  min-width: 0
  min-height: 0
  display: flex column

TopBar/PageHeader
  stable height

PageScrollRegion
  flex: 1
  min-height: 0
  overflow-y: auto
  overflow-x: hidden
```

## Dashboard grid target

Use a reusable CSS Grid based dashboard system:

- mobile: one column;
- tablet: two columns when width allows;
- desktop: `repeat(auto-fit, minmax(...))` with card span helpers;
- important/priority cards appear first in DOM and visual order;
- no CSS columns for primary content because columns can confuse reading order;
- no JS masonry library unless current stack proves CSS Grid inadequate.

Recommended primitives:

- `PrimaryPageLayout`
- `DashboardGrid`
- `DashboardCard`
- `SectionCard`
- `StatusSummaryRow`
- `EmptyState`
- `ErrorState`
- `LoadingState`
- `TechnicalDetails`
- `DataQualityIndicator`

## Copy architecture target

Centralize status and error translations:

- `statusCopy.ts`: auth/readiness/data-quality/brief/source-status labels.
- `errorCopy.ts`: user-safe error messages with optional technical details disclosure.
- UI components must not render raw route names, HTTP status text, backend details, prompt IDs, or raw payloads in normal views.

## Data Quality footer target

Non-admin users:

```text
Data Quality   ● green/yellow/red/gray
```

Hover/focus detail:

```text
Last updated Jun 7, 2026 at 8:00 PM
Some sources need attention
```

Admins:

- same indicator may link or route to Data Health/Admin detail;
- technical details remain behind disclosure.
