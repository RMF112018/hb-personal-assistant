# 02 — Target design

## Client path

```text
Mac MCP client → http://127.0.0.1:18765/mcp
  SSH tunnel: ssh -N -L 18765:127.0.0.1:8765 -p 10021 hb-nas
  NAS host: 127.0.0.1:8765 → hb-personal-assistant-mcp container
```

## Port separation

| Service | Host bind | Container |
|---|---|---|
| Backend/viewer (not started by N7) | `127.0.0.1:8000` | `hb-personal-assistant-backend` |
| NAS MCP (N7) | **`127.0.0.1:8765` only** | `hb-personal-assistant-mcp` |

## Docker networking (corrected)

- **Bridge** network (`hb-mcp-internal`), **not** `network_mode: none` + `ports`
- Host publish literal: `127.0.0.1:8765:8765`
- Container process bind: `0.0.0.0:8765` (reachable via Docker port map)
- Outbound prohibition: **application/tool policy**, not disabled network namespace

## Server command

```bash
hb-assistant mcp serve --nas-readonly --streamable-http --host 0.0.0.0 --port 8765
```

Standalone ASGI (`/health`, `/mcp`); does **not** import `create_app`.

## Env guards

- `HB_MCP_NAS_READONLY=1`
- `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`
- `HB_ASSISTANT_DB_READONLY=1`
- `HB_NAS_RUNTIME=1`
