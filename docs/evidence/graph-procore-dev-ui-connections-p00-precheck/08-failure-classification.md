# P00 — 08 Failure Classification (core acceptance artifact)

Captured: 2026-06-07 · Environment: **dev** (`source_refresh_mode: mock_data`, live gates OFF) ·
Backend: healthy uvicorn on `:8000` · Frontend: vite `:5173` (serving **uncommitted working-tree** source)

## Method

Drove `http://127.0.0.1:5173` headless (Playwright/Chromium) across `/`, `/get-started`, `/settings`,
`/admin`, `/today`, `/my-dashboard` with UI role `admin`; captured console, network, page errors, and
full-page screenshots; cross-checked every Connections/Settings `/api` route by `curl` (proxy `:5173`
and direct `:8000`) and by reading the backend launcher log. Evidence: files `02`–`07` and
`06-browser-capture/`.

## What is NOT failing (ruled out with evidence)

| Candidate root cause | Verdict | Evidence |
|---|---|---|
| CORS / base-url / proxy | **Not the cause** | Proxy `:5173` and direct `:8000` status codes match for every route (02) |
| Missing per-card connection endpoint | **Not the cause** | `accounts`, `connections/accounts`, `connections/projects`, `onboarding/readiness`, etc. all 200 (02) |
| Backend down / connection refused | **Not the current state** | Backend `running`, `/health` 200, schema 40 (02) |
| Live external read / writeback leak | **Not occurring** | All gates OFF, fail-closed honored; no live calls (05) |
| Backend 5xx / tracebacks | **None** | Backend log clean of exceptions (07) |
| Auth exists only in CLI (no UI flow) | **Not the cause** | Device-code Graph + OAuth Procore connect flows render in UI (06 screenshots/text) |

## Classified current failure paths

### F1 — UI calls an admin-gated endpoint without client-side role gating → repeated `403`
- **Severity:** P0 · **Category:** *frontend calls endpoint it isn't authorized for (missing UI role gate)*
- **Observed:** `GET /api/settings/admin-sync` returns **403** for `viewer`/`operator`/default, **200**
  only for `admin`. The backend log shows this 403 repeating across the default-role browser session.
- **Root cause:** `frontend/src/components/settings/AdminFirstSyncApprovalPanel.tsx:22` calls
  `getAdminPendingApprovals()` unconditionally on mount with no role check. The backend guard is correct
  and fail-closed; the **frontend** fires an admin-only call for every user.
- **Maps to:** GPC-P1-003 (internal errors leak to UI) / GPC-P0-004 (connect/admin surfaces behave wrong
  for role). Fix later in P06/P07: gate the call/panel on `admin` role.

### F2 — Settings panels render error states despite valid `200` responses → contract-handling mismatch
- **Severity:** P0 · **Category:** *response-shape / frontend contract handling mismatch*
- **Observed (running WIP UI):**
  - **Preferences**: red "Preferences could not be saved. The rest of the page remains advisory."
    (on load; no PATCH issued) — `GET /api/settings/preferences` returns valid 200.
  - **Daily Brief**: "Daily Brief settings could not be loaded…" — `GET /api/settings/daily-brief` 200.
  - **Data Health**: "Data Health could not be loaded… details are not available for this role."
    (role = admin; `data-quality/detail` returns 200 for admin) — 200.
  - **Project Keywords**: "Project keywords could not be loaded…" — `GET /api/settings/keywords` 200.
- **Network proof:** Playwright admin session — 501 responses, **0** ≥400, **0** request failures,
  **0** page errors. The error states render **without any failed HTTP request**.
- **Root cause:** client-side handling/contract expectation mismatch between the frontend panels and the
  backend response shapes (the panels take their error branch on well-formed 200 data).
- **Attribution caveat:** these panels are the **uncommitted working-tree** components
  (`DataHealthPanel.tsx`, `KeywordManagementPanel.tsx`, `DailyBriefSettingsPanel.tsx` are untracked;
  `AccountConnectionsPanel.tsx` etc. are modified) from the parallel
  `frontend-ui-ux-shell-layout` effort. The committed baseline may differ. See F4.
- **Maps to:** GPC-P0-006 (frontend/backend endpoint/response-contract mismatch → normalize typed API
  client + response contracts), addressed in P05/P06.

### F3 — Aggregate source-status surface absent → `404`
- **Severity:** P0 · **Category:** *missing backend endpoint (not yet wired in frontend)*
- **Observed:** `GET /api/environment` → 404; `GET /api/sources/status` → 404 (07). No frontend code
  references these yet (03).
- **Root cause:** the package's intended aggregate "running in Dev / local-mock mode + per-source
  freshness" contract does not exist. Per-card status exists; the **aggregate** does not.
- **Maps to:** GPC-P0-001 (add `/api/environment` + `/api/sources/status`) and GPC-P1-001 (surface
  Dev/local-mock mode), addressed in P01/P07.

## Residual risk / context (not failures of this precheck)

- **R1 — Mid-flight working tree.** The repo carries substantial uncommitted WIP that overlaps the very
  Connections/Settings surface this package targets (see `01-baseline-preflight.md`). The running UI is
  that WIP, not the committed baseline — later prompts must reconcile/define the baseline before editing.
- **R2 — Backend is `optional=True` in the launcher.** If uvicorn ever fails to start, the UI gets
  connection-refused on all `/api` calls (a latent "missing endpoint/connection refused" failure path).
  Not the current state (deps installed, backend healthy).
- **R3 — Stale auth.** Procore access token is **expired** (~7h); Graph mail token is `app_only`
  (`classification: unexpected`). Re-auth/refresh next-actions are needed before any live read (05).

## Acceptance check

✅ No source edits (only new `docs/evidence/**`). ✅ Current UI failure path captured (screenshots,
console, network, response bodies, backend logs) and **classified** into F1–F3 with ruled-out
alternatives and residual risks.
