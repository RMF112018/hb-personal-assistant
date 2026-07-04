# 08 — Logs and Error Review

Log source: container stdout via `docker compose logs` during smoke. Committed evidence is summarized; no secrets/tokens in committed material.

## Findings

| Category | Result |
|---|---|
| Uvicorn startup | **Normal** — application startup complete, serving on container :8000 |
| HTTP requests | **Safe GET only** — `/health`, `/api/admin/schema/status`, `/api/environment`, `/api/onboarding/readiness` |
| `SQLITE_BUSY` | **None** |
| Database locked | **None** |
| Source ingestion | **None** |
| Scheduler startup | **None** |
| Watcher startup | **None** |
| Graph/Procore live sync | **None** |
| Vault writes | **None** |
| Secrets/tokens in logs | **None** in committed excerpts |

## Docker build log note

Build-time pip retries (bridge DNS failure) appear in build log only; runtime logs clean.
