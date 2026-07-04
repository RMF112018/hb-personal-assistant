# 07 — Security deny rules

## Root policy

| Rule | Enforcement |
|---|---|
| Root-key enum only | `vault`, `home`, `work`, `outputs` in config; unknown keys denied |
| Home/Work read-only | `RootSpec.mode: read_only`; no write tools for these keys |
| Vault + outputs RW only | `assert_write()` allows `vault` (Obsidian) and `outputs` only |
| No arbitrary absolute paths | `path_safe.validate_relative_under_root` |
| No `../` traversal | Rejected in path validation |
| Symlink escape | `realpath` guard in `resolve_under_root` |
| No `.enc` blobs | `deny_if_blocked` suffix + name patterns |
| Token/cache/key paths | Denied name patterns in `NasMcpConfig` |
| No auth/security mounts | `check-mcp-compose.sh` forbids auth/text-vault |
| No Docker socket | Not mounted |
| No backend / port 8000 | Compose guard + runner status check |
| No broad sudo | Unchanged single runner sudoers example |
| No DB writes | RO SQLite + `HB_ASSISTANT_DB_READONLY=1` |
| No raw SQL | Broker deny list |
| No shell/exec tools | Broker deny list |
| Obsidian blocked tools | `NAS_OBSIDIAN_BLOCKED` map (24 tools) |
| Host path leak | Obsidian adapter JSON scan rejects `/volume1/` |

## Compose guards (`check-mcp-compose.sh`)

- Publish `127.0.0.1:8765:8765` only
- Vault `:rw`, home/work `:ro`, outputs `:rw`
- Audit `/app-support/audit/mcp:rw`, DB `/app-support/db:ro`
- No `8000`, no backend service, no auth/text-vault mounts

## Local test evidence

| Test | Deny proved |
|---|---|
| `test_filesystem_traversal_and_enc_denied` | traversal, `.enc`, absolute, token path |
| `test_symlink_escape_denied` | symlink out of vault root |
| `test_obsidian_blocked_tool_denied` | `search_sources` blocked |
| `test_home_read_and_write_denied` | output traversal write denied |
| `test_output_sandbox_writes` | bad extension denied |
| `test_vault_write_outside_vault_denied` | outputs traversal denied |

## NAS proof

Security posture on NAS host **not re-validated** this session (MCP not restarted). Compose/config artifacts ready in repo; install blocked on sudo.
