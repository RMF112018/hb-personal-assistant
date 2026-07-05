# 06 — Health Endpoint Policy

## Decision: minimal-public liveness + authenticated detail
The previous `/health` leaked `configured_roots` (mount **paths**), `allowlisted_table_keys`,
and full `guardrails` to **unauthenticated** callers. That is an info leak once the origin
is internet-reachable. Fixed.

### `minimal_public` (default, `HB_MCP_ORIGIN_AUTH_HEALTH_MODE=minimal_public`)
`GET /health` (no auth) returns **only**:
```json
{"status":"ok","surface":"nas_mcp","nas_readonly":true,
 "profile":"remote_cloudflare","origin_auth_required":true}
```
No DB path, no root mounts, no allowlisted table keys, no host details, no schema.
Proof: `test_health_minimal_public_hides_detail` asserts 200 + absence of
`configured_roots` / `allowlisted_table_keys` / `guardrails`.

### Detailed health
Two authenticated paths:
1. The **`hb_mcp_status` MCP tool** (already behind `/mcp`, thus behind origin auth) returns
   the full status incl. exposure profile + gate states.
2. `HB_MCP_ORIGIN_AUTH_HEALTH_MODE=protected` makes `/health` itself require a bearer and
   then return the detailed body. Proof: `test_health_protected_requires_auth` — `401`
   without a token, `200` + `configured_roots` with a valid token.

## Rationale
Liveness must stay probe-able (uptime checks, cloudflared health) without a credential,
but nothing sensitive is exposed there. Anything descriptive requires authentication.
