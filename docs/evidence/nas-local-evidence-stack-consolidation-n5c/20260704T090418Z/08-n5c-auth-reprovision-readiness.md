# 08 — Auth Re-Provision Readiness (planning; NO auth writes performed)

Repo-truth-grounded plan for re-provisioning delegated Graph (MSAL) + Procore auth on the NAS. **Nothing executed.**

## MSAL / Graph
- **Command (repo truth):** `hb-assistant auth login` — `cli/auth.py:43` `@app.command("login")`. **Device-code is the
  default** (`use_device_code = not no_device_code`; `--no-device-code` forces browser). `--json` output is "always
  safe, never contains tokens". `auth status` / `auth logout` / `auth clear-cache` also exist.
- **Cache target:** `<app-support>/auth/msal-token-cache.bin` (delegated) — `token_cache_manager.py:4`; app-only cache
  is `msal-token-cache-app.bin` (cert/proof only, not needed). `PathPolicy.get_auth_dir()` = `<app-support>/auth`,
  created `0700` (`path_policy.py:69-70,203`).
- **Expected owner/mode:** `personal-assistant-svc:users`; cache file `600`, `auth/` dir `700`.
- **Scopes (repo truth):** delegated allowlist `user.read, mail.read, calendars.read, files.read.all`
  (`scope_policy.py:EXPECTED_GRAPH_SCOPES`) + reserved `offline_access`. `files.read.all` covers OneDrive/Graph file
  sources (`hb-onedrive`). Runtime requests are minimized (mailbox is read-only).
- **DB-safety (verified):** `cli/auth.py` imports only `auth.providers`, `config.loader.load_config`,
  `config.path_policy.PathPolicy` — **no `store`/`migrator`/DB import**. `login` writes only the MSAL cache under
  `auth/`. → running login **does not open the DB** and does not trigger `SQLiteMigrator.apply()`.

### Questions answered
- **Run as svc via bfetting sudo?** Yes — so the cache is owned `personal-assistant-svc:users` from the start (as with
  N4A key/blob ownership). Alternatively run interactively and `chown` after.
- **Does device-code work over non-interactive SSH?** Yes — device-code prints a URL + short code to stdout; the
  operator completes sign-in in any browser. No local browser on the NAS is required. (An interactive `-tt` SSH
  session is used so the code is visible and the process waits.)
- **Writes only under NAS app-support?** Yes — only `<app-support>/auth/msal-token-cache.bin` (+ dir perms).
- **Needs production config placement first?** No — it can run with an explicit `HB_PA_CONFIG` pointing at a bounded
  config whose `application_support_root` is the intended NAS app-support (or a scratch root for a dry proof). Do
  **not** activate production config to run login.
- **DB write risk?** None (import analysis above). Safe to run.

## Procore
- **Do not copy the macOS Keychain secret** — Keychain does not exist on the Synology/Linux host.
- **Secret sources (repo truth, precedence — `procore/config.py:7-9`):** (1) macOS Keychain via `security` [N/A on
  NAS] → (2) env `PROCORE_CLIENT_SECRET` → (3) protected file `~/.config/hb-assistant/procore/client_secret` (`0600`,
  owner-only). On the NAS use **(2) or (3)**.
- **Presence-check tool (repo truth):** `procore/auth.py` inspects the **presence** of `PROCORE_CLIENT_ID`,
  `PROCORE_CLIENT_SECRET`, `PROCORE_REFRESH_TOKEN` (env) — it "never reads their values". Also honors
  `PROCORE_ACCESS_TOKEN`. `HB_PROCORE_LIVE` gates live calls and stays **off**.
- **Token file target:** `<app-support>/auth/procore_token.json` (`AUTH_TOKEN_FILE_NAME = "procore_token.json"`),
  owner `personal-assistant-svc:users`, `600`.

### Questions answered
- **CLI that mints a token without live endpoint calls?** The presence/status check runs with no live call; full token
  minting requires the OAuth exchange (a network call) and should stay behind `HB_PROCORE_LIVE`/explicit auth.
- **Limit proof to config/env presence + cache-write mechanism?** Yes — a presence-only proof (env/protected-file
  detected, no values read, no live call) is the safe bounded proof.
- **Defer token minting to N7/N8?** Recommended — Procore live tokens are not needed for N6 operator tooling.
- **Required before N6?** No.

## Recommendation
- **MSAL/Graph:** **READY** for a bounded, separately-authorized device-code proof (cache-creation + metadata only, no
  token values printed, no backend/MCP/DB). This is the higher-value re-provision (unblocks Graph/OneDrive sources).
- **Procore:** **DEFER token minting**; an optional presence-only mechanism proof can accompany the MSAL proof. Full
  re-provision fits N7/N8.
- **No auth writes in N5C.** Await explicit authorization before any login/token write.
