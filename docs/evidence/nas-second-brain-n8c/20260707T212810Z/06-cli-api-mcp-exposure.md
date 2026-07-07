# 06 — CLI / API / MCP Exposure

## CLI (`hb-assistant action-stage`) — one write gate
Commands: `preview` (RO), `build` (writer), `list`, `show`, `export` (RO). The write gate is a single
`--dry-run/--apply` flag defaulting to `--dry-run`; only `--apply` persists (into the five stage tables). No
execute/send/schedule/dispatch/remind/task command exists (`test_action_stage_cli`).

## API — read-only GET only
`construction/analytics/api.py` adds six GET routes, all-roles, wrapped in `_assistant_env(...)`
(`guardrails.read_only == true`):
`/api/assistant/action-stages`, `/summary` (before `/{stage_id}`), `/{stage_id}`, `/{stage_id}/items`,
`/{stage_id}/citations`, `/{stage_id}/export`. No POST/PUT/PATCH/DELETE, no build/apply/execute route — the
writer is CLI-only (`test_fastapi_analytics_action_stages::test_routes_are_get_only`, `::test_no_write_or_
build_route`). Missing id → 404. Limits bounded.

## MCP — six read-only remote tools
Profile `assistant_action_stages_enabled()` (env `HB_MCP_ASSISTANT_ACTION_STAGES`, default-ON) + gate_status
line. Broker `ASSISTANT_ACTION_STAGE_TOOLS`: `assistant_list_action_stages`, `assistant_get_action_stage`,
`assistant_get_action_stage_items`, `assistant_get_action_stage_citations`,
`assistant_get_action_stage_summary`, `assistant_get_action_stage_export`. Gated dispatch precedes the
`startswith("assistant_")` catch-all; `_invoke_assistant_action_stages` opens a `mode=ro&immutable=1` snapshot
with `PRAGMA query_only=ON` (no live-DB fallback) and reads the stage repository only. `tool_registration.py`
wraps the six `@mcp.tool()` defs in `if assistant_action_stages_enabled():`.

All six names clear the 23-substring finality guard. Verified read-only, kill-switch-scoped, and
finality-clean in `test_nas_mcp_action_stages`; the existing finality guard in `test_nas_mcp_workflows` also
covers them. There is NO stage-write / build / apply / execute MCP tool. `ai_outputs_card_upsert` stays the
only sanctioned remote write.
