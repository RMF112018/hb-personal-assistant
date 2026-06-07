# Chrome Header Page Title Addendum

## Scope correction

The current UI has duplicative shell/page title treatment on secondary pages. Page titles must render in the chrome header and replace the static app title text currently shown as `Personal Assistant` / previously `HB Analytics`.

## Required target behavior

- The chrome header is the single owner of the current route/page title.
- The static shell title `Personal Assistant` must be replaced by the active page title.
- Page bodies must not render duplicate top-level titles immediately below the chrome header.
- Page bodies may still render section headings, card titles, subheaders, tab labels, and contextual summaries.
- Each route should still preserve one accessible page-level heading. Prefer the chrome header title as the `h1`, or use an equivalent accessible title pattern if the header cannot be an `h1` for layout reasons.
- Secondary/project detail pages must use route-specific titles such as `Projects`, `All Projects`, project name/title, `Meetings`, `Field Operations`, `Cost & Time`, `Settings`, `Data Health`, `Get Started`, and `My Items`.

## Implementation approach

### 1. Add route/page metadata

Create a single source of truth for page title metadata. Acceptable approaches:

- extend the existing route configuration with `handle: { title }` metadata if React Router route objects are already centralized;
- add a `getPageTitle(location, params, data)` helper if dynamic project names need lookup;
- create a small `PageTitleProvider` / `usePageTitle` pattern only if route metadata is insufficient.

Prefer the simplest route-metadata approach that fits current repo truth.

### 2. Update AppShell chrome header

Replace static shell title copy with active route title.

Target behavior:

```tsx
<header className="...">
  <h1>{activePageTitle}</h1>
  {/* right-side controls */}
</header>
```

Do not render `Personal Assistant` as the primary header title on routed app screens. If brand identity is needed, move it to the sidebar brand area or a small app badge, not the page title area.

### 3. Remove duplicate page-body titles

Audit and remove duplicate top-level title blocks from:

- `TodayPage.tsx`
- `ProjectsPage.tsx`
- `ProjectDashboardPage.tsx`
- `MyItemsPage.tsx`
- `SettingsPage.tsx`
- `AdminDataConfidencePage.tsx`
- `GetStartedPage.tsx`
- project subpages/tabs such as meetings, field operations, cost/time, or equivalent current files

Preserve non-duplicative section labels inside cards and dashboard sections.

### 4. Refactor PrimaryPageLayout accordingly

If `PrimaryPageLayout` is created in the implementation package, it should not default to rendering another visible `h1` that duplicates the chrome title. It should support:

- optional subtitle/description;
- optional page actions;
- optional status row;
- optional hidden/sr-only title only when the chrome header cannot provide the accessible title.

Recommended API:

```tsx
<PrimaryPageLayout
  subtitle="Your project work queue and updates."
  actions={<... />}
>
  ...
</PrimaryPageLayout>
```

Avoid requiring `title` as visible body content when the chrome owns title rendering.

## Prompt integration

### Update P01 — App Shell Overflow, Sidebar Footer, and Production Chrome

Add acceptance criteria:

- Chrome header renders the active route/page title instead of static `Personal Assistant` / `HB Analytics`.
- Static app name remains only in sidebar brand or metadata, not as the main page header on routed screens.

### Update P02 — Shared Layout, Card, State, and Copy Primitives

Add acceptance criteria:

- `PrimaryPageLayout` does not create duplicate body `h1` titles when the chrome header already owns the page title.
- Page metadata/title helper exists and is consumed by `AppShell`.

### Update P03/P04/P05/P06/P07

Add acceptance criteria:

- The refactored page removes duplicate top-level body titles.
- Only section/card headings remain inside the page body.
- The chrome header title matches the active route.

### Update P08 — Visual/A11y Hardening

Add validation:

- Confirm each route has one page-level accessible title.
- Confirm no visual double-header appears on Today, Projects, My Items, Settings, Data Health, or project detail pages.

## Validation commands

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

Recommended grep checks:

```bash
grep -R "Personal Assistant\|HB Analytics" -n frontend/src || true
grep -R "<h1\|role=\"heading\"" -n frontend/src/pages frontend/src/layouts frontend/src/components || true
```

Manual validation:

- Open each primary and secondary route.
- Confirm the chrome header title changes per route.
- Confirm the page body does not start with a duplicate title card/header.
- Confirm sidebar brand still identifies the application without competing with the active page title.
- Confirm keyboard/screen-reader title semantics remain coherent.
