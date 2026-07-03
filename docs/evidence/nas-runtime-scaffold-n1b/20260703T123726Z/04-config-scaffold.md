# 04 — Config Scaffold (N1B)

## HB_PA_CONFIG examples (no secrets)
- `deploy/nas/hb-pa-config.nas.example.yml` (production-intent) →
  `paths.application_support_root: /volume1/personal-assistant/app-support`, `obsidian_vault:` an inert
  path under app-support (vault deferred/disabled). Nothing else — Pydantic fills defaults; no identity
  secrets, no automation/live-read toggles, no source-roots.
- `deploy/nas/hb-pa-config.smoke.example.yml` (disposable) →
  `application_support_root: /volume1/personal-assistant/app-support-smoke` (SCRATCH; distinct from live),
  inert vault under the scratch root.

### Why a `paths:` block is sufficient and safe
The loader shallow-merges top-level keys (`loader.py:34-52`), and the image excludes repo `config/config.yml`
(`.dockerignore`), so the `paths:` block from `HB_PA_CONFIG` is authoritative for paths in the container.
No secrets are needed for the backend to start and answer `/health` (against a scratch DB).

### Secrets posture
Both files carry an explicit banner: **add no secrets** (MSAL caches, tenant/client secrets, Fernet/Text-Vault
keys) until the NAS `auth`/`security` folder permissions are hardened (N1A blocker). The `.dockerignore` and the
safety checks enforce that no secret values live in the scaffold.

## .env.example (`deploy/nas/.env.example`)
- `HB_PUBLISH_ADDR=127.0.0.1` (loopback default; documented tailnet option `100.66.28.14` only after exposure is confirmed).
- Commented production paths and commented **N1C scratch overrides** (`HB_APP_SUPPORT_DIR=…/app-support-smoke`,
  `HB_CONFIG_FILE=…/hb-pa-config.smoke.yml`).
- Explicitly states `HB_PA_CONFIG` and the worker kill switch are set in compose/Dockerfile and must not be weakened.

## Config → mount contract
The compose app-support mount uses an **identical host↔container path**, so whatever
`application_support_root` the config declares (live or smoke) is exactly what is mounted — preventing a
mismatch where the app writes to a path that isn't the intended NAS-local volume.
