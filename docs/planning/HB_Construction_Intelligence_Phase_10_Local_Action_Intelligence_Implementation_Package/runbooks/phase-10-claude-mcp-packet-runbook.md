# Phase 10 Claude MCP Packet Runbook

## Build packet

```bash
hb-assistant second-brain mcp packet build --packet-type daily_brief --date 2026-06-07 --json
hb-assistant second-brain mcp packet build --packet-type meeting_prep --project-key hilltop --json
```

## MCP expectations

Claude should receive source-linked context packets, not raw unrestricted content or database access.
