# 190 - Frontend Layout Primitives and Safe Copy

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package

## Decision

The analytics frontend now has shared primitives for primary page layout, dashboard grids, dashboard cards, section cards, state rendering, optional technical disclosure, and backend-status copy mapping.

These primitives are additive. Existing page imports under `components/ui` continue to work while later page refactors migrate Today, Projects, and My Items toward the shared layout/card components.

## Rationale

The dashboard pages need consistent spacing, card structure, empty/loading/error behavior, and copy conventions before the larger page-specific masonry refactors. Centralizing this layer avoids repeating ad hoc grid classes and raw backend message handling across primary pages.

Error presentation is split into user-facing copy and optional technical detail. Primary UI copy stays safe and business-readable. Raw details may be retained for operators only inside a collapsed disclosure.

## Constraints

- No JavaScript masonry dependency is introduced.
- Dashboard grids preserve DOM reading order and do not use dense auto-placement.
- Cards keep semantic headings.
- No backend routes, auth behavior, sync behavior, source-system reads, SQLite writes, auth-cache access, or Obsidian access are changed.
