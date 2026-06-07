# Addendum Prompt — My Dashboard Navigation Model

You are updating the frontend UI/UX implementation package for `hb-personal-assistant`.

## Objective

Correct the primary navigation model:

- Rename `My Items` to `My Dashboard`.
- Make `My Dashboard` the first item in the primary navigation.
- Nest `Today` under `My Dashboard`.
- Keep `Today` as the primary landing view.
- Preserve legacy path compatibility where practical.

This prompt should be implemented with the chrome-header page-title addendum because page title metadata, active navigation state, and body-title removal are coupled.

## Scope

Likely files:

- `frontend/src/navigation/navigationModel.ts`
- `frontend/src/app/routes.tsx`
- `frontend/src/layouts/AppShell.tsx`
- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/components/layout/PrimaryPageLayout.tsx`
- route/title/nav helper files created during the implementation package
- tests that assert route/nav labels or default landing behavior

## Required work

1. Replace visible `My Items` primary nav/page label with `My Dashboard`.
2. Move `My Dashboard` to the first primary nav position.
3. Remove `Today` as a top-level nav peer.
4. Render `Today` as a nested child under `My Dashboard`.
5. Make `/` land on the Today view under My Dashboard.
6. Prefer route `/my-dashboard/today` for the nested Today view.
7. Add legacy redirects/aliases from `/today` to `/my-dashboard/today`.
8. Add legacy redirect/alias from `/my-items` to either:
   - `/my-dashboard/items` if the old My Items content remains separate; or
   - `/my-dashboard/today` if the old page is merged into the dashboard landing.
9. Preserve the prior My Items content as a dashboard work-queue section or nested subview.
10. Update chrome header title metadata so the active page reads as `My Dashboard` with `Today` as the nested view/breadcrumb/subtitle.
11. Remove duplicate page-body top-level titles.
12. Update tests and copy checks for the new naming.

## Preferred route model

```text
/                         -> /my-dashboard/today
/my-dashboard             -> /my-dashboard/today
/my-dashboard/today       -> Today view
/my-dashboard/items       -> prior My Items work-queue view, if retained separately
/today                    -> /my-dashboard/today legacy redirect
/my-items                 -> /my-dashboard/items or /my-dashboard/today legacy redirect
```

## Acceptance criteria

- `My Dashboard` is the first primary nav item.
- `Today` is visibly nested under `My Dashboard`.
- `Today` remains the default landing view.
- `Today` is no longer a top-level nav item.
- Chrome header reflects the active hierarchy: `My Dashboard` / `Today`.
- Page body does not render a duplicate top-level title.
- Existing Projects navigation remains intact.
- Legacy `/today` and `/my-items` paths do not produce dead routes.
- No stale visible `My Items` label remains except in explicit legacy route/test references.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test

grep -R "My Items" -n frontend/src || true
grep -R "Personal Assistant\|HB Analytics" -n frontend/src || true
```

Manual smoke:

- `/` opens the Today view under My Dashboard.
- First primary nav item is My Dashboard.
- Today is nested below My Dashboard.
- Projects is still available and not nested under My Dashboard.
- `/today` redirects or aliases correctly.
- `/my-items` redirects or aliases correctly.
- Header and body title hierarchy are not duplicative.
