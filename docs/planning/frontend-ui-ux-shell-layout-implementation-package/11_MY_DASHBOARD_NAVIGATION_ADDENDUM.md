# My Dashboard Navigation Addendum

## Scope correction

The primary navigation hierarchy needs to be corrected before the shell/layout work is finalized:

- `My Items` must be retitled `My Dashboard`.
- `My Dashboard` must be the first item in the primary navigation.
- `Today` must be nested under `My Dashboard`.
- The `Today` view remains the primary landing page.
- The shell chrome header must reflect the new hierarchy without introducing duplicate page-body titles.

## Required target behavior

### Primary navigation order

```text
My Dashboard
  Today
  My Work Queue / Items assigned to me, if the prior My Items content remains separate
Projects
Settings / Data Health / support items as already scoped
```

`My Dashboard` should be the first visible primary nav item.

### Landing behavior

Preferred route model:

```text
/                         -> redirect to /my-dashboard/today
/my-dashboard             -> redirect to /my-dashboard/today
/my-dashboard/today       -> Today view
/my-dashboard/items       -> prior My Items work-queue content if it remains as a separate subview
/today                    -> legacy redirect to /my-dashboard/today
/my-items                 -> legacy redirect to /my-dashboard/items or /my-dashboard/today, depending on where the prior content is placed
```

If the repo’s current route structure makes the preferred route model too disruptive, the minimum acceptable implementation is:

- keep `/today` as the resolved landing route for compatibility;
- render `Today` as a child item under the first primary nav parent `My Dashboard`;
- ensure `My Dashboard` is active when `/today` is active;
- preserve redirects or aliases for old paths.

The preferred approach is still to introduce `/my-dashboard/today` and redirect legacy paths.

## Chrome header title behavior

Because page titles are now owned by the chrome header:

- for `/my-dashboard/today`, the chrome header should orient the user to `My Dashboard` with `Today` as the active nested view;
- acceptable display patterns:
  - title: `My Dashboard`, secondary label/breadcrumb: `Today`; or
  - title: `My Dashboard / Today` if the current header only supports one text slot.
- do not render a duplicate visible `Today` or `My Dashboard` title at the top of the page body.

Recommended header data shape:

```ts
type PageTitleMeta = {
  title: string;
  eyebrow?: string;
  subtitle?: string;
  navParent?: string;
  navChild?: string;
};
```

Example:

```ts
{
  title: "My Dashboard",
  eyebrow: "Today",
  navParent: "my-dashboard",
  navChild: "today"
}
```

## Implementation approach

### 1. Update navigation model

Likely file:

```text
frontend/src/navigation/navigationModel.ts
```

Required changes:

- replace visible `My Items` label with `My Dashboard`;
- place `My Dashboard` first in primary nav;
- represent `Today` as a nested child/subitem, if the model supports nested nav;
- if the current model is flat, extend it carefully to support optional `children` or create a dedicated dashboard child-nav/subnav component;
- ensure active state treats `/my-dashboard`, `/my-dashboard/today`, and legacy `/today` as part of `My Dashboard`.

### 2. Update route configuration

Likely file:

```text
frontend/src/app/routes.tsx
```

Required changes:

- make root landing resolve to the Today view under My Dashboard;
- add redirects from legacy `/today` and `/my-items` routes;
- retain existing page components where possible to avoid data-contract churn;
- rename route metadata so titles and breadcrumbs are correct.

### 3. Rename page/component copy

Likely files:

```text
frontend/src/pages/MyItemsPage.tsx
frontend/src/pages/TodayPage.tsx
frontend/src/layouts/AppShell.tsx
frontend/src/components/layout/PrimaryPageLayout.tsx
```

Required changes:

- visible label `My Items` becomes `My Dashboard` where it refers to the primary nav/page concept;
- prior personal work-queue sections may be labeled `My Work Queue`, `My Action Items`, or another business-readable section title inside My Dashboard;
- do not create a second top-level page title inside the page body;
- update empty/error/copy helpers if they reference `My Items`.

### 4. Preserve backward compatibility

Do not break existing bookmarks or tests unnecessarily. Add redirects/aliases for:

```text
/today
/my-items
```

Where possible, test that both old paths resolve to the new route structure.

## Prompt integration

### Update P01 — App shell overflow, sidebar footer, and production chrome

Add acceptance criteria:

- Primary nav first item is `My Dashboard`.
- `Today` is not a separate top-level primary nav item.
- `Today` is rendered as nested under `My Dashboard`.
- Chrome header reflects `My Dashboard` / `Today` hierarchy.

### Update P02 — Shared layout and route/page metadata

Add acceptance criteria:

- route metadata supports parent/child page title hierarchy;
- active-nav helpers can identify parent and child states;
- `PrimaryPageLayout` supports nested page context without rendering duplicate page titles.

### Update P03 — Today

Add acceptance criteria:

- Today route is nested under My Dashboard;
- Today remains the default landing page;
- Today body does not render a duplicate top-level title.

### Update P05 — My Items / My Dashboard

Rename this prompt to:

```text
P05 — My Dashboard Work-Queue Grid
```

Add acceptance criteria:

- `My Items` visible nav/page label is replaced by `My Dashboard`;
- prior My Items content is preserved as a work-queue section or nested route;
- first nav item routes users to Today under My Dashboard.

### Update P08/P09

Add validation:

- confirm nav order;
- confirm nested active state;
- confirm legacy path redirects;
- confirm no duplicate chrome/page-body titles;
- confirm no stale `My Items` label remains except in intentionally retained migration/legacy route tests.

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
grep -R "My Items" -n frontend/src || true
grep -R "Today" -n frontend/src/navigation frontend/src/app frontend/src/layouts frontend/src/pages || true
grep -R "Personal Assistant\|HB Analytics" -n frontend/src || true
```

Manual validation:

- Open `/` and confirm it lands on the Today view under My Dashboard.
- Confirm first primary nav item is `My Dashboard`.
- Confirm `Today` appears nested under `My Dashboard`, not as a top-level peer.
- Confirm the chrome header communicates `My Dashboard` / `Today`.
- Confirm the page body does not show a duplicate `Today` or `My Dashboard` title.
- Open legacy `/today` and confirm redirect/alias behavior.
- Open legacy `/my-items` and confirm redirect/alias behavior.
- Confirm Projects remains the next major nav item after My Dashboard.
