# P00 — 01 Baseline Preflight

Package: `graph-procore-dev-ui-connections-implementation-package`
Prompt: P00 — Precheck and Branch Discipline
Captured: 2026-06-07

## Branch discipline

| Field | Value |
|---|---|
| Current branch | `codex/frontend-shell-layout-p00` |
| Upstream | `origin/codex/frontend-shell-layout-p00` (ahead 3) |
| HEAD | `876dd6e606da32f12fd6698461ab61530d09414a` |
| Project version (`pyproject.toml`) | `1.3.0` |
| Frontend `package.json` version | `0.0.0` (private workspace) |
| Remote | `https://github.com/RMF112018/hb-personal-assistant.git` |

Branch discipline is satisfied: work is already on the dedicated `codex/frontend-shell-layout-p00`
branch (not `main`).

## ⚠ Working tree is NOT clean (overlap risk recorded)

The tree carries substantial **pre-existing uncommitted work** from a parallel
`frontend-ui-ux-shell-layout-implementation-package` effort. This is *not* produced by P00, but it
overlaps the Connections UI this package will later modify, so it is recorded here for branch
discipline and to avoid accidental staging.

Modified Connections/Settings components (overlap with later prompts P02/P03/P06/P07):

```
 M frontend/src/components/settings/AccountConnectionsPanel.tsx
 M frontend/src/components/settings/AdminFirstSyncApprovalPanel.tsx
 M frontend/src/components/settings/ConnectionPreviewCard.tsx
 M frontend/src/components/settings/GraphConnectionCard.tsx
 M frontend/src/components/settings/ProcoreConnectionCard.tsx
 M frontend/src/components/settings/ProjectConnectionsPanel.tsx
```

Other notable uncommitted items:
- Modified: `.gitignore`, `frontend/package-lock.json`, several `frontend/src/components/ui/*` and
  `daily-brief`/`projects` components, and many `docs/evidence/**` JSON/MD files (cross-phase).
- Untracked: `docs/architecture/189-…194-frontend-*.md`, new `frontend/src/components/common/*`,
  `frontend/src/components/layout/DashboardGrid.tsx`, `frontend/src/components/today/`,
  `frontend/src/components/settings/{DailyBriefSettingsPanel,DataHealthPanel,KeywordManagementPanel}.tsx`,
  and a **root** `package-lock.json` (untracked, empty `packages: {}` — stray, not introduced by P00).

**P00 staging rule:** commit only the new
`docs/evidence/graph-procore-dev-ui-connections-p00-precheck/**` files (and, if added, a new
`docs/architecture/` note for this run). Do **not** stage any of the pre-existing modified/untracked
files above.

## Recent commits (top 10 of 30)

```
876dd6e6 feat(frontend): Polish — Remove redundant Open Settings row under My Dashboard + add Today navigation
d30fbe5c feat(frontend): Refinement — My Dashboard = My Items Content; Remove Today and "My Items" from Sidebar
d577f80a feat(frontend): Addendum — Chrome Header Owns Page Titles + Coupled My Dashboard Navigation
9269d996 HB Construction Intelligence — Launcher MCP Lifecycle: stdio External-Client-Managed v1.3.1
8287d14c feat(frontend): P09 follow-up — Replace user-facing HB Analytics with Personal Assistant
5577466f feat(frontend): P09 — Copy Regression Harness, Documentation, and Closeout Evidence
c8959194 feat(frontend): P08 — Visual Hierarchy, Responsiveness, and Accessibility Hardening
7ce27ecf HB Construction Intelligence — Launcher Hardening: Preflight, Port Determinism & Stale Cleanup v1.3.0
5d75bf1c feat(frontend): P07 — Sidebar Data Quality and Admin/Data Health translation
b901d7b6 HB Construction Intelligence — Launcher Frontend Display Alias v1.2.1
```

## Frontend stack (`frontend/package.json`)

- React `^19.2.6` + React-DOM, React Router `^6.26.0`, TanStack React Query `^5.45.0`, Recharts.
- Build/dev via **Vite `^8.0.12`** (`npm run dev` → `vite`). Tests via Vitest. TypeScript `~6.0.2`.
- No axios; native `fetch` (see `frontend/src/lib/api.ts`). UI helpers: `clsx`, `tailwind-merge`,
  `class-variance-authority`, `lucide-react`, Tailwind `^3.4.3`.

## Installed runtime preflight (already verified)

- Backend optional deps present in `.venv`: `fastapi 0.136.3`, `uvicorn 0.49.0`.
- Frontend `node_modules` present (311 entries); `frontend/dist/` present (note: dist may be stale vs.
  the uncommitted source above — only relevant to production-mode static serve, not dev/vite).
