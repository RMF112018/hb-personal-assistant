# UI Kit, Theme, and Components

## Design Flexibility

Do not overfit a rigid design system. Build a modular UI kit from off-the-shelf free packages wherever practical.

Recommended stack:

- React + TypeScript + Vite.
- Tailwind CSS.
- shadcn/ui or equivalent Radix-style component kit.
- Radix UI primitives where direct lower-level control helps.
- TanStack Query for server-state fetching/caching.
- TanStack Table for data grids.
- Recharts for charts.
- Lucide React for icons.

## Theme

Primary theme: dark.

Support:

- dark;
- light;
- system.

System mode should respect OS preference. Store user preference locally.

## App Shell Components

The app shell must support the simplified navigation hierarchy:

- primary nav: Today, Projects, My Items;
- support nav: Admin / Data Confidence, Settings;
- no active Chat nav item.

Required shell components:

- `AppShell`
- `MainNavigation`
- `SupportNavigation`
- `ProjectSelector`
- `ProjectSubNav`
- `PageHeader`
- `DashboardSection`
- `FreshnessBadge`
- `ConfidenceBadge`
- `AttentionItemCard`
- `MetricCard`
- `MetricChartCard`
- `DrilldownTable`
- `EmptyState`
- `StaleDataBanner`
- `ErrorRecoveryPanel`

## Dashboard Component Families

### Today components

- Important Today panel.
- Daily Brief executive renderer.
- Today's Meetings panel.
- What Changed feed.
- Action Items panel.
- Portfolio Signals panel.

### Projects components

- Portfolio dashboard.
- All Projects aggregated dashboard.
- Project Overview dashboard.
- Project Meetings tab.
- Project Field Operations tab.
- Project Cost & Time tab.
- Project selector with All Projects option.

### My Items components

- My Action Items panel.
- My Meetings panel.
- My Correspondence panel.
- My Files panel.
- My Followed Projects panel.

### Admin components

- Source / Sync Health cards.
- Workflow / Job Health cards.
- Evidence / Guardrail cards.
- Retrieval / AI Quality cards.
- Permissions / Governance cards.
- Data Completeness cards.

### Setup components

- First-run onboarding wizard.
- Graph device login status.
- Procore OAuth status.
- SharePoint URL setup.
- Procore project URL setup.
- OneDrive scope selector.
- Outlook/Calendar scope selector.
- Project keyword editor.
- Daily Brief external platform setup wizard.

## UX Tone

Calm, executive, operations-focused. Avoid playful dashboards or engineering-heavy telemetry labels in primary screens.

Avoid exposing dry-run/apply/execute in construction-user screens. Use business language such as Refresh, Review, Prepare, Open, Mark Reviewed, Update Connection, Schedule First Sync, and View Source.

Admin / Data Confidence may expose more technical detail, but should still use plain-language explanations first.
