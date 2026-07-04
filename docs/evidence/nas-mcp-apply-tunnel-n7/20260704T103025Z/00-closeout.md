# 00 — Closeout

**Phase:** N7-APPLY — NAS MCP apply + SSH tunnel proof  
**Result:** **WARN**

## Summary

Dedicated MCP service installed and validated on NAS with Mac SSH tunnel. Loopback-only bind, no backend on `:8000`, MCP protocol proof through tunnel, deny proofs, audit events, clean stop.

## WARN reasons

1. **Production DB allowlist mismatch at apply time** — MCP tool key `schema_version` was allowlisted but mapped to non-existent table `schema_version`; production uses `schema_migrations`. Bounded DB MCP proof returned `no such table` during apply. **Decision recorded:** keep tool key `schema_version`; approved narrow mapping to `schema_migrations` columns `version`, `name`, `applied_at` only (implementation + re-proof deferred).
2. Apply required hotfix `a9ff717e` (MCP lifespan + mount at `/`); applied on NAS during session; now committed locally atop `5dd638ff`.
3. Initial sudoers file was 0 bytes (install tee bug); corrected to single runner grant before closeout.
4. `hb-mcp-launcher status` cannot inspect Docker without sudo (bfetting not in docker group) — launcher patch follow-up.
5. Vault excerpt proof deferred — list/stat only (no non-sensitive sample file selected).

## Commits

| Role | SHA | Message |
|---|---|---|
| N7 implementation | `5dd638ff` | `feat(nas): add read-only MCP SSH launcher mode` |
| N7 apply hotfix | `a9ff717e` | `fix(nas): align MCP streamable HTTP lifespan and mount` |
| N7-APPLY evidence | (this package) | `docs(nas): add N7 MCP apply and tunnel proof` |

## Verdict table

| Check | Result |
|---|---|
| Launcher/runner installed | PASS |
| Sudoers single command | PASS (after correction) |
| Service-user SSH denied | PASS |
| MCP container UID 1028:100 | PASS |
| Host bind `127.0.0.1:8765` only | PASS |
| Port 8000 unused | PASS |
| Mac tunnel `127.0.0.1:18765` | PASS |
| `/health` through tunnel | PASS |
| `/mcp` through tunnel | PASS (after hotfix) |
| DB allowlist attempt | WARN (table name mismatch) |
| DB deny | PASS |
| FS allow/deny | PASS |
| Audit JSONL | PASS |
| Stop/cleanup | PASS |
| DB unchanged | PASS |

## Boundaries

No push, no PR, no backend, no Cloudflare, no broad sudo, NAS apply completed for MCP only then stopped.
