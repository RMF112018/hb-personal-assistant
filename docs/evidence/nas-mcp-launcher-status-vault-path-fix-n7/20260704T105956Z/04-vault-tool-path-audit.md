# 04 — Vault tool path audit

## Search scope

`src/hb_assistant/nas_mcp/`, `deploy/nas/mcp/`, `tests/test_nas_mcp_readonly.py`, N7 evidence dirs.

## Approved NAS vault host path

```text
/volume1/personal-assistant/vault/obsidian
```

## Container mount (compose default)

```yaml
${HB_VAULT_MOUNT:-/volume1/personal-assistant/vault/obsidian}:/mnt/vault:ro
```

## MCP config root (in-container)

```yaml
mcp.roots.vault.mount: /mnt/vault
```

## Tool routing

| Tool family | Root key | Mount used |
|---|---|---|
| `hb_vault_*` | `vault` (hardcoded) | `/mnt/vault` |
| `hb_secure_*` | caller `root_key` | configured roots only |
| `hb_source_root_*` | default `syn-work` | `/mnt/source-roots/syn-work` |

## Findings

| Check | Result |
|---|---|
| Mac Obsidian vault path in NAS MCP code/deploy | **Not found** |
| Host `/volume1/...` in normal tool JSON responses | **Not present** (relative + `path_display` only) |
| Vault tools escape to other roots | **Denied** by root_key allowlist |
| Traversal / absolute / `.enc` / token paths | **Denied** (existing + tests) |
| Symlink escape | **Denied** (new `realpath` guard) |
| Audit JSONL on allow/deny | **Active** |

## `server.py` hotfix

MCP lifespan + `/mcp` mount fix already committed as `a9ff717e`. Not modified in N7-FIX.
