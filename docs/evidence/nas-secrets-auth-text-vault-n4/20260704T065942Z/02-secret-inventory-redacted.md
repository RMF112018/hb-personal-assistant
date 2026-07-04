# 02 — Secret / Auth Dependency Inventory (redacted)

Names, paths (as placeholders), and mechanisms only. **No secret values, no decrypted content, no full hashes.**
`<app-support>` = `/volume1/personal-assistant/app-support` on NAS (Mac source: `~/Library/Application Support/HB Personal Assistant`).

| Family | Material | Location (mechanism) | Secret? | Migration decision |
|---|---|---|---|---|
| Text Vault | Fernet key | `<app-support>/security/text-vault.key` (file, 0600) or env `HB_TEXT_VAULT_KEY` | **yes** | **COPY** (deferred to explicit auth) |
| Text Vault | ciphertext blobs | `<app-support>/security/text-vault/<ref>.enc` (files, 0600) | **yes** (encrypted bodies) | **COPY** (deferred) |
| MSAL delegated | token cache | `<app-support>/auth/msal-token-cache.bin` | **yes** | RE-PROVISION (device-code login) |
| MSAL app-only | token cache + cert | `<app-support>/auth/msal-token-cache-app.bin`; cert path hardcoded to macOS (`cli/auth.py:32`) | **yes** | DEFER (not runtime; needs `AZURE_CLIENT_CERT_PATH` wiring) |
| Procore | OAuth token cache | `<app-support>/auth/procore_token.json` (0600) | **yes** | RE-PROVISION (re-mint after secret provisioned) |
| Procore | client secret | macOS Keychain `hb-assistant-procore/client-secret` → NAS via env `PROCORE_CLIENT_SECRET` or protected file `~/.config/hb-assistant/procore/client_secret` | **yes** | RE-PROVISION (Keychain can't migrate) |
| Procore | client id / company id | config seed / `PROCORE_CLIENT_ID` (id `5280` company) | no | config/env |
| Anthropic | API key | env `HB_ANTHROPIC_API_KEY` (only when second-brain live) | **yes** | RE-PROVISION via env |
| Identity (MSAL) | tenant/client id, scopes | `identity.*` in config YAML (non-secret) | no | config |

## Required env vars (names only; secret flag)
- `HB_PA_CONFIG` (no) — config path; required on NAS.
- `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` (no) — worker kill-switch; keep exact value.
- `HB_TEXT_VAULT_KEY` (**yes**, optional) — key override; prefer key file instead.
- `PROCORE_CLIENT_ID` (no) / `PROCORE_CLIENT_SECRET` (**yes**) / `PROCORE_REFRESH_TOKEN` (**yes**) / `PROCORE_ACCESS_TOKEN` (**yes**) — only for live Procore; gated by `HB_PROCORE_LIVE=1` (off by default).
- `HB_ANTHROPIC_API_KEY` (**yes**, optional) — second-brain live only.
- Non-secret optional: `OLLAMA_HOST`, `HB_MCP_TRANSPORT`, `HB_MCP_POLICY`, forecast `HB_FORECAST_*`, second-brain `HB_SECOND_BRAIN_*`, deploy `HB_PUBLISH_ADDR`/`HB_CONFIG_FILE`/`HB_APP_SUPPORT_DIR`.

## Sensitivity note on the DB itself
The copied DB carries secret-like content beyond the vault: `procore_endpoint_raw_payloads.contains_secret_like_value`
flags 136,458 rows. This reinforces the NAS DB's `svc:users` 600 permission and the no-print rule.
