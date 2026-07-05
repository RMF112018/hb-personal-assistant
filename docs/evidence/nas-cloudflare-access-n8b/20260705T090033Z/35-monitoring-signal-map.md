# 35 — Monitoring Signal Map

| Signal | Source | Status |
|---|---|---|
| MCP local health | `/health` (profile-aware) | EXISTS |
| MCP routed health | Cloudflare hostname `/health` behind Access | HOLD (live) |
| Tunnel status | Cloudflare dashboard/API + `cloudflared-runner status` | HOLD (live) |
| Access allow/deny events | Cloudflare Access logs | HOLD (live) |
| Service restart count | NAS Docker / logs | HOLD (needs supervision) |
| Last successful tool call | broker audit `mcp-audit-*.jsonl` (allow) | EXISTS |
| Last failed tool call | broker audit (deny) | EXISTS |
| Last AI Outputs write | `mutations.jsonl` receipt | EXISTS |
| DB read status / schema version | `hb_mcp_status` / `/health` allowlist + DB read | PARTIAL (schema via allowlisted read) |
| Disk free | NAS probe | GAP (later) |
| Queue depth / freshness timestamps | `source_index_status` (blocked on NAS today) | GAP → `43` |
| Safe mode status | profile/gate status | PARTIAL (`45` full safe-mode GAP) |
| Override status | override tool | GAP → `39` |

## Recommended alerts (later)
Tunnel down · MCP health down · routed health down · repeated Access denials · repeated tool errors · disk low · DB read failure · data stale · queue high · safe mode enabled.

## Verdict
Local audit/health/receipts EXIST and are attributable; Cloudflare-side + freshness + disk signals are HOLD/GAP for later sub-phases.
