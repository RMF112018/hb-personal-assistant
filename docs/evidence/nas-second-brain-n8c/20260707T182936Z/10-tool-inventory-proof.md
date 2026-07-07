# 10 — Tool inventory before/after (delta proof)

Measured by registering against a fake MCP (`register_nas_mcp_tools`):

- **Before N8C-16 (workflows off):** assistant tools = 54.
- **After N8C-16 (workflows on):** assistant tools = 60.
- **Delta:** exactly the six `ASSISTANT_WORKFLOW_TOOLS`, proven by set difference
  (`test_tool_count_delta_is_exactly_six`: `set(on) - set(off) == set(ASSISTANT_WORKFLOW_TOOLS)`), not a
  brittle absolute count — no test hard-codes a total, so a future repo change elsewhere won't false-fail.
- All prior tool tuples remain present by name (subset asserts).
- `ai_outputs_card_upsert` remains the ONLY sanctioned remote write; `test_ai_outputs_remains_only_write`
  confirms workflow reads work under safe mode while the write is denied (`safe_mode_active`).
