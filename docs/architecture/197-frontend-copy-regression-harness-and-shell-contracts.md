# 197. Frontend Copy Regression Harness and Shell/Layout Contracts (P09 Closeout)

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package (P09)

## Decision

A production source copy regression harness (`npm run copycheck`) was added:

- Implementation: `scripts/proofs/frontend_display_copy_check.py` (stdlib Python; follows existing `scripts/proofs/` convention).
- Invocation: `cd frontend && npm run copycheck` (wires `python ../scripts/proofs/frontend_display_copy_check.py`).
- Scan targets (per package data/forbidden_terms_seed.json and 08 plan): `frontend/src/**/*.ts`, `**/*.tsx`, `**/*.css`.
- Skip rules: any path matching `*.test.*`, `*_test.*`, or containing `/test/` or `/tests/` segments (test files legitimately reference the terms in assertion arrays).
- Term list (hardcoded, with comment reference to the planning seed): the minimum set from the P09 query + seed — "local dev role", "not production auth", "Prompt 14B", "Prompt 20", "FPR-004", "raw panels", "JSON.stringify", "FastAPI", "uvicorn", "read model", "read models", "source/sync/evidence", "Chat (disabled)", "Vite", "HMR", "Count is".
- Behavior: on any hit in a non-skipped file, prints "VIOLATION: relpath: term" lines, "copycheck FAILED", exits 1. On clean: "copycheck: no forbidden production terms found...", exits 0.
- Smarts: the checker skips `JSON.stringify(` call sites (legitimate internal serialization in the API client; the forbidden intent was visible "JSON.stringify output" fallbacks in rendered UI).
- Hygiene: legacy demo strings removed from the unused `frontend/src/App.tsx` starter; historical prompt numbers / "FastAPI" / "read models" / "Vite dev proxy" mentions rephrased in `frontend/src/lib/api.ts` header comments (so literals do not appear in prod source while preserving developer context).

The harness is the required "copycheck regression coverage" for P09. It is intentionally simple (substring on the three globs) and fast.

Shell / layout / copy contracts implemented by the package (P01–P09) are summarized here with pointers to the detailed ADRs:

- Viewport-locked shell + independent main content scroll: `AppShell` (`h-[100dvh] overflow-hidden flex` outer, `main id="main" ... overflow-y-auto overflow-x-hidden` for content; sidebar `overflow-hidden`). See 189 and 196.
- Pinned sidebar footer/status: `SidebarFooter` (`mt-auto shrink-0`) containing the role-gated `DataQualityIndicator` (non-admin only) + `SupportNavigation`. See 189, 195 (P07), 196.
- Production chrome: no visible "Local dev role", no "Chat (disabled)". Skip link present and functional. See 189 + AppShell.test.
- Page header: sole `h1` + advisory from `PageHeader` (always rendered by shell). `PrimaryPageLayout` title is a non-heading visual label bar (post-P08) with subtitle/actions/status; `space-y-4` + responsive `flex-col sm:flex-row`. See 196.
- Dashboard primitives and grid rules: `DashboardGrid` ( `grid grid-cols-1` base + `md:`, `lg:`, `xl:` responsive for `cards`/`sections`/`metrics` variants; `gap` scale `sm|md|lg` ). `DashboardCard` and `SectionCard` (`card min-w-0`, tone borders, footer slots, post-P08 hover affordance). Used consistently for Today, Projects, My Items, Settings, ProjectDashboard. Preserve DOM order; no dense auto-flow. See 190, 191, 192, 193, 196.
- Shared state/copy primitives: `EmptyState`/`ErrorState`/`LoadingState` (userMessage + optional TechnicalDetails disclosure), `statusCopy.ts` / `errorCopy.ts`, `getDataQualityCopy`, etc. Technicals behind `<details>` for admins. See 190 + 06_COPY_REMEDIATION_STANDARD in the planning package.
- Copy remediation standard + Data Health: voice is professional, plainspoken, CM-first, advisory. Exact replacements and the full forbidden list (plus allowlist guidance for `docs/**`, `tests/**`, dev-only) are in the package's `06_COPY_REMEDIATION_STANDARD.md`. P07 translated Admin/Data Confidence → Data Health with the 6 section renames (Source Updates, Background Tasks, Safety Checks, Answer Quality, Access & Permissions, Data Coverage); non-admin `Data Quality` compact footer indicator (green/yellow/red/gray dot + label + hover/focus last-updated + summary via `useDataQualitySummary` + `statusCopy`; admins reach `/admin` Data Health via support nav with shield). See 195 (P07) and 06_.
- Responsive / a11y: all grids 1-col base + breakpoints; header actions wrap; sidebar overlay on narrow + `aria-label`; focus-visible on nav/items + global rules + skip link; headings sequential (h1 shell + h3 cards/sections); landmarks coherent (`aside[aria-label="Primary navigation"]`, labeled navs, main, footer). See 196 (P08) + 189.
- No P0/P1 gaps remain (all addressed across P01–P09; P09 adds the regression guard + docs/evidence).

## Rationale

P09 completes the package by adding the automated guard against regression of the copy problems identified in the original audit and copy package, plus the required documentation and evidence bundle so operators have a durable record of the implemented contracts and can re-verify quickly (`npm run copycheck` is the canary).

The source scan + test-file skip + limited smarts + comment hygiene is the smallest change that makes the AC ("`npm run copycheck` passes") true while matching the spirit of the 06 standard (prevent the terms from appearing where users or rendered output would see them).

Pointers to prior ADRs + the planning package docs keep this record concise yet traceable.

## Guardrails

- Harness and docs only; no runtime behavior, data, auth, or backend changes.
- No new npm/python runtime dependencies (stdlib + existing project tooling).
- Scans only the declared production globs; tests/docs/dev-only remain the documented allowlist locations.
- All validation commands from the package 08/09 plans and the P09 query were executed (see evidence bundle).
- Safety: no live reads, writes, tokens, or external systems touched (source + docs + evidence only).
- Post-P09, `npm run copycheck` (plus the rest of the frontend suite) is part of the required closeout for any future frontend display-copy work.

Evidence bundle (including the filled CLOSEOUT per 09_CLOSEOUT_REPORT_TEMPLATE, full command outputs, copycheck log, smoke notes, and safety confirmation) lives under `docs/evidence/frontend-ui-ux-shell-layout-implementation/`.
