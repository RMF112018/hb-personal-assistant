# 09 — Auth Carry-Forward

## Resolved by N5C-A
- **MSAL / Graph delegated auth on NAS: RE-PROVISIONED.** Fresh device-code login (Mac cache not copied); delegated
  MSAL cache persisted at `/volume1/personal-assistant/app-support/auth/msal-token-cache.bin` (`600`,
  `personal-assistant-svc:users`), svc-readable. Effective scopes include `Files.ReadWrite.All` (covers
  OneDrive/Graph file sources) + `Mail.Read` + `Calendars.ReadWrite.Shared` + `User.Read`.

## Follow-ups / open items
- **Graph smoke** — optional live `/me` metadata proof, deferred (`07`); run only under separate authorization.
- **Scope minimization review** — the account's effective delegated scopes include write-capable
  `Calendars.ReadWrite.Shared` and `Files.ReadWrite.All`. The product is intended read-mostly; a later review should
  confirm whether the NAS runtime should request a narrower set. N5C-A did **not** change identity/scope config.
- **Cache refresh/expiry** — the delegated cache holds a refresh token (offline access); MSAL silent refresh renews
  access tokens. Re-login only needed if the refresh token is revoked/expired.
- **Docker bridge DNS** — the default bridge resolver is intermittently unreliable on this Synology; use
  `--network host` for outbound-only CLI runs (safe: `auth login` binds no ports), or fix the daemon DNS config in a
  later runtime-hardening step.
- **Procore** — still deferred (env `PROCORE_CLIENT_SECRET` / protected file; token minting to N7/N8). Not in N5C-A.

## Downstream
- **N6** (operator control tooling), **N7** (MCP-on-NAS launcher), **N8** (watchers/scheduler) can now assume a valid
  delegated MSAL cache exists on the NAS. Text Vault (N4A) + copied DB (N3) + vault mirror (N5A) + read-only `syn-work`
  ACL (N5B) remain in place. Activation of backend/MCP/watchers is **not** authorized by N5C-A.
