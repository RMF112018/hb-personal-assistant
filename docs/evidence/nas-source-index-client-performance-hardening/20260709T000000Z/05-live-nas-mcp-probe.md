# Live NAS MCP probe

Date: 2026-07-09 (UTC session)

| URL | Result |
|-----|--------|
| `https://nas-mcp.bobby-fetting.me/health` | **200** `{"status":"ok","surface":"nas_mcp","nas_readonly":true,"profile":"remote_cloudflare","origin_auth_required":true}` |
| `https://nas-mcp.bobby-fetting.me/mcp` | **401** `{"detail":"unauthorized"}` |
| `https://nas-mcp.bobby-fetting.me/` | **401** unauthorized |

No `HB_MCP_ORIGIN_AUTH_*` / bearer was available in the agent environment. Authenticated tool listing against the hosted surface was therefore **not** completed.

Equivalent connected-client discovery was executed locally via FastMCP registration + broker dispatch (same path as `scripts/smoke-n8c-client-exposure.sh`): see `05-mcp-client-discovery.json.txt`.

**PR gate:** do not push/open PR until live matrix with origin auth is run, or operator accepts pending live validation.
