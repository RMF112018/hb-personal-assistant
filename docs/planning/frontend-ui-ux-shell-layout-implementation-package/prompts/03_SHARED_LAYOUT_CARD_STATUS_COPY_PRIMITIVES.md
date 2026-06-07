# P02 — Shared Layout, Card, State, and Copy Primitives

## Objective

Create reusable primitives for page layout, dashboard grids, cards, and user-safe copy/status/error handling so the primary page refactors remain consistent.

## Scope

Likely new or refactored files:

- `frontend/src/components/layout/PrimaryPageLayout.tsx`
- `frontend/src/components/layout/DashboardGrid.tsx`
- `frontend/src/components/layout/DashboardCard.tsx`
- `frontend/src/components/common/SectionCard.tsx`
- `frontend/src/components/common/EmptyState.tsx`
- `frontend/src/components/common/ErrorState.tsx`
- `frontend/src/components/common/LoadingState.tsx`
- `frontend/src/components/common/TechnicalDetails.tsx`
- `frontend/src/lib/statusCopy.ts`
- `frontend/src/lib/errorCopy.ts`

## Required implementation

1. Add a primary page layout primitive with consistent title, subtitle, actions, and content region.
2. Add dashboard grid/card primitives using CSS Grid and responsive classes.
3. Support card span variants without breaking DOM reading order.
4. Add shared state components for loading, error, empty, and disconnected states.
5. Add `TechnicalDetails` or equivalent disclosure component for admin/developer details.
6. Add status/error copy helpers that map backend/API terms to user-facing labels.
7. Ensure raw error detail can be logged or disclosed, but not rendered as the primary user message.

## Non-scope

- Do not refactor every page yet.
- Do not create a JS masonry dependency.
- Do not implement new backend routes.

## Acceptance criteria

- Today, Projects, and My Items can reuse the same grid/card primitives.
- ErrorState no longer requires raw backend message display.
- Empty/loading/disconnected states have consistent styling and action slots.
- Technical details are optional and collapsed by default.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

## Risk notes

- Avoid `grid-auto-flow: dense` unless you validate screen-reader/keyboard order.
- Preserve semantic headings in cards; do not replace headings with generic divs.
