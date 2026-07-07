# 07 — Finality + Naming Guard

## The 23-substring finality guard is preserved and covers the new tools
`_FORBIDDEN` (in `tests/test_nas_mcp_workflows.py`): extract, apply, write, create, delete, persist, upsert,
close, reopen, accept, reject, defer, dispose, build, send, remind, answer, generate, scan, reindex, rebuild.
`test_existing_finality_guard_still_passes` registers ALL assistant tools (now including the six N8C-19
action-stage tools) and asserts no registered name contains any `_FORBIDDEN` substring — green in the
regression subset.

## The six action-stage tool names are clean by construction
`assistant_list_action_stages`, `assistant_get_action_stage`, `assistant_get_action_stage_items`,
`assistant_get_action_stage_citations`, `assistant_get_action_stage_summary`,
`assistant_get_action_stage_export` — none contains a forbidden finality/execution substring
(list/get/items/citations/summary/export; `export` ≠ `extract`).
`test_nas_mcp_action_stages::test_no_write_build_or_execute_tool_registered` additionally forbids
execute/dispatch/schedule/remind/send in any assistant tool name.

## Guard not weakened
No `_FORBIDDEN` entry removed or relaxed. No new sanctioned remote write added. `ai_outputs_card_upsert`
remains the single sanctioned remote write; the stage MCP tools are strictly read-only over an RO snapshot.
