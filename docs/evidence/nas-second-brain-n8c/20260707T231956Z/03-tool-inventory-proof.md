# N8C-21 — MCP tool inventory proof (13 groups / 78 tools)

Registered against a fake MCP over a fresh temp DB:

```
TOTAL_TOOLS 121   ASSISTANT_TOOLS 78   (13 read-only assistant groups)
```

The 13 groups (each independently gated, default-ON kill-switch):
nav(12), context_packs(4), memory(4), decision_memory(6), review(5), intelligence(5), research_packets(6),
source_connector(6), answer_drafts(6), workflows(6), feedback(6), action_stages(6), **quality(6)**.

`tests/test_n8c_mcp_tool_inventory_final.py` asserts:
- every group's tool tuple is registered BY NAME; the assistant union == the 78 registered assistant tools;
- each group is independently gated — toggling one `HB_MCP_ASSISTANT_*` env var flips ONLY that group's
  `gate_status` key, leaving the other 12 enabled;
- `hb_mcp_status` advertises every group's `*_enabled` flag + `*_tools` list.
