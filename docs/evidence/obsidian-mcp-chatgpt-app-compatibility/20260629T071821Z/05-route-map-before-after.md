# Route Map Before / After

Relevant routes are registered before the `/mcp` mount:

- `GET /api/settings/obsidian-mcp/oauth`
- `GET /api/settings/obsidian-mcp/chatgpt`
- `POST /api/settings/obsidian-mcp/chatgpt/readiness-check`
- `GET /.well-known/oauth-authorization-server`
- `GET /.well-known/openid-configuration`
- `GET /.well-known/oauth-protected-resource`
- `GET /.well-known/oauth-protected-resource/mcp`
- `POST /oauth/register`
- `GET /oauth/authorize`
- `POST /oauth/authorize`
- `POST /oauth/token`
- `MOUNT /mcp`

