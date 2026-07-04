# 02 — Repo-Truth Graph Command Audit

## Search for a bounded `/me` command
Audited `src/hb_assistant/cli/graph.py` and the auth layer for an existing narrow `/me` profile command.

Findings:
- The `graph` CLI has bounded probes, but they hit **mail/calendar** endpoints — `/me/mailFolders`
  (`cli/graph.py:239,251,258`) and `/me/calendarView` (`:309,329,336`). **These are prohibited by N5C-B** (no
  mail/calendar reads), so they were **not** used.
- `hb-assistant auth status` reads cache metadata (`status_info()`) but does **not** call Graph.
- **No** existing command issues a bare `/v1.0/me` profile request.

## Selected approach — inline sanitized fallback
Per the N5C-B fallback spec, a short inline Python snippet was run **inside** the container (no new production feature):
1. Loads config + `PathPolicy` and constructs the repo's `DelegatedAuthProvider` exactly as `cli/auth.py`
   `_build_providers()` does (`cfg.identity.tenant_id/client_id/delegated_scopes`).
2. `provider.get_token(["User.Read"])` → **silent** acquisition from the existing NAS cache
   (`acquire_token_silent`; `providers.py:156-170`). No device code, no re-login.
3. Calls exactly `https://graph.microsoft.com/v1.0/me` with the bearer token.
4. Prints **only** sanitized metadata (status, endpoint, HTTP code, content-type, response **key names**, a 12-char
   UPN sha256, presence booleans). Never prints the token, authorization header, or raw body.

This reuses repo-truth auth/token-cache loading and touches no DB (the auth path imports no store/migrator, confirmed
in N5C-A/N5C-R).
