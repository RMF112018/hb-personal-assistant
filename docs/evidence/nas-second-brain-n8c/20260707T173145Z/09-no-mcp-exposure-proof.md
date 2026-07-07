# 09 — No MCP exposure

N8C-15 adds **no** remote MCP tools. `nas_mcp/broker.py`, `nas_mcp/profile.py`, and
`nas_mcp/tool_registration.py` are byte-unchanged on this branch (`git diff --name-only` shows no
nas_mcp path). `tests/test_workflow_router.py::test_no_mcp_workflow_tools_added` asserts the substring
`workflow` is absent from all three nas_mcp source files. The existing assistant MCP tool inventory
(54 tools as of N8C-14) is unchanged; `ai_outputs_card_upsert` remains the only sanctioned remote
write. The N8C-12 finality guard test is untouched and still passing. Live MCP/ChatGPT workflow
consumption is deferred to N8C-16.
