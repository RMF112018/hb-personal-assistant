# 204 — Frontend Source-Status API Client and State Models

Status: Active · Package: `graph-procore-dev-ui-connections-implementation-package` (P05) · App version 1.3.0

## Context

P01–P04 added the backend `/api/environment`, `/api/sources/*` (status + Graph/Procore safe auth +
refresh) and `/api/scheduler/daily-source-refresh/status` contracts. P05 makes them consumable from the
frontend with typed client methods + normalized TypeScript state models, errors normalized to user-safe
copy, and no raw JSON in the UI. This is the **lib-layer foundation** the Connections/Source-Status UI
cards bind to in P06/P07 (no component changes here).

## Proxy / base URL (confirmed, unchanged)

`frontend/vite.config.ts` proxies `/api` → `http://127.0.0.1:8000` during `npm run dev`;
`frontend/src/lib/api.ts` uses `API_BASE = import.meta.env.VITE_API_BASE || ''` (relative paths). No
change required.

## Client methods + state models (added to `frontend/src/lib/api.ts`)

New typed methods (each `fetchJson<T>` with `X-HB-UI-Role` header; POST bodies JSON-encoded):

| Method | Endpoint | Model |
|---|---|---|
| `getEnvironment()` | `GET /api/environment` | `EnvironmentStatus` |
| `getSourcesStatus()` | `GET /api/sources/status` | `SourcesStatus` |
| `getGraphSourceStatus()` | `GET /api/sources/graph/status` | `GraphSourceStatus` |
| `startGraphSourceAuth()` | `POST /api/sources/graph/auth/start` | `GraphAuthStartResult` (reused) |
| `getGraphSourceAuthStatus(flowId)` | `GET /api/sources/graph/auth/status?flow_id=` | `AuthFlowStatus` (reused) |
| `refreshGraphSourceAuth()` | `POST /api/sources/graph/auth/refresh` | — |
| `getProcoreSourceStatus()` | `GET /api/sources/procore/status` | `ProcoreSourceStatus` |
| `startProcoreSourceAuth()` | `POST /api/sources/procore/auth/start` | `ProcoreAuthStartResult` (reused) |
| `getProcoreSourceAuthStatus(flowId)` | `GET /api/sources/procore/auth/status?flow_id=` | `AuthFlowStatus` (reused) |
| `refreshProcoreSourceAuth()` | `POST /api/sources/procore/auth/refresh` | — |
| `refreshSourcesDryRun()` | `POST /api/sources/refresh/dry-run` | `RefreshReceipt` |
| `refreshSourcesLocal()` | `POST /api/sources/refresh/local` | `RefreshReceipt` |
| `refreshSourcesLive(confirm)` | `POST /api/sources/refresh/live` (`{confirm}`) | `RefreshReceipt` |
| `refreshSources(mode, {confirm})` | dispatch by `RefreshMode` | `RefreshReceipt` |
| `getSchedulerStatus()` | `GET /api/scheduler/daily-source-refresh/status` | `SchedulerStatus` |

New `interface`s (`EnvironmentStatus`, `SourcesStatus`, `GraphSourceStatus`, `ProcoreSourceStatus`,
`SchedulerStatus`, `RefreshReceipt`) follow the file's any-tolerant house style and model the safe
metadata-only response shapes (e.g. Graph `state` + `scope_presence`; Procore `state` + `missing_config`
+ `missing_mapping` + `mapping`; refresh `dry_run`/`live_mode`/`live_read_performed`/`reason`). All are
added to the aggregate `api` object + default export.

### Action URL selection

`REFRESH_ENDPOINTS: Record<RefreshMode, string>` + `refreshSources(mode, opts?)` choose the endpoint by
mode and only attach the confirmation payload for `live` (throws on an unknown mode). This makes
action→URL selection explicit and unit-testable.

## Error normalization + no raw JSON (reused)

Reuses the existing committed `frontend/src/lib/errorCopy.ts`: `getErrorCopy(error)` →
`{userMessage, technicalDetail}` maps known backend codes (`not_found`, `forbidden`, `invalid_ui_role`,
`blocked_db_unavailable`) and falls back to a generic safe message for 500/network, preserving the raw
detail only for the collapsible admin-only `TechnicalDetails`. `safeDisplayText()` never JSON-dumps
objects, and `ErrorState` renders normalized copy. `fetchJson` already throws an `Error` carrying only a
safe `.message` (status + optional `.detail`/`.message`) + `.status` — so no raw payload reaches the UI.
No new error layer; `errorCopy.ts`/`statusCopy.ts` are unchanged.

## Tests

`frontend/src/lib/sourcesApi.test.ts` (vitest, stubs `global.fetch` to exercise the real `fetchJson`):
- **response mapping** — environment / aggregate / Graph / Procore / scheduler 200 bodies map to typed
  objects at the right URLs; `X-HB-UI-Role` header sent.
- **action URL selection** — dry-run/local/live endpoints + methods; `live` carries `{"confirm":true}`;
  `refreshSources` dispatches by mode; unknown mode throws; auth-status poll encodes `flow_id`.
- **failure copy** — 404 `not_found` → friendly copy; 500 and network → generic safe copy with no `{`/`}`
  and no raw detail leak.

## Verification (P05)

`cd frontend && npx vitest run src/lib` → 19 passed (incl. `copyHelpers.test.ts`, confirming reuse did
not regress). `npx eslint src/lib/api.ts src/lib/sourcesApi.test.ts` clean. `npx tsc -b` → 0 errors
across the frontend. Method↔endpoint paths match the P01–P04 routes verified live in prior phases.
