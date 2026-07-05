# 16 — Transport Decision

**Decision: Streamable HTTP (already implemented) — no transport change needed.**

- `nas_mcp/server.py:38` — `FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)`; `:54` `mcp.streamable_http_app()` mounted at `/`; `/health` route (`:67`). Route path `/mcp` (confirmed by `claude-desktop-config.example.json`).
- **Why it fits Cloudflare:** Streamable HTTP means the server runs independently and remote clients connect over HTTP through the tunnel. `stateless_http=True` means dropped/reconnected tunnel connections lose no server-side MCP session state — resilient across Cloudflare reconnects.
- **Route/health:** `/mcp` (MCP), `/health` (GET, unauthenticated at origin — but only reachable through Cloudflare Access once fronted). Access should also protect `/health` per the N8B plan.
- **Timeouts / long jobs:** per-tool budget `tool_timeout_seconds=30` exists on the obsidian side (`obsidian_mcp/config.py`); the NAS surface tools are synchronous/bounded (size + row caps, `nas_mcp/config.py:64-70`). No long-running tool holds a remote connection open on this surface. Long-running work is out of the read+AI-Outputs-write scope; if added later it must return a job id (documented in `39`/`43`).
- **Idempotency on retry/reconnect:** the one write tool (`ai_outputs_card_upsert`) is SHA-gated for update and create-once for create, so a retried write does not silently duplicate/clobber (`27`, `28`).

## Verdict
Transport is Cloudflare-compatible today. Remaining transport-adjacent gaps (rate limiting, explicit reconnect/idempotency proof under a live tunnel) are HOLD until live activation.
