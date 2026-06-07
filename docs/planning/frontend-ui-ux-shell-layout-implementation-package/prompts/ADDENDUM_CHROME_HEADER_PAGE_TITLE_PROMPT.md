# Addendum Prompt — Chrome Header Owns Page Titles

You are updating the frontend UI/UX implementation package for `hb-personal-assistant`.

## Objective

Correct the app shell title hierarchy. The chrome header must render the active page/route title and replace static `Personal Assistant` / `HB Analytics` text. Page bodies must not render duplicate top-level titles.

## Scope

Likely files:

- `frontend/src/layouts/AppShell.tsx`
- `frontend/src/app/routes.tsx`
- `frontend/src/pages/*.tsx`
- `frontend/src/components/layout/PrimaryPageLayout.tsx`
- any existing page-header/title helper component

## Required work

1. Add or use centralized route/page title metadata.
2. Make `AppShell` resolve and render the active page title in the chrome header.
3. Remove duplicate body-level page titles from primary and secondary pages.
4. Keep section/card titles inside page content.
5. Preserve one accessible page-level heading per route.
6. Keep brand identity in the sidebar/brand area only, not as the primary chrome title.

## Acceptance criteria

- Chrome header title changes per route.
- `Personal Assistant` / `HB Analytics` no longer appears as the main routed-page header title.
- No visual double-header appears on primary or secondary pages.
- Page bodies start with meaningful dashboard/content, not duplicate page title chrome.
- Accessibility semantics remain coherent with one page-level heading per route.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test

grep -R "Personal Assistant\|HB Analytics" -n frontend/src || true
grep -R "<h1\|role="heading"" -n frontend/src/pages frontend/src/layouts frontend/src/components || true
```

Manual smoke all primary and secondary routes.


## Coupled navigation update

Also apply `ADDENDUM_MY_DASHBOARD_NAVIGATION_PROMPT.md` in the same implementation pass or immediately after this prompt. The active title system must support the new `My Dashboard` parent and nested `Today` view.
