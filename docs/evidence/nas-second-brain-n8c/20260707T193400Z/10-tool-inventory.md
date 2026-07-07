# 10 — Tool Inventory: Unchanged Names, Richer Context

## No new MCP tool, no rename (clarifications #3, #11, #12)
N8C-17 adds NO MCP tool and renames NONE. The six N8C-16 workflow tools are byte-identical in name and
registration; the handler improvements flow through them because they already return the full router
envelope:

    assistant_list_workflows        assistant_route_workflow        assistant_get_workflow_context
    assistant_get_workflow_artifacts  assistant_get_workflow_policy  assistant_get_workflow_summary

Proven unchanged/complete by `test_nas_mcp_workflows.py::test_workflow_tools_registered_when_enabled`
(`len == 6`), `test_tool_count_delta_is_exactly_six`, and `test_no_forbidden_substring_in_workflow_names`.

## Richer context through the same names (clarification #11)
`assistant_route_workflow` and `assistant_get_workflow_context` return non-empty `workflow_sections` for the
implemented workflows. The ONE authorized nas_mcp change — `_workflow_context_view` passing through
`workflow_sections` + `workflow_policy` (read-only SELECT) — makes the context tool surface the sections.
Proven by:
- `test_route_and_context_return_workflow_sections_for_implemented_workflows` (both tools, open_loop_triage)
- `test_daily_brief_route_carries_sections`

## CLI / API unchanged, surface the richer envelope
No new CLI command, no new API route. `tests/test_cli_workflow.py` and
`tests/test_fastapi_analytics_workflows.py` pass unchanged — they now carry the richer envelope
transparently.

## Only sanctioned remote write unchanged
`ai_outputs_card_upsert` remains the single sanctioned remote write, still denied under safe mode
(`test_nas_mcp_workflows.py::test_ai_outputs_remains_only_write`).
