# 03 — Config verification

Host config: `/volume1/personal-assistant/config/hb-pa-config.yml`

```
application_support_root: /volume1/personal-assistant/app-support
```

Implied DB path: `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`

## Compose runtime env (staged `deploy/nas/compose.yaml`)

| Variable | Value |
|---|---|
| `HB_PA_CONFIG` | `/config/hb-pa-config.yml` (container) |
| `HB_NAS_RUNTIME` | `"1"` |
| `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS` | `"1"` |
| `HB_PUBLISH_ADDR` (smoke script) | `127.0.0.1` |

## Static safety check

Not re-run on NAS (requires staged repo shell access only). Staged repo includes updated `check-runtime-safety.sh` with `HB_NAS_RUNTIME` assertion.
