# 10 — Boundaries maintained

| Boundary | Status |
|---|---|
| No push | Yes |
| No PR | Yes |
| No NAS apply | Yes (deferred) |
| No backend/viewer on :8000 | Yes (MCP compose excludes it) |
| No Cloudflare/Tailscale public bind | Yes (loopback publish only) |
| No broad sudo | Yes (single runner command in example) |
| No direct personal-assistant-svc SSH | Yes (unchanged) |
| No arbitrary SQL | Yes |
| No arbitrary filesystem reads | Yes |
| No token cache / Text Vault key / auth mounts | Yes |
| No workers/ingestion | Yes (env guards) |
| No DB write/migration in MCP path | Yes (RO URI + no migrator import) |
