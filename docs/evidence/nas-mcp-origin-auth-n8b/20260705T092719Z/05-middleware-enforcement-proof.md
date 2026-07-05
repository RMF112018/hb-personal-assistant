# 05 — Middleware Enforcement Proof

`OriginAuthMiddleware` gates the real wired app (`build_nas_mcp_asgi_app`) under the
default `remote_cloudflare` profile (origin auth hard-on). Proven against a real Starlette
`TestClient` — a fresh app per session (the MCP session manager runs once per instance).

## Denied (all → `401 {"detail":"unauthorized"}`, uniform, no existence leak)
| case | test |
|---|---|
| missing `Authorization` | `test_mcp_denied_without_auth` |
| malformed header (`Basic …`, empty `Bearer `) | `test_mcp_denied_bad_and_malformed_bearer` |
| unknown token | `test_mcp_denied_bad_and_malformed_bearer` |
| revoked token | `test_mcp_denied_revoked_and_expired` |
| expired token (time advanced past expiry) | `test_mcp_denied_revoked_and_expired` |

## Allowed
`test_valid_token_allowed_and_audit_attribution` — a valid bearer completes the MCP
`initialize` → `tools/call hb_mcp_status` flow with HTTP 200.

## Structured denial
The client always receives the same body/`WWW-Authenticate: Bearer realm="hb-nas-mcp"`.
The precise reason class (`origin_auth:unknown_token` / `:revoked` / `:expired` /
`:missing_authorization` / `:malformed_authorization`) is written only to the 0600 audit
(`12`), never returned — so a caller cannot distinguish "wrong token" from "no such token".

## Same-context propagation
Because the middleware is pure ASGI, the `AuthContext` it sets on success reaches the tool
coroutine and thus the broker audit (proven end-to-end in `12`). No token value is ever
logged on any path.
