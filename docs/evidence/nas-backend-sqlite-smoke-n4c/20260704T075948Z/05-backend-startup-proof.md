# 05 — Backend Startup Proof

## Image

| Field | Value |
|---|---|
| Image | `hb-personal-assistant:nas` |
| Image ID | `dfd65a0bb7b2` |
| Size | 286 MB |

## Build method

| Item | Value |
|---|---|
| Command shape | `docker build --network host -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .` |
| Context | `/volume1/personal-assistant/runtime/n4c-backend-smoke-20260704T075948Z/repo` |
| `--network host` scope | **Build-time only** — resolves PyPI/DNS for `pip install -e ".[analytics-ui]"` |
| Runtime networking | Standard bridge; **not** host-network at runtime |

Bridge DNS failed during initial `docker compose up --build`; host-network build succeeded.

## Runtime method

| Item | Value |
|---|---|
| Command | `docker compose up --no-build -d` |
| Working dir | `.../repo/deploy/nas` |
| Env | `HB_PUBLISH_ADDR=127.0.0.1`, `HB_CONFIG_FILE=/volume1/personal-assistant/config/hb-pa-config.yml`, `HB_APP_SUPPORT_DIR=/volume1/personal-assistant/app-support` |
| Container env (inherited) | `HB_PA_CONFIG=/config/hb-pa-config.yml`, `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` |
| User | `1028:100` (`personal-assistant-svc`) |

## Runtime bind proof

| Check | Result |
|---|---|
| Host publish | **127.0.0.1:8000** only |
| `0.0.0.0:8000` | **Not present** |

See [`07-port-and-exposure-proof.md`](07-port-and-exposure-proof.md) for `netstat` + `docker inspect` evidence.

## DB path (runtime)

NAS-local SQLite via config + mount:

`/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`

(config `paths.application_support_root` → `PathPolicy.get_db_path()`; container mount at identical path)
