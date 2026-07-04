# 12 — Boundaries maintained

| Boundary | Held |
|---|---|
| No backend/viewer :8000 | Yes |
| No Cloudflare/public/LAN MCP bind | Yes |
| No broad sudo | Yes (single runner) |
| No service-user SSH | Yes |
| No arbitrary SQL/FS | Yes |
| No token/auth mounts | Yes |
| No DB write/migration | Yes |
| No push/PR | Yes |
| MCP stopped after proof | Yes |

NAS apply performed for MCP install/validation only; service not left running.
