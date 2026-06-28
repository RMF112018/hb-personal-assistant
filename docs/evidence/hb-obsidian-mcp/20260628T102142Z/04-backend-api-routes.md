# Backend API Routes

All routes are managed by the existing FastAPI analytics backend.

- `POST /mcp` and related official SDK Streamable HTTP session traffic
- `GET /api/settings/obsidian-mcp/config`
- `PATCH /api/settings/obsidian-mcp/config`
- `GET /api/settings/obsidian-mcp/status`
- `POST /api/settings/obsidian-mcp/health-check`
- `GET /api/settings/obsidian-mcp/tools`
- `POST /api/settings/obsidian-mcp/enable`
- `POST /api/settings/obsidian-mcp/disable`
- `POST /api/settings/obsidian-mcp/restart`
- `POST /api/settings/obsidian-mcp/test/list-directory`
- `POST /api/settings/obsidian-mcp/test/search`
- `POST /api/settings/obsidian-mcp/test/read-file`
- `GET /api/settings/obsidian-mcp/grok-config`

Viewer access is allowed for read-only status/config/tool/Grok surfaces. Operator access is required for config changes, lifecycle controls, and test tool calls.
