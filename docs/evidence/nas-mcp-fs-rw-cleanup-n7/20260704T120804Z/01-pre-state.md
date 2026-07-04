# 01 — Pre-cleanup state

**Captured:** before `hb-mcp-launcher stop`

| Item | Value |
|---|---|
| MCP container | `hb-personal-assistant-mcp` **Up** |
| DB path | `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| DB size | `4151631872` bytes |
| DB mtime (UTC) | `2026-07-04 08:55:03.807899678 +0000` |
| Port 8765 | `listen_other` (docker publish; cleared after stop) |
| Port 8000 | `absent` |
| Vault probe | `exists` |
| Outputs probe | `exists` |
| Vault top-level count | 17 |
| Outputs top-level count | 1 |

## Vault top-level entries (before)

`.obsidian`, `.smart-env`, `00 Inbox`, `90 Archive`, `99 System`, `AI Outputs`, `Attachments`, `Daily`, `Email Archive`, `Home`, `MOCs`, `README.md`, `Source Notes`, `Templates`, `Untitled.base`, `Work`, **`n7-fs-rw-probe.md`**

## Outputs top-level entries (before)

**`n7-fs-rw-probe.txt`**
