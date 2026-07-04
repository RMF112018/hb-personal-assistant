# 07 — MCP health and endpoint proof

## `/health`

PASS through Mac tunnel — sanitized JSON, no secrets.

## `/mcp` (streamable HTTP)

After lifespan/mount hotfix:

| Probe | Result |
|---|---|
| `initialize` | HTTP 200, server `hb-nas-mcp-readonly` |
| `tools/list` | Lists `hb_mcp_status`, `hb_db_select`, filesystem tools |
| No backend routes on `:18765` | PASS |

Captured: `captured/mcp-tunnel-probe.jsonl`

Client endpoint: `http://127.0.0.1:18765/mcp` (not `/mcp/` mount double-path).
