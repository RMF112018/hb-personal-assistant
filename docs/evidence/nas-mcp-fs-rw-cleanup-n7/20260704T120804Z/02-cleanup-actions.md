# 02 — Cleanup actions

| Step | Command / action | Result |
|---|---|---|
| 1 | `hb-mcp-launcher stop` | Container + network removed |
| 2 | `rm` `/volume1/homes/bfetting/mcp-outputs/n7-fs-rw-probe.txt` | PASS (bfetting) |
| 3 | `sudo rm` `/volume1/personal-assistant/vault/obsidian/n7-fs-rw-probe.md` | PASS (owned `personal-assistant-svc`; required sudo) |

No other files deleted or modified.
