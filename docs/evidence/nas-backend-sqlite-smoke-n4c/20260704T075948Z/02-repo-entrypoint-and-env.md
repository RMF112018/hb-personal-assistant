# 02 — Repo Entrypoint and Environment

## Backend entrypoint

| Item | Value |
|---|---|
| Factory | `hb_assistant.construction.analytics.api:create_app` |
| Runtime CMD | `python -m uvicorn hb_assistant.construction.analytics.api:create_app --factory --host 0.0.0.0 --port 8000` (container namespace; host publish loopback) |
| Source | [`deploy/nas/Dockerfile`](../../../../deploy/nas/Dockerfile), [`api.py`](../../../../src/hb_assistant/construction/analytics/api.py) |

## Config / DB path (repo-truth)

| Variable | Role |
|---|---|
| **`HB_PA_CONFIG`** | App reads this — path to YAML inside container: `/config/hb-pa-config.yml` |
| **`HB_CONFIG_FILE`** | Compose **host volume source** only — maps to `/config/hb-pa-config.yml:ro` |
| **`paths.application_support_root`** | YAML → `PathPolicy` → `{root}/db/hb-personal-assistant.sqlite` |
| **`HB_APP_SUPPORT_DIR`** | Compose host mount for app-support (identical path in container) |

Production NAS config: `/volume1/personal-assistant/config/hb-pa-config.yml`

## Worker / ingestion disable

| Variable | Value | Effect |
|---|---|---|
| `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` | `"1"` (exact) | Disables quality poll, source watcher, source-root registration |

No separate scheduler service in compose. No ingestion env flags enabled.

## Safe read-only endpoints (N4C smoke set)

- `GET /health`
- `GET /api/admin/schema/status` (`X-HB-UI-Role: admin`)
- `GET /api/environment`
- `GET /api/onboarding/readiness`

## Startup migration note

Lifespan calls `ensure_forecast_managed_storage()` → may run `SQLiteMigrator.apply()` on managed DB. At schema **98** with head **98**, expected no-op; post-smoke DB-truth confirms schema **98**, table count **506**.
