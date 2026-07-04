# 01 — Preflight + Deploy Verification

## Git preflight (local worktree)
- Branch `ops/nas-copied-db-n3-20260704T060648Z`, HEAD `e9ac67f5` (`docs(nas): add N5C-R CLI runtime blocker
  evidence`), clean, 13 ahead / 0 behind, local branch only (never pushed).

## Deploy artifacts verified (read-only, from the N4C repo)
`deploy/nas/` contains `Dockerfile`, `compose.yaml`, `hb-pa-config.nas.example.yml`, `hb-pa-config.smoke.example.yml`,
`.env.example`, `README.md`, `scripts/`.

### Dockerfile (`deploy/nas/Dockerfile`)
- `FROM python:3.12-slim AS base` — satisfies `requires-python >=3.12` (the native-venv blocker from N5C-R).
- Creates non-root runtime user `hbsvc` = uid **1028** / gid **100** (= `personal-assistant-svc:users`).
- Bakes `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` and `HB_PA_CONFIG=/config/hb-pa-config.yml` (config supplied only
  at runtime via mount).
- `COPY . /app` + `chmod -R a+rX /app` (read/traverse only) + `pip install -e ".[analytics-ui]"`.
- Default `CMD` = **uvicorn backend** (`hb_assistant.construction.analytics.api:create_app`) → must be **overridden**
  for a CLI-only proof.

### compose.yaml
- Single service `hb-personal-assistant-backend`, `image: hb-personal-assistant:nas`, `user: "1028:100"`.
- Publishes to **loopback only** by default; mounts config **read-only** and **app-support read/write**; healthcheck
  hits `/health` (**touches the DB**). No scheduler/watcher/DB-copy service.
- **Therefore `compose up` was NOT used** — it would mount app-support RW and open the DB via healthcheck. The CLI
  proof used plain `docker run` with the command overridden and **no mounts**.

## Docker access
- `docker` binary at `/usr/local/bin/docker` (→ Synology ContainerManager); daemon socket is root-owned → **sudo
  required** (bfetting is in `administrators` but has no docker-socket access). Build/run performed via operator sudo.
- Image `hb-personal-assistant:nas` was **already present** (built earlier by the operator's `n4c-backend-smoke`), so
  no rebuild was necessary for this proof.
