# 11 — MCP Service Supervision Design + Restart Promotion Gate

## Today
Both the MCP (`compose-mcp.yaml`) and the new connector (`compose-cloudflared.yaml`) use `restart: "no"` — deliberate, matching the repo's standing prohibition on `unless-stopped` "until a production cutover phase is authorized." The MCP container is `-d` (survives the SSH session) but has no crash recovery and no boot start.

## Always-on target (live-activation sub-phase)
1. **Restart policy** → `restart: unless-stopped` on both services (the promotion).
2. **Boot start** → a DSM Task Scheduler `@boot` triggered-task running `docker compose -f compose-mcp.yaml -f compose-cloudflared.yaml up -d` (no SSH session required).
3. **Single instance** → `container_name` (Docker refuses a duplicate) + loopback port publish. No app-level lock exists today; the container-name + port are the singleton levers.
4. **Health-driven restart** → optional compose `healthcheck` on `/health` so a wedged (not crashed) MCP is recycled.
5. **Mac-independence** → both are NAS Docker services; once the connector runs, the Mac SSH tunnel is no longer needed.

## Promotion gate (must all hold before flipping to unless-stopped)
- Lockdown proven (`29`) ✅ (done in this foundation).
- Cloudflare Access denies unauthenticated (`49`) — HOLD.
- Origin-side auth ported onto `nas_mcp:8765` (`19`) — HOLD (required before final PASS).
- Rollback proven (`56`) — HOLD.

## Full N8B PASS requirement
A full N8B PASS **cannot** be claimed until MCP + cloudflared **start after reboot** and **restart after failure** are proven live (`09`, `13`, `14` in the full evidence set).

## Verdict
Supervision design recorded; policy flip intentionally deferred. This foundation keeps the current safe posture.
