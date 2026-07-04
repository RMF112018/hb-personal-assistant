# 06 — MSAL / Graph Auth — Re-provision Plan

## Decision: RE-PROVISION on NAS (do NOT copy token caches)

## Repo-truth
- Delegated cache: `<app-support>/auth/msal-token-cache.bin` (`auth/token_cache_manager.py`); dir 0700, file 0600.
- Flow: `msal.PublicClientApplication` **device-code** by default (`auth/providers.py`), silent refresh via
  `acquire_token_silent`. ⇒ cache is **re-mintable** by an interactive device-code login; copying only avoids re-auth.
- Identity from config (non-secret): `identity.tenant_id`, `identity.client_id`, `identity.delegated_scopes`
  (`config/models.py`). No client secret for the delegated public client.
- App-only path: `msal.ConfidentialClientApplication` with a certificate whose path is **hardcoded to macOS**
  (`cli/auth.py:32`). Not used at runtime.

## Plan (executed in a later authorized phase, needs CLI/interactive login)
1. Ensure NAS config carries `identity.tenant_id` / `identity.client_id` (non-secret; add to `hb-pa-config.yml` if not default).
2. Run `hb-assistant auth login` on the NAS (device-code) → writes a fresh `msal-token-cache.bin` (0600 svc) under NAS `auth/`.
3. No secret copied; no Mac cache transferred.

## Flag (later hardening, not N4)
App-only MSAL cert path is hardcoded to a macOS location and won't resolve on NAS; the documented
`AZURE_CLIENT_CERT_PATH` env is not currently wired in code. If app-only auth is ever needed on NAS, wire that env
and provision the cert as a protected file. App-only is out of scope for runtime and for this pass.

## This pass
No login performed, no cache copied, no secret read. Plan only.
