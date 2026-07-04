# 08 — Logs and error review

Source: `evidence/compose-logs-tail.txt`

## Startup

- Uvicorn started; application startup complete.
- No `DbStorageGuardError`, `StartupSchemaPolicyError`, `SQLITE_BUSY`, or `database locked`.
- No source watcher, scheduler, or ingestion startup lines.

## Request log (safe GETs only)

| Request | Status |
|---|---|
| `GET /health` | 200 |
| `GET /api/admin/schema/status` | 200 |
| `GET /api/admin/db/status` | 200 |
| `GET /api/environment` | 200 |
| `GET /api/onboarding/readiness` | 200 |

## Follow-up: startup posture log

Captured tail does **not** include an explicit `db_posture_at_startup` line. Startup posture is otherwise evidenced via `/health` and `/api/admin/db/status`. Non-blocking follow-up to improve log visibility.

## Secrets scan

No tokens, vault material, or raw row payloads in captured log tail.
