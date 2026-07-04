# 08 — Auth Re-Provision Plan (no secrets)

Decision (from N4/N4A): **re-provision on NAS**, do not copy token caches. Deferred to a later authorized phase (N5C).

## MSAL / Graph
- CLI: `hb-assistant auth login` on NAS (device-code, `auth/providers.py`), as the runtime user context.
- Scopes: `identity.delegated_scopes` (default incl. `User.Read`, `Mail.Read`, `Calendars.ReadWrite.Shared`,
  **`Files.ReadWrite.All`** → covers OneDrive/Graph file sources, `offline_access`).
- Writes ONLY: `<app-support>/auth/msal-token-cache.bin` (dir 0700, file 0600) — owner `personal-assistant-svc:users`.
- Do not copy the Mac cache. App-only cert path is hard-coded to macOS (`cli/auth.py:32`) — not runtime; wire
  `AZURE_CLIENT_CERT_PATH` separately if ever needed.

## Procore
- Client secret cannot migrate (macOS Keychain). Provide on NAS via env `PROCORE_CLIENT_SECRET` **or** protected file
  `~/.config/hb-assistant/procore/client_secret` (0600, runtime user). Also `PROCORE_CLIENT_ID`, `PROCORE_REFRESH_TOKEN`.
- Mint fresh `<app-support>/auth/procore_token.json` (0600 svc). Keep `HB_PROCORE_LIVE` unset/`0` — no live calls
  without separate authorization.

## This pass
No login, no secret read/print, no token copied. Plan only. Commands determined; execution = N5C.
