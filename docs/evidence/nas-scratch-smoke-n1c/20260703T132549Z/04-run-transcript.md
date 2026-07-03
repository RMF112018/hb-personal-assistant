# 04 — N1C Run Transcript (verbatim)

Authoritative step-by-step of the successful N1C run (the raw `nas-artifacts/run-transcript.log` is gitignored
by the repo's `*.log` rule, so it is reproduced here as committable markdown). Build details are in `01`/`02`;
`nas-artifacts/health.json` holds the full `/health` payload.

```text
RUN_START 2026-07-03T14:28:19Z
############ STEP 1: scratch paths + config (no live DB) ############
[config]
  application_support_root: /volume1/personal-assistant/app-support-smoke
[scratch dir]
drwxrwxrwx+ 1 personal-assistant-svc users 0 Jul  3 13:34 /volume1/personal-assistant/app-support-smoke
[live app-support BEFORE — expect 0]
live_file_count_before=0
[memory before]
Mem:           19Gi       1.1Gi        15Gi       218Mi       3.0Gi        16Gi
############ PRECHECK: port 8000 free before start ############
port_8000_free_before=yes
############ STEP 3: start container (loopback 127.0.0.1:8000) ############
 Container hb-personal-assistant-backend  Started
[docker ps]
hb-personal-assistant-backend | Up 2 seconds (health: starting) | 127.0.0.1:8000->8000/tcp
[docker port — must be 127.0.0.1, never 0.0.0.0]
8000/tcp -> 127.0.0.1:8000
[host listen socket]
tcp        0      0 127.0.0.1:8000          0.0.0.0:*               LISTEN
############ STEP 4: confirm background workers disabled ############
env_HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1
############ STEP 5: /health from NAS-local ############
health_reachable=1 after ~9s
[payload]
{"status":"ok","surface":"analytics.fastapi_shell","role":{"role":"viewer","permission_scope":"read_only"},"schema_version":98,"schema_expected":97,"schema_ready":true,"chat_enabled":false,"guardrails":{"read_only":true,"local_first":true,"no_cli_shellout":true,"no_live_endpoint_calls":true,"no_external_writeback":true,"active_chat_routes":false,"chat_enabled":false},"background_worker_mode":"disabled","background_workers_disabled_by_env":true,"background_workers":{"quality_poll_started":false,"source_watcher_initialized":false,"source_watcher_started":false}}
############ STEP 6: capture container logs ############
container_log_lines=5
[tail]
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.20.0.1:54312 - "GET /health HTTP/1.1" 200 OK
############ STEP 7: prove live untouched + writes went to scratch ############
live_file_count_after=0   (expect 0 == before)
[live db dir — expect no *.sqlite]
drwxrwxrwx+ 1 personal-assistant-svc users  0 Jul  3 11:42 backups
[scratch files — expect hb-personal-assistant.sqlite here]
  /volume1/personal-assistant/app-support-smoke/db/hb-personal-assistant.sqlite
  /volume1/personal-assistant/app-support-smoke/analytics/forecast_runtime_config.json
############ STEP 8: stop + down ############
 Container hb-personal-assistant-backend  Stopped
 Container hb-personal-assistant-backend  Removed
 Network hbn1c_default  Removed
[remaining named containers — expect none]
############ STEP 9: port 8000 free again ############
port_8000_free_after=yes
[all containers — unrelated untouched]
ubuntu-1 | Up About an hour
homeAssistant | Up About an hour
[memory after]
Mem:           19Gi       1.1Gi        15Gi       218Mi       3.0Gi        16Gi
############ STEP 10: final live-untouched assertion ############
live_file_count_final=0
RUN_END 2026-07-03T14:28:37Z
===== N1C RUN COMPLETE =====
```
