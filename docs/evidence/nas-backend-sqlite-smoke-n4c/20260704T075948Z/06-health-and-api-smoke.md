# 06 — Health and API Smoke

All requests from NAS host loopback: `http://127.0.0.1:8000`. Sanitized summaries only.

## Endpoint results

| Endpoint | HTTP | Notes |
|---|---|---|
| `GET /health` | **200** | `status=ok`; `schema_version=98`; `schema_expected=98`; `schema_ready=true`; `background_worker_mode=disabled`; background workers (quality poll, source watcher) **false** |
| `GET /api/admin/schema/status` | **200** | Header `X-HB-UI-Role: admin`; schema 98 ready (runtime reported `table_count=507` — see `09` for DB-truth 506) |
| `GET /api/environment` | **200** | Live reads **disabled** |
| `GET /api/onboarding/readiness` | **200** | No tokens/secrets returned; no Graph/Procore live calls |

## Not called

Scheduler, source ingestion, sync, vault write, or auth device-login endpoints were **not** invoked.

## Config env resolution

Container reads **`HB_PA_CONFIG=/config/hb-pa-config.yml`**, mounted from host:

`/volume1/personal-assistant/config/hb-pa-config.yml`

(`HB_CONFIG_FILE` in compose is the **host volume source** for that mount; app code uses `HB_PA_CONFIG`.)
