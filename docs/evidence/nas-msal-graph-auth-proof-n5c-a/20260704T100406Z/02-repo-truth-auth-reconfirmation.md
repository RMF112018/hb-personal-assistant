# 02 — Repo-Truth Auth Reconfirmation

Reconfirmed before login that the auth mechanism is DB-safe and backend-free.

- **Command:** `hb-assistant auth login --json` (console script `hb_assistant.cli.main:cli`).
- **Call chain:** `cli/auth.py → auth/providers.py → auth/token_cache_manager.py → config/loader.py`. Grep confirmed
  **0** store/migrator/sqlite/connection/repository imports across all four modules. `config/path_policy.py` imports
  `sqlite3` only for path helpers (opens nothing).
- **Delegated login flow (device-code default):** `initiate_device_flow → acquire_token_by_device_flow → save_cache`
  (providers.py) — writes only the delegated MSAL cache; no DB open, no backend start.
- **Config:** loaded from `HB_PA_CONFIG`; `PathPolicy` resolves `get_auth_dir()` = `application_support_root/auth`.
- **Scopes (repo allowlist / sanitizer):** the CLI passes the configured delegated scopes and strips reserved ones
  (`offline_access`) via `sanitize_delegated_scopes`.

**Conclusion:** running `auth login` opens no DB and starts no backend — consistent with N5C/N5C-R findings. The DB
mtime/size equality proof (`06`) confirms this empirically.
