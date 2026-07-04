# 05 — Runtime execution

## Operator invocation

```bash
sudo bash /volume1/personal-assistant/runtime/n4c-pr-a-backend-smoke-20260704T092127Z/n4c-pr-a-smoke-run.sh
```

(Initial agent attempt used `sh`; operator corrected to **`bash`**.)

## Script permissions

| Before | After |
|---|---|
| `777` | **`700`** (`-rwx------`) |

## Build

```bash
docker build --network host -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .
```

| Item | Value |
|---|---|
| Tag | `hb-personal-assistant:nas` |
| Image ID | `d18715bf714c` |
| Network | host (**build-time only**) |

## Runtime start

```bash
HB_PUBLISH_ADDR=127.0.0.1 \
HB_CONFIG_FILE=/volume1/personal-assistant/config/hb-pa-config.yml \
HB_APP_SUPPORT_DIR=/volume1/personal-assistant/app-support \
docker compose up --no-build -d
```

| Env (container) | Value |
|---|---|
| `HB_NAS_RUNTIME` | `1` |
| `HB_PA_CONFIG` | `/config/hb-pa-config.yml` |
| `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` | `1` |

No secrets, vault, or source-root mounts.

## Shutdown

`docker compose down` — container and `nas_default` network removed. See `10-shutdown-proof.md`.

Raw endpoint JSON: `evidence/*.json`  
Raw logs: `evidence/compose-logs-tail.txt`, `evidence/compose-down.txt`
