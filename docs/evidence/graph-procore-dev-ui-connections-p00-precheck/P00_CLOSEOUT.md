# P00 Closeout — Precheck and Branch Discipline

## Summary

- Branch: `codex/frontend-shell-layout-p00`
- Starting HEAD: `876dd6e606da32f12fd6698461ab61530d09414a`
- Ending HEAD: (this evidence commit)
- Package: `graph-procore-dev-ui-connections-implementation-package`, prompt **P00**
- App version: `1.3.0`
- Status: **Complete** (precheck/diagnostic — no source changes)

## Objective result

P00 is a precheck; it does **not** make the Dev UI usable, it **captures and classifies the current
failure path** so P01+ fix a real problem. Result: with the backend healthy and Dev in
`mock_data` mode, the per-card Graph/Procore connection contracts already return 200 and the connect
flows render, but three concrete failure paths exist (F1–F3 in `08-failure-classification.md`):
admin-only call fired for all roles (403), Settings panels showing error states on valid 200 data, and
the aggregate source-status endpoints missing (404).

## Changed files

| File | Purpose | Prompt |
|---|---|---|
| `docs/evidence/graph-procore-dev-ui-connections-p00-precheck/01-baseline-preflight.md` | Branch/version/tree state | P00 |
| `…/02-launcher-and-environment.{md,json}` | Launcher lifecycle, ports, roots, reachability matrix | P00 |
| `…/03-source-inventory-and-search.md` | File counts + search sweeps + api-client base | P00 |
| `…/04-safe-cli-status.json` | graph/procore/scheduler safe status JSON | P00 |
| `…/05-gated-live-reads.md` | Gate-state inventory; live reads skipped (gates OFF) | P00 |
| `…/06-browser-capture/` | screenshots, console.log, network.json, page-text.md, response-bodies.md | P00 |
| `…/07-backend-logs.md` | Correlated uvicorn 403/404 + clean-of-5xx | P00 |
| `…/08-failure-classification.md` | **Core artifact** — classified F1–F3 + ruled-out + residual risk | P00 |
| `…/P00_CLOSEOUT.md` | This closeout | P00 |

No `src/` or `frontend/src/` files were modified by P00.

## API contracts (observed during precheck — none added by P00)

| Endpoint | Implemented/adapted | Metadata-only | Tests |
|---|---|---|---|
| `/api/environment` | **No (404)** — GPC-P0-001 target | n/a | — |
| `/api/sources/status` | **No (404)** — GPC-P0-001 target | n/a | — |
| `/api/sources/graph/status` | Not present (per-card `/api/settings/accounts` returns Graph status, 200) | yes | — |
| `/api/sources/procore/status` | Not present (per-card `/api/settings/accounts` returns Procore status, 200) | yes | — |
| `/api/sources/refresh/dry-run` | Not present | n/a | — |
| `/api/sources/refresh/local` | Not present | n/a | — |
| `/api/sources/refresh/live` | Not present | n/a | — |

## Frontend results (observed)

- Graph card states: renders **"never connected"** (Microsoft 365) from backend contract — OK.
- Procore card states: renders **"env present"** from backend contract — OK.
- Local/mock refresh: not a distinct UI action yet (GPC-P0-005).
- Dry-run: not a distinct UI action yet.
- Live refresh: not surfaced; gates OFF.
- Data Quality footer: renders, but the Settings DataHealth panel takes its **error branch** on valid
  200 data (F2).
- Admin diagnostics: `/admin` renders; Settings AdminFirstSyncApprovalPanel fires admin-only call for
  all roles → 403 (F1).

## Validation

- `launcher dev --open` → `status: ok`, backend/frontend/scheduler `running`, `frontend_reachable: true`.
- `GET :8000/health` → 200 (schema 40, guardrails intact).
- Endpoint reachability matrix (proxy vs direct) — see `02`; per-card endpoints 200, aggregate 404.
- Headless capture (Playwright, admin) — 0 responses ≥400, 0 request failures, 0 page errors; only
  React Router v7 future-flag warnings.
- Role probe: `/api/settings/admin-sync` → 403 viewer/operator/default, 200 admin.
- Safe CLI status checks captured (`04-safe-cli-status.json`).

## Manual Dev validation

- URL: `http://127.0.0.1:5173` (`/settings`, `/get-started`, `/admin`).
- Browser console: only React Router v7 future-flag warnings (benign); no errors/exceptions.
- Network failures: none at the network layer; the 403 on `/api/settings/admin-sync` is a deliberate
  fail-closed guard hit by an ungated UI call.
- Backend logs: clean of 5xx/tracebacks; repeated `403 admin-sync`, `404 /api/environment`,
  `404 /api/sources/status` (see `07`).
- Graph card result: "never connected" (OK).
- Procore card result: "env present" (OK; underlying access token expired — re-auth needed for live).
- Local refresh result: n/a (not surfaced).
- Live refresh fail-closed result: confirmed OFF (gates unset; `live_reads_enabled: false`).

## Safety confirmation

- ✅ No Graph writeback endpoints added (no endpoints added at all).
- ✅ No Procore writeback endpoints added.
- ✅ No tokens/secrets/cache paths exposed (status surfaces return names/flags only; verified in bodies).
- ✅ No raw email/calendar/Procore payload exposed.
- ✅ Status page load performs no live external reads (all gates OFF; no live calls made).
- ✅ Live refresh remains gated / default OFF.

## Residual risks / next step

- **R1:** Working tree carries uncommitted WIP overlapping Connections/Settings (parallel
  `frontend-ui-ux-shell-layout` effort). Reconcile/define the baseline before P01 source edits; the F2
  panel errors are observed in this WIP and must be confirmed against the chosen baseline.
- **R2:** Backend is `optional=True` in the launcher — add a UI "backend unreachable" state (P06/P07)
  so the optional-backend-down path degrades gracefully instead of connection-refused everywhere.
- **R3:** Stale auth — Procore token expired; Graph mail token is `app_only` (`unexpected`). P02/P03
  must surface clear re-auth/refresh next-actions.
- **R4:** The **uncommitted** working-tree `.gitignore` adds `/docs/evidence`, `/docs/planning`,
  `/.claude`, `/.code-graph`, which would stop tracking all evidence/planning bundles — contradicting
  governance (`CLAUDE.md`: "docs/evidence/** stays in-repo and is referenced"). This P00 bundle was
  committed via `git add -f` to bypass that WIP ignore without modifying the parallel WIP. The
  `.gitignore` change should be reverted/reconciled before P01.
- **Next:** P01 — add/adapt `/api/environment` + `/api/sources/status` (GPC-P0-001) and surface Dev/
  local-mock mode (GPC-P1-001).
