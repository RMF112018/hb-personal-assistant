# 04 — Launcher start status health

## Start

`sudo -n /volume1/personal-assistant/bin/hb-mcp-runner up` — container `hb-personal-assistant-mcp` created.

## NAS health (loopback)

```json
{"status":"ok","surface":"nas_mcp.readonly","nas_readonly":true,"allowlisted_table_keys":["schema_version"],...}
```

## Launcher limitation

`hb-mcp-launcher status` without docker group membership cannot run `docker ps` (permission denied). Runner/start/stop via passwordless sudo to fixed runner path works.

Captured: `captured/mac-tunnel-health.json`
