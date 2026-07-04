# 01 — N1C Requirements Matrix (12/12 PASS)

All evidence is from `nas-artifacts/run-transcript.log` (authoritative step-by-step) plus `build.log`,
`container.log`, `health.json`.

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 1 | Verify scratch paths + config | PASS | `application_support_root: /volume1/personal-assistant/app-support-smoke` (smoke config); scratch dir present; build context `src/ deploy/ pyproject.toml README.md LICENSE .dockerignore` |
| 2 | Build image from staged NAS context | PASS | `build.log`: `Successfully installed … fastapi-0.139.0 uvicorn-0.49.0 hb-personal-assistant-1.3.0 …`; `IMAGE hb-personal-assistant:nas 263MB 144ac90ca3d7` |
| 3 | Start on **loopback** `127.0.0.1:8000` | PASS | `docker port` → `8000/tcp -> 127.0.0.1:8000`; host socket `tcp 127.0.0.1:8000 … LISTEN` (never `0.0.0.0`); `docker ps` ports `127.0.0.1:8000->8000/tcp` |
| 4 | `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` | PASS | `printenv` → `1`; `/health`: `background_worker_mode:"disabled"`, `background_workers_disabled_by_env:true`, `quality_poll_started:false`, `source_watcher_initialized:false`, `source_watcher_started:false` |
| 5 | `/health` from **NAS-local** curl | PASS | `health_reachable=1 after ~9s`; `health.json` → `{"status":"ok",…,"schema_ready":true}` (viewer role, auth-free) |
| 6 | Capture logs | PASS | `container.log`: `Started server process [1]` → `Application startup complete` → `GET /health HTTP/1.1 200 OK` |
| 7 | Live app-support untouched | PASS | `live_file_count_before=0`, `…_after=0`, `…_final=0`; live `db/` holds only empty `backups/`; writes went to **scratch**: `app-support-smoke/db/hb-personal-assistant.sqlite` + `analytics/forecast_runtime_config.json` |
| 8 | Stop / down the container | PASS | `Container … Stopped/Removed`, `Network hbn1c_default Removed`; remaining named containers: none |
| 9 | Port 8000 free again | PASS | `port_8000_free_after=yes` |
| 10 | Capture evidence | PASS | `nas-artifacts/{build.log,container.log,health.json,run-transcript.log}` (this bundle) |
| — | No live DB / copied DB / secrets / vault / source-roots | PASS | Only mounts: smoke config `:ro` + scratch app-support (compose `config`, `02`); no other mounts |
| — | No Portainer restart / unrelated-container / firewall changes | PASS | `ubuntu-1`, `homeAssistant` `Up` throughout & untouched; Portainer left off 8000; no DSM/router/Tailscale action |

## Notable non-blocking observation
`/health` reports `schema_version:98` while `schema_expected:97` (`LATEST_SCHEMA_VERSION`). A fresh scratch
DB migrated one version **ahead** of the code's expected constant (`schema_ready:true` because `98 >= 97`).
This is a pre-existing code inconsistency (migrator defines a V98 the `LATEST_SCHEMA_VERSION` constant hasn't
caught up to), surfaced here but **not caused by N1C** and **not a smoke blocker**. Worth a follow-up sync.

## Environment facts at run time
- NAS memory: **19Gi total, 16Gi available** (20GB RAM upgrade confirmed), swap unstressed — comfortable for the smoke.
- Container ran as **non-root** `hbsvc` uid 1028 / gid 100 (= `personal-assistant-svc:users`).
- Compose project `hbn1c`; fixed `container_name: hb-personal-assistant-backend`; `restart: "no"`; mem limit 768M.
