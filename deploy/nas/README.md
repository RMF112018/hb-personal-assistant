# HB Personal Assistant — NAS Runtime (Viewer Mode)

Operator runbook for Synology DS923+ Docker viewer backend on **port 8000** (loopback only).

**Current approval:** read-only / local-cache **viewer mode** only — see [VIEWER_MODE.md](VIEWER_MODE.md).

PR A hardening + N4C-PR-A re-smoke **PASS** @ `9bcf7e2e`. PR B (writer/WAL/backup) **not started**.

## Viewer posture summary

| Property | Value |
|---|---|
| Mode | Read-only viewer / local-cache |
| Workers | **Disabled** (`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`) |
| Source ingestion | **Disabled** |
| Secrets | **Not required** for viewer smoke |
| Cloudflare / public exposure | **Not authorized** |
| DB storage | NAS-local SQLite only (no SMB/NFS) |
| Docker sudo | Operator-mediated sudo expected for `bfetting` |

## Components

- [Dockerfile](Dockerfile) — Python 3.12, `.[analytics-ui]`, `HB_NAS_RUNTIME=1`, workers disabled.
- [compose.yaml](compose.yaml) — single service, loopback publish, `restart: "no"`.
- [scripts/](scripts/) — lifecycle, validation, safety checks.
- [BUILD.md](BUILD.md) — image build/load paths.
- [CLEANUP.md](CLEANUP.md) — post-smoke artifact hygiene.
- [VIEWER_MODE.md](VIEWER_MODE.md) — allowed/disallowed behavior.

## NAS paths

| Purpose | Path |
|---|---|
| Service root | `/volume1/personal-assistant` |
| Runtime config | `/volume1/personal-assistant/config/hb-pa-config.yml` |
| App-support / DB | `/volume1/personal-assistant/app-support` |
| Scratch smoke (optional) | `/volume1/personal-assistant/app-support-smoke` |

## Quick start (viewer — requires prebuilt image)

```sh
# 1) Config (no secrets)
deploy/nas/scripts/render-config.sh nas
deploy/nas/scripts/check-runtime-safety.sh /volume1/personal-assistant/config/hb-pa-config.yml

# 2) Build or load image (see BUILD.md) — NOT done by start.sh

# 3) Start viewer backend (loopback, no build)
cd deploy/nas && ./scripts/start.sh

# 4) Health / status
HB_VIEWER_HEALTH_OK=1 ./scripts/health.sh
./scripts/status.sh

# 5) Stop (do not leave running after validation)
./scripts/stop.sh --down
```

## Lifecycle scripts

| Script | Purpose |
|---|---|
| [start.sh](scripts/start.sh) | `compose up --no-build -d`; fails if image missing |
| [stop.sh](scripts/stop.sh) | Stop HB service only (`--down` removes project) |
| [restart.sh](scripts/restart.sh) | stop --down + start (no build) |
| [status.sh](scripts/status.sh) | compose ps, port bind, LISTEN check |
| [health.sh](scripts/health.sh) | `/health`; optional admin DB status flag |
| [validate-db.sh](scripts/validate-db.sh) | Read-only DB quick_check/schema/counts |
| [emergency-shutdown.sh](scripts/emergency-shutdown.sh) | compose down + LISTEN verify |
| [logs.sh](scripts/logs.sh) | HB service logs only |
| [check-runtime-safety.sh](scripts/check-runtime-safety.sh) | Static scaffold validator |

## Startup schema policy (PR A)

NAS runtime (`HB_NAS_RUNTIME=1`) fail-closed rules — see [VIEWER_MODE.md](VIEWER_MODE.md):

- DB missing → fail startup
- schema == head → start, **no** silent migration
- schema < head → fail unless explicit operator migration flags + backup receipt
- schema > head → fail always

## DO NOT

- Enable workers, source watchers, or schedulers.
- Mount `/Volumes/*`, secrets, vault, or source-roots.
- Publish `0.0.0.0:8000` without exposure phase authorization.
- Run `start.sh` without a prebuilt image (no implicit build).
- Restart Portainer on port 8000.
- Push secrets or perform Text Vault / MSAL / Procore migration in viewer mode.

## Persistent service

**Not authorized** by this runbook. Viewer scripts are for bounded operator validation only.

## Future phases (deferred)

- **PR B:** single-writer, WAL/checkpoint, online backup (before ingestion).
- **Ingestion cutover:** secrets + workers + exposure — separate authorization.
- **DB migration:** SQLite backup API only — never raw hot WAL copy.
