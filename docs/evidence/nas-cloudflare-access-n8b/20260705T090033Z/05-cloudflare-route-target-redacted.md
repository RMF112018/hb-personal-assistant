# 05 — Cloudflare Route Target (redacted)

**Tunnel ingress (set in the Cloudflare dashboard for a token/remotely-managed tunnel):**

| Public hostname | Path | Service (private origin) |
|---|---|---|
| `mcp.bobby-fetting.me` | `/` (covers `/mcp`, `/health`) | `http://hb-personal-assistant-mcp:8765` |
| (catch-all) | `*` | `http_status:404` |

- The connector reaches the origin over the shared internal bridge `hb-mcp-internal` by **container name** — not over the host or any LAN address.
- **Exactly one** ingress rule to the MCP origin, plus a 404 catch-all. No rule targets DSM/SSH/SMB/NFS/WebDAV/raw vault/raw DB/Portainer/NAS admin.
- The tunnel **token** is a secret — see `07`. It is never in this evidence.
- Redaction: tunnel id / account id / connector id and the tailnet IP are **not** recorded here; if captured live they go to `local-sensitive/` and are referenced by hash only.

## Access-before-route (hard gate)
This route is **not live/usable** until the Cloudflare Access self-hosted app for `mcp.bobby-fetting.me` denies unauthenticated traffic (`20`, `49` HOLD). Operator creates + verifies Access before enabling the DNS/route.

## Status
Design recorded. Live tunnel/route creation = **operator step / HOLD**.
