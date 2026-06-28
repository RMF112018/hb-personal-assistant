# 08 — Frontend Surfacing Evidence

The Computed CPM analysis is surfaced read-only in the React frontend.

## Route and navigation

- **Route:** `schedules/cpm` → `<ScheduleCpmPage />`, page title "Computed CPM"
  (`frontend/src/app/routes.tsx:245-247`).
- **Nav entry:** `{ to: '/schedules/cpm', label: 'Computed CPM', icon: Workflow }`
  (`frontend/src/components/schedule/SchedulePageChrome.tsx:24`).
- **Selection semantics:** same `?project=&version=` selection as the other schedule pages.

## Page composition (`frontend/src/pages/ScheduleCpmPage.tsx`)

- **Run-chain card** — the six CPM stages with their statuses.
- **DCMA evidence card** — measurability, basis, dependency runs, caveats.
- **Longest path panel** — the extracted path (`..._p01`, 45 activities).
- **Computed activity table** — app-owned whitelisted fields (no source critical/driving/float
  columns).
- **Source-export separation** — computed CPM is presented as application-computed; source-export
  evidence is not mixed in.
- **Empty / error states** — when no computed CPM exists the page shows an explicit
  "No computed CPM yet" empty state (covered by `ScheduleCpmPage.test.tsx`'s
  "renders empty state when no computed CPM is available").

## Client layer

`frontend/src/lib/api.ts` exposes 4 typed CPM client fns + types matching the 4 endpoints. (The
file also carries unrelated obsidian_mcp WIP additions — see doc 01 — but the CPM client code is
the merged Phase 8 code and is eslint/typecheck clean; see `artifacts/frontend-test-output.txt`.)

## UI observation: before vs after explicit-DB backend

This mirrors the `create_app(db_path=...)` finding in doc 07 from the UI's perspective:

- **Before** (backend launched via factory `create_app()` without `db_path`): the page showed
  **"No computed CPM yet"** even though the evidence DB held the full chain — because
  `app.state.db_path` was `None`.
- **After** (backend restarted via `artifacts/run-evidence-api.py` →
  `create_app(db_path="/tmp/hb-schedule-cpm-evaluation.sqlite")`): the page surfaced the
  **computed CPM** (run-chain, DCMA evidence, longest path, activity table).

This was a runtime DB-binding condition, **not** a CPM computation or frontend defect.

## Validation

`artifacts/frontend-test-output.txt`: `npm run typecheck` clean; `ScheduleCpmPage.test.tsx`
**7/7 passed**; eslint on the 5 CPM-touched files exit 0.

See also `ui-cpm-review-notes.md` (per-version UI review) and `manual-ui-import-log.md` (the
manual UI import that produced the evaluated schedule).
