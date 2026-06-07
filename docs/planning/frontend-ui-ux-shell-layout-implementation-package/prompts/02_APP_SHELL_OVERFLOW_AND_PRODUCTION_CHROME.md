# P01 — App Shell Overflow, Sidebar Footer, and Production Chrome

## Objective

Fix the app shell so the sidebar is viewport-height, the sidebar footer/status area remains pinned, and page content scrolls independently. Remove normal-user development chrome and hidden/future Chat affordances.

## Scope

Likely files:

- `frontend/src/index.css`
- `frontend/src/layouts/AppShell.tsx`
- `frontend/src/layouts/SupportNavigation.tsx`
- `frontend/src/navigation/navigationModel.ts`
- new/extracted `frontend/src/components/layout/SidebarFooter.tsx`
- new/extracted `frontend/src/components/layout/DataQualityIndicator.tsx`

## Required implementation

1. Set root height rules so `html`, `body`, and `#root` support a bounded viewport app.
2. Refactor `AppShell` to use `height: 100dvh`, `overflow: hidden`, and `min-h-0` where needed.
3. Ensure desktop sidebar has fixed viewport height and does not expand with page content.
4. Ensure the main panel is the only primary scroll container.
5. Extract or define a pinned sidebar footer/status area.
6. Remove the visible local dev role selector from normal chrome. Keep it only behind an explicit dev-only flag/panel if needed.
7. Remove disabled Chat from visible navigation.
8. Preserve skip link, route navigation, and role-aware Admin visibility.

## Non-scope

- Do not implement Chat.
- Do not change backend auth behavior.
- Do not start sync or external reads.

## Acceptance criteria

- Main content scroll no longer pushes/displaces sidebar footer.
- Sidebar footer remains visible at top/middle/bottom scroll states.
- No normal UI text: `Local dev role`, `not production auth`, `Chat (disabled)`.
- Navigation active states still work.
- Mobile/tablet behavior remains usable.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

Manual browser smoke:

- Today: scroll top/middle/bottom; sidebar footer visible throughout.
- Projects: same.
- My Items: same.
- Narrow width: navigation remains accessible; no horizontal overflow.

## Risk notes

- Missing `min-h-0` on a flex child can silently preserve the overflow bug.
- Avoid putting footer/status controls inside the page scroll region.
