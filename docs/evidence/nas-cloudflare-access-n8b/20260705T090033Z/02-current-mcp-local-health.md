# 02 — Current MCP Local Health (contract)

The NAS MCP is SSH-launched on demand (`hb-mcp-launcher`), not persistently running, so this foundation records the **health contract** rather than a live probe. A live check is an operator step (`hb-mcp-launcher health` → `curl http://127.0.0.1:8765/health`) done at the live-activation sub-phase or on request.

## Health route (`nas_mcp/server.py:41-50`)
`GET /health` returns:
```json
{
  "status": "ok",
  "surface": "nas_mcp",
  "nas_readonly": true,
  "allowlisted_table_keys": ["schema_version", ...],
  "configured_roots": {"vault": "read_write", "home": "read_only", ...},
  "guardrails": { ... "exposure_profile": { ... } }
}
```

## New in N8B — profile surfaced on `/health`
`guardrails.exposure_profile` (via `guards.build_guard_status()` → `profile.gate_status()`) now reports the active exposure posture. Verified locally under `HB_MCP_PROFILE=remote_cloudflare`:
```json
{
  "profile": "remote_cloudflare",
  "ai_outputs_write_enabled": true,
  "local_scratch_output_write_enabled": false,
  "legacy_broad_vault_write_enabled": false
}
```
So any health probe (local or Cloudflare-routed) shows at a glance whether the surface is locked to read + AI-Outputs-write only.

## MCP status tool (`hb_mcp_status`)
Returns the same `exposure_profile` block plus `obsidian_tools_enabled`, `obsidian_tools_blocked`, and `blocked_write_tools` (the profile-blocked write tools). See `03`.

## Verdict
Health/status contract is defined and profile-aware. Live health probe: **operator step / HOLD** (service not persistently running yet).
