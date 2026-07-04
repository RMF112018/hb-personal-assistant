# 08 — NAS re-apply proof or deferred

**Status:** **DEFERRED**

NAS re-apply not authorized this session. N7-APPLY left MCP stopped.

## Minimum proof (when authorized)

1. Install updated launcher/runner on NAS
2. Confirm sudoers still single runner grant
3. `hb-mcp-launcher status` as `bfetting` (no Docker group)
4. Confirm vault mount `.../vault/obsidian:/mnt/vault:ro`
5. Bounded `hb_vault_*` list/stat via tunnel — logical paths only
6. Deny traversal/absolute path
7. Audit event written
8. Stop + cleanup; DB unchanged

## Local substitute

Static compose/config/tests prove vault mapping and launcher routing without live NAS apply.
