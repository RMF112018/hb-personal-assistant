# 04 — Exposure Surface Decision

| Item | Decision |
|---|---|
| Public hostname | `mcp.bobby-fetting.me` (operator-confirmable) |
| Origin target | internal `http://hb-personal-assistant-mcp:8765` (shared `hb-mcp-internal` bridge); loopback `127.0.0.1:8765` retained for the Mac tunnel |
| MCP route | `/mcp` |
| Health route | `/health` (protect with Access too) |
| Human access | Cloudflare Access identity login |
| Agent access | Cloudflare Access service token (per-client) + origin-side auth (required later; `19`) |
| Public exposure | **MCP only** |
| Forbidden exposure | DSM, SSH, SMB, NFS, WebDAV, raw vault, raw SQLite, Portainer, NAS admin, auth/secret folders |

## Guarantees in this foundation
- The `cloudflared` connector (`compose-cloudflared.yaml`) publishes **no ports** and dials out only; its only network peer is the MCP container on the internal bridge. It cannot reach DSM/SSH/SMB/etc. (they are not on `hb-mcp-internal`).
- The MCP surface is locked to read + AI-Outputs-write by the `remote_cloudflare` profile (`03`, `26`, `29`).
- **Access-before-route:** the route is not considered usable until Cloudflare Access denies unauthenticated traffic (`48`, `49` HOLD). A published self-hosted app without Access is internet-reachable — so Access is created and verified first.

## Not in scope
No broad private-network/LAN/CIDR route; no NAS admin or storage protocol; no second ingress.

## Verdict
Exposure is MCP-origin-only, profile-locked, and access-gated. Live route/Access = HOLD (operator Cloudflare setup).
