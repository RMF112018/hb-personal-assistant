# 03 — Launcher / runner fix

## `hb-mcp-runner`

Fixed verb enum: `start` | `stop` | `status` | `health` (replaces `up`/`down`).

`status` runs bounded inspection as root:

- `docker ps` filtered to `hb-personal-assistant-mcp`
- `docker port hb-personal-assistant-mcp 8765/tcp`
- loopback listener check `127.0.0.1:8765`
- port `8000` absent check

No `$2`, no `shift`, no arbitrary passthrough.

## `hb-mcp-launcher`

| Subcommand | Behavior |
|---|---|
| `start` | `sudo -n hb-mcp-runner start` → sleep → `sudo -n hb-mcp-runner status` |
| `stop` | `sudo -n hb-mcp-runner stop` |
| `status` | `sudo -n hb-mcp-runner status` |
| `health` | `curl http://127.0.0.1:8765/health` (no Docker; bfetting-local) |

Removed all direct `docker ps` / `DOCKER=` usage from launcher.

## Sudoers posture (unchanged)

```text
bfetting ALL=(root) NOPASSWD: /volume1/personal-assistant/bin/hb-mcp-runner
```

Example: `deploy/nas/mcp/sudoers.hb-pa-mcp.example`
