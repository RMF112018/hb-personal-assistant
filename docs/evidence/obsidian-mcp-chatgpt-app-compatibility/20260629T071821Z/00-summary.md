# ChatGPT Obsidian MCP Compatibility Summary

- Branch: `codex/obsidian-mcp-chatgpt-app-compat-20260629T062304Z`
- Base commit: `5921d5b9 merge: project schedule workbench and executive narrative`
- Connector URL: `https://mcp.bobby-fetting.me/mcp`
- Implemented: `/mcp` `WWW-Authenticate` discovery challenge, DCR `POST /oauth/register`, shared OAuth client metadata model, resource-bound authorization codes/tokens, ChatGPT Settings status/readiness surfaces, and core tool annotations/security metadata.
- CIMD: disabled and unadvertised.
- ChatGPT manual setup: not completed because the public domain still serves the pre-change runtime until this branch is deployed/restarted behind the tunnel.
- Public runtime drift: `https://mcp.bobby-fetting.me/.well-known/oauth-authorization-server` did not advertise `registration_endpoint` during validation.

