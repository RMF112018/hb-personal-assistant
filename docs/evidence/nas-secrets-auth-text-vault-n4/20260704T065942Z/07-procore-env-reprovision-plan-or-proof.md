# 07 — Procore / API Credential — Re-provision Plan

## Decision: RE-PROVISION on NAS (do NOT copy token cache)

## Repo-truth
- OAuth 2.0 OOB installed-app flow: `authorization_code` exchange + `refresh_token` refresh (`procore/oauth.py`).
- Token cache: `<app-support>/auth/procore_token.json` (0600) — holds access/refresh tokens (`procore/token_provider.py`).
- Client secret selector order (`procore/config.py`): (1) macOS Keychain `hb-assistant-procore/client-secret`,
  (2) env `PROCORE_CLIENT_SECRET`, (3) protected file `~/.config/hb-assistant/procore/client_secret` (0600).
  Access token similarly Keychain → env `PROCORE_ACCESS_TOKEN`.
- Live calls gated by `HB_PROCORE_LIVE=1` (off by default; `procore/live_gate.py`).

## Why re-provision (not copy)
- The client secret lives in **macOS Keychain**, which does not exist on Synology/Linux ⇒ cannot migrate transparently.
- Even if `procore_token.json` were copied, a token refresh still needs the client secret present on NAS.
- Least-privilege: avoid transplanting long-lived tokens; mint fresh on the target.

## Plan (later authorized phase; needs the secret + interactive login)
1. Provide the client secret on NAS via env `PROCORE_CLIENT_SECRET` OR protected file
   `~/.config/hb-assistant/procore/client_secret` (0600, owned by the runtime user). Never in YAML/DB/repo.
2. Set `PROCORE_CLIENT_ID` (non-secret) and, if used, `PROCORE_REFRESH_TOKEN`.
3. Run the Procore OOB login on NAS → writes fresh `procore_token.json` (0600 svc) under NAS `auth/`.
4. Keep `HB_PROCORE_LIVE` unset/`0` until live reads are intended.

## This pass
No secret read, no Keychain access, no token copied, no login. Plan only.
