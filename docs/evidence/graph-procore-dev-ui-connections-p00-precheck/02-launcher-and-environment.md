# P00 — 02 Launcher and Environment

Captured: 2026-06-07 · Environment: **dev** · App version: `1.3.0` · build_sha `876dd6e6`

## Launcher lifecycle results

| Step | Result |
|---|---|
| `launcher close --environment dev --action quit` | `status: ok`; terminated backend/frontend/scheduler from prior session; receipt written to dev evidence dir |
| `launcher dev --plan` | `status: ok`; planned 3 processes (backend, frontend, scheduler) |
| `launcher dev --open --open-timeout-seconds 45` | `status: ok`; `frontend_reachable: true`, `frontend_opened: true`, `open_method: browser`; preflight `ok: true` |
| `launcher status --environment dev` | `status: ok`; backend/frontend/scheduler all `running` |

## Recorded environment facts (per prompt)

| Field | Value |
|---|---|
| Dev app-support root | `~/Library/Application Support/HB Personal Assistant (Dev)` |
| Dev DB path | `…(Dev)/db/hb-personal-assistant.sqlite` |
| Log path | `…(Dev)/logs` (launcher logs under `logs/launcher/`) |
| Frontend port | `5173` (vite `npm run dev`, `--strictPort`, host `127.0.0.1`) |
| Backend port | `8000` (uvicorn factory `hb_assistant.construction.analytics.api:create_app`) |
| Frontend URL | `http://127.0.0.1:5173` (`frontend_url_source: fallback`; alias `not_configured`) |
| Environment mode | `dev` |
| Frontend mode | `npm_dev` |
| Backend mode | `uvicorn_factory_dev` |
| **Source mode** | **`source_refresh_mode: mock_data`** (Dev uses mock data — live reads off) |
| Scheduler | `scheduler_enabled: true`, running (`daily-source-refresh --loop`) |
| MCP | `external_client_managed`, `stdio`, not launcher-managed |

## Process health (launcher dev --open)

| Process | PID | Status | Port | Log |
|---|---|---|---|---|
| backend | 46331 | running | 8000 | `…/logs/launcher/dev-backend.log` |
| frontend | 46332 | running | 5173 | `…/logs/launcher/dev-frontend.log` |
| scheduler | 46333 | running | — | `…/logs/launcher/dev-scheduler.log` |

Browser-open result: `frontend_opened: true`, `open_method: browser`, `actual_shell: browser`,
`window_close_intercept_supported: false`, `lifecycle_control: cli_or_ui_action_required`.

## Backend `/health` (`:8000`)

`HTTP 200`:
```json
{"status":"ok","surface":"analytics.fastapi_shell","role":{"role":"viewer","permission_scope":"read_only"},
 "schema_version":40,"schema_expected":40,"schema_ready":true,"chat_enabled":false,
 "guardrails":{"read_only":true,"local_first":true,"no_cli_shellout":true,"no_live_endpoint_calls":true,
 "no_external_writeback":true,"active_chat_routes":false,"chat_enabled":false}}
```
Note: health is served at `/health`, **not** `/api/health` (`/api/health` → 404 on both ports — expected).

## Endpoint reachability matrix (role `admin`, via `:5173` proxy and direct `:8000`)

| Endpoint | proxy :5173 | direct :8000 |
|---|---|---|
| `/api/onboarding/readiness` | 200 | 200 |
| `/api/settings/accounts` | 200 | 200 |
| `/api/settings/connections/accounts` | 200 | 200 |
| `/api/settings` | 200 | 200 |
| `/api/settings/projects` | 200 | 200 |
| `/api/settings/sources` | 200 | 200 |
| `/api/settings/data-quality/summary` | 200 | 200 |
| `/api/settings/data-quality/detail` | 200 | 200 |
| `/api/settings/admin-sync` | 200 | 200 |
| `/api/today` | 200 | 200 |
| `/api/admin/source-sync-health` | 200 | 200 |
| **`/api/environment`** | **404** | **404** |
| **`/api/sources/status`** | **404** | **404** |

**Key takeaways:**
1. The Vite `/api` → `:8000` proxy is working (proxy and direct match for every route) — **no
   CORS/base-url/proxy failure**.
2. Every per-card Connections/Settings endpoint already returns **200** — the existing auth/connection
   backend contract is present.
3. The only **missing** endpoints are the **aggregate** `/api/environment` and `/api/sources/status`
   (HTTP 404), exactly the **GPC-P0-001** gap ("Dev UI lacks aggregate source status").
