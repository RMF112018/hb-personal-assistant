# 04 — Kill-switch proof

`assistant_workflows_enabled()` reads `HB_MCP_ASSISTANT_WORKFLOWS` via `_env_bool` and defaults ON
(`True if override is None else override`) — consistent with every N8C read-only gate (nav … answer-drafts).

Test-backed (`tests/test_nas_mcp_workflows.py`):
- `test_kill_switch_disables_only_workflows` — default ON dispatches; `=0` makes `assistant_route_workflow`
  return `ok=False, error="assistant_workflows_disabled"` while sibling `assistant_list_drafts` still works;
  the 6 tools are NOT registered when off.
- `gate_status()` and `hb_mcp_status` advertise `assistant_workflows_enabled` + the gated
  `assistant_workflow_tools` list.
