# 03 — Origin Auth Design

## Goal
`nas_mcp:8765` rejects unauthenticated MCP even if Cloudflare Access is misconfigured,
bypassed, or disabled. Origin auth is **additional** to edge Access — never a replacement,
and never "trust all requests from cloudflared."

## Placement
`build_nas_mcp_asgi_app()` composes `Starlette([Route('/health'), Mount('/', mcp_app)])`
and then wraps the whole thing:

```
return OriginAuthMiddleware(app, config=cfg)
```

`OriginAuthMiddleware` is **pure ASGI** (`async __call__(scope, receive, send)`), so:
- non-`http` scopes (lifespan) pass straight through — MCP session lifespan is unaffected;
- it can emit a raw `401` before the request ever reaches MCP processing;
- a `contextvars.ContextVar` set here **propagates into the tool coroutine** (verified end-to-end, `12`), which `BaseHTTPMiddleware` would not guarantee.

## Per-request decision (in order)
1. non-http scope → pass through.
2. path `/health` and `HB_MCP_ORIGIN_AUTH_HEALTH_MODE != protected` → pass through (minimal-public liveness, `06`).
3. `origin_auth_required()` is false (only possible in `local_trusted`) → pass through.
4. else require `Authorization: Bearer <token>`:
   - extract via latin1-decoded headers; classify missing / malformed;
   - `store.validate(raw)` → `AuthContext` or a reason class (`unknown_token`/`revoked`/`expired`);
   - **fail →** audit the reason class (no token) + uniform `401 {"detail":"unauthorized"}`;
   - **pass →** set the request `AuthContext` contextvar, delegate to the app, reset in `finally`.

## `origin_auth_required()` policy (in `profile.py`)
- `remote_cloudflare` → **True, hard-on, no env override** (mirrors the write-gate lockdown; a stray flag can never expose an unauthenticated internet-facing MCP).
- `local_trusted` → default **False**, opt-in via `HB_MCP_ORIGIN_AUTH_REQUIRED=1`.

## Config / env seams
- `HB_MCP_PROFILE` (existing) selects the profile.
- `HB_MCP_ORIGIN_AUTH_REQUIRED` (local_trusted only).
- `HB_MCP_ORIGIN_AUTH_HEALTH_MODE=minimal_public|protected`.
- `HB_MCP_ORIGIN_AUTH_TOKEN_STORE` (path) or `mcp.origin_auth_store_path`, else default `<app_support>/origin-auth/tokens.json`.

## Non-goals this phase (documented HOLD)
Full OAuth 2.1/PKCE flow, live Cloudflare Access wiring, service-token dual-header bridge — see `10`.
