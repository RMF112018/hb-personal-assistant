# HB Personal Assistant — NAS Runtime (Container Manager) — Operator Runbook

**Phase N1B scaffold — review-only.** These files let the HB backend run later on the Synology
DS923+ via Container Manager/Docker on **port 8000**, with the app-support root on **NAS-local**
storage. **Nothing here has been built or run.** Do not start the container until a later phase
(N1C scratch smoke, then a cutover phase) is explicitly authorized.

## What this is
- `Dockerfile` — Python 3.12 image, installs `.[analytics-ui]`, runs the FastAPI factory
  `hb_assistant.construction.analytics.api:create_app` on `0.0.0.0:8000` **inside the container**,
  as non-root uid `1028:100` (the NAS `personal-assistant-svc`), workers disabled by default.
- `compose.yaml` — one service `hb-personal-assistant-backend`; publishes to **loopback** by default;
  mounts config read-only and app-support read/write; `restart: "no"`; no vault/source-roots/secrets;
  no scheduler/watcher service.
- `hb-pa-config.nas.example.yml` / `hb-pa-config.smoke.example.yml` — example `HB_PA_CONFIG` files
  (no secrets); production-intent vs disposable scratch app-support roots.
- `.env.example` — host paths + publish address (never `0.0.0.0`).
- `scripts/` — `check-runtime-safety.sh`, `render-config.sh`, `smoke-local.sh` (static), `stop.sh`,
  `logs.sh`, `health.sh`.

## Prerequisites before any start (N1C or later)
- **Port 8000 free** — Portainer CE was stopped and set `restart=no` in N1A. **Do not restart Portainer
  on 8000.** If you need Portainer, recreate it without publishing `8000`.
- **auth/security permissions hardened** before any secret is placed (still 0777 + broad ACL — N1A blocker).
- **Public exposure confirmed safe** (DSM firewall + router + Tailscale) — see N1A `06`.
- **Memory headroom** — N1A freed ~300 MB (available ~1.9 GiB). Do not run sustained load without approval.
- Container Manager/Docker active (it is), and the repo cloned on the NAS to build the image.

## NAS paths
- Service root: `/volume1/personal-assistant`
- Runtime config: `/volume1/personal-assistant/config/hb-pa-config.yml`
- App-support (live intent): `/volume1/personal-assistant/app-support`
- App-support (scratch smoke): `/volume1/personal-assistant/app-support-smoke`

## 1) Put a config on the NAS (no secrets)
```sh
# production-intent config:
deploy/nas/scripts/render-config.sh nas
# OR disposable scratch config for the N1C smoke:
deploy/nas/scripts/render-config.sh smoke
```
`render-config.sh` copies the example and runs the safety validator. **Add no secrets.**

## 2) Validate (no build, no run)
```sh
deploy/nas/scripts/check-runtime-safety.sh /volume1/personal-assistant/config/hb-pa-config.yml
deploy/nas/scripts/smoke-local.sh
```

## 3) Start — DEFERRED (do not run without authorization)
```sh
# DEFERRED until N1C is authorized. For the SCRATCH smoke only:
#   export HB_APP_SUPPORT_DIR=/volume1/personal-assistant/app-support-smoke
#   export HB_CONFIG_FILE=/volume1/personal-assistant/config/hb-pa-config.smoke.yml
#   cd deploy/nas && docker compose up -d --build
```

## 4) Health (scratch only)
```sh
HB_SMOKE_OK=1 deploy/nas/scripts/health.sh    # refuses unless HB_SMOKE_OK=1; /health can touch the DB
```

## 5) Stop
```sh
deploy/nas/scripts/stop.sh          # stops ONLY the HB service
deploy/nas/scripts/stop.sh --down   # also removes the HB compose project (keeps images/volumes)
```

## 6) Logs
```sh
deploy/nas/scripts/logs.sh                # follow HB service logs
deploy/nas/scripts/logs.sh --tail 200     # last 200 lines
```

## 7) Rollback
```sh
deploy/nas/scripts/stop.sh --down
docker image rm hb-personal-assistant:nas   # optional: remove the built image
# (Optional) delete the disposable scratch root only:
#   rm -rf /volume1/personal-assistant/app-support-smoke
```
Rollback affects only the HB project/image and the scratch root. It never touches the live app-support,
DB, secrets, other containers, or Synology packages.

## DO NOT
- Do **not** copy the live Mac DB or any DB to the NAS.
- Do **not** copy secrets (MSAL caches, Procore tokens, Fernet/Text-Vault keys/blobs).
- Do **not** mount `/Volumes/*` (SMB) as a DB path — WAL SQLite over SMB/NFS can corrupt.
- Do **not** mount the live Obsidian vault or source-roots.
- Do **not** restart Portainer on port 8000.
- Do **not** enable background workers, source watchers, or schedulers.
- Do **not** point the smoke at a live DB — scratch root only.

## Future DB migration (later phase, not now)
Move the DB with the **SQLite backup API** (`sqlite3.connect("file:<src>?mode=ro", uri=True)` → `src.backup(dst)`;
pattern in `src/hb_assistant/launcher/profiles.py:214-223`) — **never a raw copy of a hot WAL DB**. Migrate the
Text-Vault key + `.enc` blobs + DB together; re-provision MSAL/Procore on the NAS (no macOS Keychain).
