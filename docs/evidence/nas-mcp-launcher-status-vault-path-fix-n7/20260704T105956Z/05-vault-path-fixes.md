# 05 — Vault path fixes

## Changes applied

1. **`path_display`** added to `hb_secure_list`, `hb_secure_stat`, `hb_secure_read_excerpt` results (`vault/...` logical paths).
2. **Symlink escape guard** in `path_safe.resolve_under_root` via `os.path.realpath`.
3. **`check-mcp-compose.sh`** validates NAS obsidian vault → `/mnt/vault:ro` mapping in compose default.

## No changes required

- `compose-mcp.yaml` vault mount default already correct.
- `hb-pa-config.mcp.example.yml` already uses `vault.mount: /mnt/vault`.
- `server.py` hotfix left untouched.

## Example tool response shape

```json
{
  "root_key": "vault",
  "relative_path": "note.md",
  "path_display": "vault/note.md"
}
```
