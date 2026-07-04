# 02 — Install plan and files

## Staging

`/volume1/personal-assistant/staging/n7-mcp-apply-20260704T103025Z/`

## Installed paths

| Path | Mode | Owner |
|---|---|---|
| `/volume1/personal-assistant/bin/hb-mcp-launcher` | 755 | root:root |
| `/volume1/personal-assistant/bin/hb-mcp-runner` | 750 | root:root |
| `/volume1/personal-assistant/deploy/nas/mcp/` | deployed | root-readable |
| `/volume1/personal-assistant/config/hb-pa-config.mcp.yml` | 640 | root:users |
| `/volume1/personal-assistant/app-support/audit/mcp` | 700 | personal-assistant-svc:users |

## Image rebuild

`hb-personal-assistant:nas` rebuilt on NAS with `.[analytics-ui,mcp]` (`--network=host` for pip). Required because pre-N7 image lacked `hb-assistant mcp`.

## Apply hotfix

Patched `src/hb_assistant/nas_mcp/server.py` on NAS staging during apply; committed locally as **`a9ff717e`** (`fix(nas): align MCP streamable HTTP lifespan and mount`) atop **`5dd638ff`**.

Changes: Starlette lifespan for MCP session manager; mount streamable app at `/` (client endpoint `/mcp`).
