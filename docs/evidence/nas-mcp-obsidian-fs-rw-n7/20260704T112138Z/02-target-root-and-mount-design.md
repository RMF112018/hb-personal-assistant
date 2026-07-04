# 02 — Target root and mount design

| Root key | Host path | Container path | Mode |
|---|---|---|---|
| vault | `/volume1/personal-assistant/vault/obsidian` | `/mnt/vault` | rw |
| home | `/volume1/homes/bfetting/Home` | `/mnt/roots/home` | ro |
| work | `/volume1/homes/bfetting/Work` | `/mnt/roots/work` | ro |
| outputs | `/volume1/homes/bfetting/mcp-outputs` | `/mnt/outputs` | rw |

Audit mount: `/volume1/personal-assistant/app-support/audit/mcp` → `/app-support/audit/mcp:rw`

DB mount: `.../db` → `/app-support/db:ro`

Obsidian backup/support (in-container only):

- `backup_dir: /app-support/audit/mcp/obsidian-backups`
- `support_dir: /app-support/audit/mcp/obsidian-support`
- env `HB_OBSIDIAN_MCP_SUPPORT_DIR=/app-support/audit/mcp/obsidian-support`

Removed legacy `syn-work` mount.
