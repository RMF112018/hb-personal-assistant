# 51 — Logging & Audit Map

| Log | Source | Status |
|---|---|---|
| Cloudflare Access auth logs | Cloudflare | HOLD (live) |
| Cloudflare tunnel status/logs | Cloudflare + `cloudflared-runner logs` | HOLD (live) |
| MCP request/tool-call audit | `nas_mcp/audit.py` → `mcp-audit-YYYYMMDD.jsonl` (`0600`) | EXISTS |
| MCP denial audit | same (decision=deny, deny_reason) | EXISTS |
| AI Outputs mutation receipts | `obsidian_mcp/mutations.py` → `mutations.jsonl` (`0600`) | EXISTS |
| Read/crawl receipts | `traversals.jsonl` (counts/scope, no bodies) | EXISTS |
| Service restart logs | NAS Docker | HOLD (supervision) |
| Safe mode / override events | safe-mode / override tools | GAP (`45`,`39`) |

## Attribution
Broker audit captures `request_id`, `tool_name`, `actor`, `decision`, `deny_reason`, `duration_ms`, `access_mode`, `write_attempted/allowed`, `rows/bytes`, `redaction_applied`, `sha256_prefix`. AI Outputs receipts capture `source_client` (client attribution), old/new SHA, backup path. So **tool calls are attributable and writes are receipted** today; Cloudflare Access identity → `source_client` mapping is wired at the auth sub-phase.

## Verdict
Origin-side audit + receipts + redaction EXIST and are attributable; Cloudflare-side logs + restart/override/safe-mode events are HOLD/GAP.
