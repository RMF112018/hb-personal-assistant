# NAS Viewer Mode

The NAS backend is approved **only** as a **read-only / local-cache viewer** until a separate ingestion cutover phase is authorized.

## What viewer mode can do

- Serve sanitized `/health` and read-only analytics API surfaces over **loopback** (`127.0.0.1:8000`).
- Read NAS-local SQLite at `/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite`.
- Expose admin metadata endpoints (`/api/admin/schema/status`, `/api/admin/db/status`) to **local operators** with `X-HB-UI-Role: admin`.
- Report environment/onboarding readiness without live Graph/Procore calls.

## What viewer mode cannot do

- Source ingestion, external source watchers, or schedulers.
- Background workers (quality poll, source watcher) — disabled by compose.
- Live Graph/Procore reads or token refresh against macOS Keychain.
- Secrets / Text Vault / MSAL / Procore migration (not in scope).
- Cloudflare, Tailscale Serve/Funnel, or public host bind (`0.0.0.0`).
- Silent schema migration on restart (PR A startup policy).
- SMB/NFS/Mac-mounted DB paths (`HB_NAS_RUNTIME=1` guard).

## Required runtime posture

| Item | Requirement |
|---|---|
| Image | Prebuilt `hb-personal-assistant:nas` (see [BUILD.md](BUILD.md)) |
| `HB_NAS_RUNTIME` | `1` (compose) |
| `HB_PA_CONFIG` | `/config/hb-pa-config.yml` in container |
| `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` | `1` |
| Host publish | `HB_PUBLISH_ADDR=127.0.0.1` only |
| DB path | NAS-local under `/volume2/personal-assistant/.../db/hb-personal-assistant.sqlite` |

## Approved endpoints (bounded smoke set)

| Endpoint | Role | Notes |
|---|---|---|
| `GET /health` | viewer+ | Sanitized posture only |
| `GET /api/admin/schema/status` | admin | Metadata counts |
| `GET /api/admin/db/status` | admin | Full posture metadata |
| `GET /api/environment` | viewer+ | Live reads disabled |
| `GET /api/onboarding/readiness` | viewer+ | No secrets/tokens |

## Disallowed actions

- `POST /api/admin/schema/migrate` during normal viewer operation (operator-only migration windows).
- Any endpoint that triggers source refresh, vault writes, or live sync.
- `docker compose up --build` in production viewer start path.
- Publishing port 8000 on tailnet/public without explicit exposure phase authorization.

## Operator lifecycle

```sh
cd /path/to/repo/deploy/nas

# Start (requires prebuilt image; no build)
./scripts/start.sh

# Status / health
./scripts/status.sh
HB_VIEWER_HEALTH_OK=1 ./scripts/health.sh
HB_VIEWER_HEALTH_OK=1 HB_ADMIN_DB_STATUS=1 ./scripts/health.sh

# Read-only DB validation
./scripts/validate-db.sh

# Stop
./scripts/stop.sh --down
# or emergency:
./scripts/emergency-shutdown.sh
```

Docker on the NAS typically requires **operator-mediated sudo** for `bfetting`.

## Rollback / stop

1. `./scripts/emergency-shutdown.sh` — compose down + verify no LISTEN on 8000.
2. Confirm with `./scripts/status.sh`.
3. Optional: remove image (`docker image rm hb-personal-assistant:nas`) — see [CLEANUP.md](CLEANUP.md).

Rollback does not mutate the production DB when PR A startup policy holds (schema == head, no migration flag).

## Evidence

- N4C backend smoke: PASS
- N4C-PR-A re-smoke @ `9bcf7e2e`: PASS (viewer hardening validated)

PR B (single-writer, WAL policy, online backup) is **deferred** until ingestion/workers are authorized.
