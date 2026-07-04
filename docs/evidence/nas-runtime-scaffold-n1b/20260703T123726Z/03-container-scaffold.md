# 03 — Container Scaffold (N1B)

New files under `deploy/nas/` (+ repo-root `.dockerignore`). Review-only; not built/run.

## Dockerfile (`deploy/nas/Dockerfile`)
- Base `python:3.12-slim` (satisfies `requires-python >=3.12`).
- Creates non-root user `hbsvc` **uid 1028, gid 100** = the NAS `personal-assistant-svc:users`, so files written to the mounted app-support keep correct NAS ownership.
- `COPY . /app` then `pip install -e ".[analytics-ui]"` — source retained for repo-relative behavior; sensitive/heavy paths excluded by `.dockerignore`.
- ENV defaults: `HB_PA_CONFIG=/config/hb-pa-config.yml`, `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`, `PYTHONUNBUFFERED=1`.
- `EXPOSE 8000`; `USER hbsvc`; CMD = `python -m uvicorn hb_assistant.construction.analytics.api:create_app --factory --host 0.0.0.0 --port 8000` (0.0.0.0 = container-internal only).

## .dockerignore (repo root)
Excludes from the build context: `.git`, `.venv`, `**/__pycache__`, node_modules/frontend dist, **`config/config.yml`** (keeps Mac paths + tenant/client IDs out of the image), `.env*`, all `*.sqlite*`/`*.db`, `*.key`/`*.pem`/`msal-token-cache*`/`text-vault*`/`**/auth/`/`**/security/`, `docs/evidence`, `**/local-sensitive/`, `tmp/`, `logs/`. → the image carries **source + packaging only**; config/DB/secrets come at runtime.

## compose.yaml (`deploy/nas/compose.yaml`)
- One service `hb-personal-assistant-backend`; `build.context: ../..` + `dockerfile: deploy/nas/Dockerfile`; `image: hb-personal-assistant:nas`.
- `user: "1028:100"`.
- Ports: `"${HB_PUBLISH_ADDR:-127.0.0.1}:8000:8000"` — **loopback by default; never 0.0.0.0**; NAS host 8000 → container 8000.
- Env: `HB_PA_CONFIG`, `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`, `PYTHONUNBUFFERED=1`.
- Volumes:
  - `${HB_CONFIG_FILE:-/volume1/personal-assistant/config/hb-pa-config.yml}:/config/hb-pa-config.yml:ro` (read-only).
  - `${HB_APP_SUPPORT_DIR:-/volume1/personal-assistant/app-support}:${...}` (read/write; identical container path so it equals `application_support_root`; NAS-local).
- `restart: "no"` (production restart policy explicitly deferred).
- `deploy.resources.limits.memory: 768M` (protects the memory-marginal NAS).
- `healthcheck` present but documented as scratch-only (it can touch/migrate the DB); long `start_period`.
- **Absent by design:** no scheduler/watcher service, no DB copy/migrate job, no vault mount, no source-roots mount, no secrets mount, no reverse proxy.

## Scripts (`deploy/nas/scripts/`)
- `check-runtime-safety.sh` — static safety validator (see `05`).
- `render-config.sh` — copy an example config to the NAS path + validate; refuses overwrite without `--force`; adds no secrets.
- `stop.sh` — stops only the HB service (`--down` removes just this project).
- `logs.sh` — HB service logs only.
- `health.sh` — queries `/health`; **refuses unless `HB_SMOKE_OK=1`** (guards against hitting a live DB).
- `smoke-local.sh` — static-only (safety + YAML parse + `docker compose config`); never starts the backend.
