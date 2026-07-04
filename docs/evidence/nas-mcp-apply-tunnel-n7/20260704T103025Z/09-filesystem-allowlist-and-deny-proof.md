# 09 — Filesystem allowlist and deny proof

## Allow (MCP)

`hb_secure_list` root_key=`vault` — bounded directory names only (relative paths), truncated to 3 entries. See probe `fs_allow_vault_list` in `captured/mcp-tunnel-probe.jsonl`.

## Deny (MCP)

`hb_secure_read_excerpt` relative_path=`../etc/passwd` → `'..' traversal in include-path rejected`

## Deferred

Safe markdown excerpt not performed (no designated non-sensitive sample file). List/stat proof sufficient for WARN closeout.

No raw `/volume1/...` host paths returned in MCP responses.
