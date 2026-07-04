# 05 — Launcher and sudoers design

## Scripts

| Script | Role |
|---|---|
| `deploy/nas/mcp/hb-mcp-launcher` | `start`/`stop`/`status`/`health`; verifies host `127.0.0.1:8765` LISTEN |
| `deploy/nas/mcp/hb-mcp-runner` | Fixed `docker compose -f compose-mcp.yaml up/down` |
| `deploy/nas/mcp/check-mcp-compose.sh` | Static guard: no `network_mode:none`+ports; publish literal |

## Sudoers (example)

```text
bfetting ALL=(root) NOPASSWD: /volume1/personal-assistant/bin/hb-mcp-runner
```

Single command only — no `docker *`, no shell passthrough.

## Mac tunnel

```bash
ssh -N -L 18765:127.0.0.1:8765 -p 10021 hb-nas
```

Client URL: `http://127.0.0.1:18765/mcp`
