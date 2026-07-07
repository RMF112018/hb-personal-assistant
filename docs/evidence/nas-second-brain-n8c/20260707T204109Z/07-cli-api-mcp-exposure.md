# 07 — CLI / API / MCP Exposure

## CLI (`hb-assistant feedback`) — one write gate
Commands: `add` (writer), `list`, `show`, `recommendations`, `export`. The write gate is a single
`--dry-run/--apply` flag defaulting to `--dry-run`, so a plan is always previewed before the sanctioned
local write; only `--apply` persists (into the five feedback tables). No accept/reject/defer/dispose/execute/
send/schedule/stage/remind command exists (`test_feedback_cli.py`).

## API — read-only GET only
`construction/analytics/api.py` adds six GET routes, all-roles, wrapped in `_assistant_env(...)`
(`guardrails.read_only == true`):
- `GET /api/assistant/feedback`
- `GET /api/assistant/feedback/summary`  *(declared before `/{feedback_id}`)*
- `GET /api/assistant/feedback/recommendations`  *(declared before `/{feedback_id}`)*
- `GET /api/assistant/feedback/{feedback_id}`
- `GET /api/assistant/feedback/{feedback_id}/targets`
- `GET /api/assistant/feedback/{feedback_id}/export`

No POST/PUT/PATCH/DELETE, no write/disposition route — the writer is CLI-only, mirroring the answer-draft
build surface (`test_fastapi_analytics_feedback.py::test_routes_are_get_only`,
`::test_no_write_or_disposition_route`). Missing id → 404. Limits bounded/clamped.

## MCP — six read-only remote tools
Profile `assistant_feedback_enabled()` (env `HB_MCP_ASSISTANT_FEEDBACK`, default-ON) + gate_status line.
Broker `ASSISTANT_FEEDBACK_TOOLS`:
`assistant_list_feedback`, `assistant_get_feedback`, `assistant_get_feedback_targets`,
`assistant_get_feedback_recommendations`, `assistant_get_feedback_summary`, `assistant_get_feedback_export`.
Gated dispatch branch precedes the `startswith("assistant_")` catch-all; `_invoke_assistant_feedback` opens a
`mode=ro&immutable=1` snapshot with `PRAGMA query_only=ON` (no live-DB fallback) and reads the feedback
repository only. `tool_registration.py` wraps the six `@mcp.tool()` defs in `if assistant_feedback_enabled():`.

All six names clear the 23-substring finality guard (`export` ≠ `extract`; feedback/recommendations/targets/
summary/list/get are all safe). Verified read-only, kill-switch-scoped, and finality-clean in
`test_nas_mcp_feedback.py`; the existing finality guard in `test_nas_mcp_workflows.py` also covers them.
There is NO feedback-write / capture / accept / stage MCP tool. `ai_outputs_card_upsert` stays the only
sanctioned remote write.
