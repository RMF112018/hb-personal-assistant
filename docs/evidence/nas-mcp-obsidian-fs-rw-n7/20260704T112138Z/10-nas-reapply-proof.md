# 10 — NAS re-apply proof

**Status:** **PASS** (re-apply completed 20260704T113533Z)

## Initial attempt (blocked)

1. Transferred staging tarball to NAS via SSH pipe (`/tmp/n7-fs-rw-20260704T112138Z.tar.gz`)
2. Install blocked at `sudo mkdir` / `sudo cp` — password required (`sudo -n` not available)

## Re-apply (authorized, completed)

**Run ID:** `20260704T113533Z`  
**Staging:** `/volume1/personal-assistant/staging/n7-fs-rw-reapply-20260704T113533Z/repo`

| Step | Result |
|---|---|
| Stop prior MCP container | PASS |
| Install compose/config/launcher/runner (N7-FIX + N7-FS-RW) | PASS |
| `check-mcp-compose.sh` | PASS |
| `mcp-outputs` ownership → `personal-assistant-svc:users` (775) | PASS |
| Audit dirs under `/volume1/personal-assistant/app-support/audit/mcp` | PASS |
| `docker build --network host` → `hb-personal-assistant:nas` | PASS |
| `hb-mcp-runner start` | PASS |
| `hb-mcp-runner health` | PASS |
| `hb-mcp-launcher status` (passwordless sudo) | PASS |
| Port 8000 LISTEN on host | **absent** (PASS) |
| Publish `127.0.0.1:8765` only | PASS |

## Hotfix during re-apply

Obsidian tools (`list_directory`, `create_note`, …) initially failed MCP validation (`**kwargs` schema). Fixed locally in `src/hb_assistant/nas_mcp/tool_registration.py` (explicit optional signature via `inspect.Signature`), rebuilt image on NAS, restarted MCP. **Fix is local uncommitted at time of this evidence update.**

## Functional NAS probes (loopback `127.0.0.1:8765/mcp`)

| Probe | Result |
|---|---|
| `initialize` → server `hb-nas-mcp` | PASS |
| `hb_mcp_status` → four roots configured | PASS |
| `hb_root_list` home | PASS (no `/volume1/` leak) |
| `hb_root_list` work | PASS (no `/volume1/` leak) |
| `hb_output_write_file` + `hb_output_read` | PASS (`outputs/n7-fs-rw-probe.txt`) |
| `list_directory` vault | PASS (after hotfix) |
| `create_note` vault | PASS — created `vault/n7-fs-rw-probe.md` (probe artifact) |
| `search_sources` blocked | PASS (denied) |
| home traversal deny | PASS |
| output traversal deny | PASS |

## Pre-apply vs post-apply

| Item | Before | After |
|---|---|---|
| Runner verbs | `{up\|down}` | `{start\|stop\|status\|health}` |
| Compose vault mount | `:ro` + `syn-work` | `:rw` + home/work/outputs roots |
| `mcp-outputs` | absent → operator-created | owned `personal-assistant-svc:users` |
| MCP container | stopped | running |

## Residual

- Probe note `vault/n7-fs-rw-probe.md` and `outputs/n7-fs-rw-probe.txt` left on NAS as apply artifacts (operator may delete).
- `host_listen=missing` in runner status despite `docker port` showing `127.0.0.1:8765` — Synology `netstat` quirk; health + probes confirm service reachable.
