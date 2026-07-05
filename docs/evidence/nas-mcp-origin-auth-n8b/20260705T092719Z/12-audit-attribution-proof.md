# 12 — Audit Attribution Proof

The authenticated identity threads from the middleware into every broker audit event via a
`contextvars.ContextVar[AuthContext]`. Because the middleware is pure ASGI, the contextvar
set on the request reaches the tool coroutine and the broker — **verified end-to-end** by
running a real MCP `tools/call` through the wired app and reading the 0600 audit JSONL.

## Allowed event (real run, values are non-secret; token never present)
```json
{ "tool_name": "hb_mcp_status", "decision": "allow",
  "authenticated": true, "client": "claude",
  "client_label": "Claude Desktop", "actor": "bfetting",
  "auth_method": "bearer", "token_id": "<16-hex-id>",
  "nas_readonly": true, "write_attempted": false }
```
(`test_valid_token_allowed_and_audit_attribution` asserts `authenticated=true`,
`client_label="Claude Desktop"`, `actor="bfetting"`, `client="claude"`.)

## Middleware denial event (no token, reason class only)
```json
{ "surface": "origin_auth_middleware", "decision": "deny",
  "deny_reason": "origin_auth:unknown_token", "auth_method": "bearer",
  "profile": "remote_cloudflare", "path_class": "mcp", "write_attempted": false }
```

## Fields added to broker audit this phase
`authenticated`, `client`, `client_label`, `token_id`, `auth_method` — plus `actor` now
resolves to the **authenticated** actor when a bearer identity is present, else the static
config actor (e.g. `local_trusted`).

## No-leak guarantee (proven)
`test_valid_token_allowed_and_audit_attribution` asserts the raw token string appears in
**no** audit line. The store never logs raw tokens; the middleware logs a reason class, not
the credential; `token_id`/`fingerprint` are safe references, not the secret.
