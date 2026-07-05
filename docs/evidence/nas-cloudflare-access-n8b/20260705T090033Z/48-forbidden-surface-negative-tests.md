# 48 — Forbidden-Surface Negative Tests

Live probes are **HOLD** (no tunnel/Access yet). This records the test plan + the structural reasons each surface is not reachable.

| Forbidden surface | Why unreachable (foundation) | Live test (HOLD) |
|---|---|---|
| DSM / NAS admin UI | not on `hb-mcp-internal`; connector routes only to the MCP container; single dashboard ingress | request DSM host via tunnel → Access deny / 404 |
| SSH / SMB / NFS / WebDAV | not routed by the tunnel; no ingress rule | port/scheme probe via hostname → no route |
| Portainer | not routed | probe → no route |
| Raw Obsidian vault folders | MCP surface exposes only bounded read tools + AI Outputs write; no static file serving | attempt raw path fetch → tool-mediated only |
| Raw SQLite DB | DB is RO to MCP and only via allowlisted `hb_db_select`; no file download | attempt DB file fetch → denied |
| Auth/security/token/cache folders | denied dir/name patterns (`auth`,`security`,`secrets`, token/key names) | attempt read → denied |
| Arbitrary SQL | `DENIED_TOOL_NAMES` (`raw_sql`,`sql`) | call → deny |
| Arbitrary filesystem | `read_file_absolute` denied; path-safe roots only | call → deny |
| Unauthenticated MCP | Cloudflare Access denies before origin | unauth request → Access login page, not MCP JSON (`49` HOLD) |

## Acceptance (live)
Every forbidden surface denied/unrouted/unreachable; an unauthenticated request receives a Cloudflare Access denial, not MCP JSON; no raw DB/vault content downloadable.

## Verdict
Structurally sound in the foundation (profile + routing + deny lists); live negative tests = HOLD.
