# NAS MCP (Phase N7) — dedicated loopback HTTP service

## Architecture

```text
Mac MCP client → http://127.0.0.1:18765/mcp
  via SSH tunnel → NAS 127.0.0.1:8765
  → container hb-personal-assistant-mcp (NOT backend :8000)
```

## Network posture

- Docker **bridge** network (not `network_mode: none` + `ports`)
- Host publish: **`127.0.0.1:8765:8765` only**
- Container listen: **`0.0.0.0:8765`**
- Application/tools: **no outbound network calls**

## Operator flow (deferred until authorized)

1. Install `hb-mcp-launcher` + `hb-mcp-runner` to `/volume2/personal-assistant/bin/`
2. Install compose + config under `/volume2/personal-assistant/deploy/nas/mcp/`
3. Install sudoers example (single runner command only)
4. `hb-mcp-launcher start` → verify `127.0.0.1:8765` LISTEN
5. Mac: `mac-tunnel.sh.example` then hit `http://127.0.0.1:18765/health`
6. `hb-mcp-launcher stop` when done

## Rollback

- `hb-mcp-launcher stop`
- Remove sudoers fragment
- Remove launcher/runner binaries

## Boundaries

No backend/viewer on :8000, no Cloudflare, no token/auth mounts, no arbitrary SQL/paths.
