# 06 — Implementation summary

## New package: `src/hb_assistant/nas_mcp/`

| Module | Purpose |
|---|---|
| `guards.py` | Env guards; blocks `create_app` import |
| `config.py` | MCP roots, limits, deny patterns |
| `audit.py` | JSONL audit writer |
| `path_safe.py` | Relative path validation (no obsidian_mcp import) |
| `redaction.py` | Token/key redaction |
| `db_allowlist.py` | Default-deny table registry + test hook |
| `db_tools.py` | `hb_db_select` structured RO queries |
| `fs_tools.py` | Root-key filesystem tools |
| `broker.py` | Deny-first dispatch + audit |
| `server.py` | Streamable HTTP ASGI + uvicorn entry |

## CLI

- `src/hb_assistant/cli/mcp_nas.py` → `hb-assistant mcp serve --nas-readonly --streamable-http`

## Deploy

- `deploy/nas/mcp/compose-mcp.yaml` — bridge + `127.0.0.1:8765:8765`
- `deploy/nas/mcp/hb-mcp-launcher`, `hb-mcp-runner`, `check-mcp-compose.sh`
- Examples: config, sudoers, client config, mac tunnel, README

## Docker image

- `deploy/nas/Dockerfile` — installs `.[analytics-ui,mcp]`

## Not implemented on NAS

Launcher/sudoers installation deferred (operator gate).
