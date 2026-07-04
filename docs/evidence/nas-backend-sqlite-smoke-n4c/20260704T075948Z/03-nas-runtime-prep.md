# 03 — NAS Runtime Prep

## Staged repo

| Item | Value |
|---|---|
| Path | `/volume1/personal-assistant/runtime/n4c-backend-smoke-20260704T075948Z/repo` |
| Method | `tar` over SSH (excluded `.git`, `.venv`, caches, `local-sensitive`, raw DB/WAL/SHM) |
| Size | ~290 MB |

## Config rendered

| Item | Value |
|---|---|
| Host path | `/volume1/personal-assistant/config/hb-pa-config.yml` |
| Source | `deploy/nas/scripts/render-config.sh nas` |
| `application_support_root` | `/volume1/personal-assistant/app-support` |
| Safety check | `check-runtime-safety.sh` — PASS |

## Image build (host-network)

Bridge DNS failed during `docker compose build` (`pip` could not resolve PyPI).

**Resolution:**

1. Attempted Docker daemon DNS override — backed up to `dockerd.json.bak.n4c-20260704T075948Z`; override **did not** fix bridge DNS.
2. **Successful build:** `docker build --network host -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .`
3. Restored original `dockerd.json` from backup; `docker info` OK.

`--network host` used **build-time only** — not runtime.

## Runtime compose

```bash
HB_PUBLISH_ADDR=127.0.0.1 \
HB_CONFIG_FILE=/volume1/personal-assistant/config/hb-pa-config.yml \
HB_APP_SUPPORT_DIR=/volume1/personal-assistant/app-support \
docker compose up --no-build -d
```

## Smoke log

`/volume1/personal-assistant/app-support/logs/n4c-backend-smoke-20260704T075948Z.log`
