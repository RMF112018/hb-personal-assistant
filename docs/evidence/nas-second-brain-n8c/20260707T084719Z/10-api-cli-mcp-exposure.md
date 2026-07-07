# 10 — API / CLI / MCP Exposure

## API (read-only, GET only) — construction/analytics/api.py
`_research_packet_repo()` factory + 6 GET routes, each `role=role_dep` + `del role`, `Query`-bounded,
`_assistant_env`-wrapped:
- `GET /api/assistant/research-packets`
- `GET /api/assistant/research-packets/summary`  ← declared BEFORE `/{packet_id}` (fixed route shadowing)
- `GET /api/assistant/research-packets/{packet_id}` (404 `packet_not_found`)
- `GET /api/assistant/research-packets/{packet_id}/items`
- `GET /api/assistant/research-packets/{packet_id}/citations`
- `GET /api/assistant/research-packets/{packet_id}/export`
No POST/PUT/PATCH/DELETE; no build route. Bounded, relative paths only (`_assert_safe`), no raw bodies.

## CLI — cli/research_packet.py (group `research-packet`, registered cli/main.py:36,93)
`preview`, `build --dry-run/--apply` (sole writer), `list`, `export` — all `--json`. No answer-generation /
action / reminder / bridge command.

## MCP (read-only) — nas_mcp/{profile,broker,tool_registration}.py
- `assistant_research_packets_enabled()` reads `HB_MCP_ASSISTANT_RESEARCH_PACKETS` (default-ON, independent
  kill switch; in `gate_status()`).
- `ASSISTANT_RESEARCH_PACKET_TOOLS` (6): `assistant_list_research_packets`, `assistant_get_research_packet`,
  `assistant_get_research_packet_items`, `assistant_get_research_packet_citations`,
  `assistant_get_research_packet_export`, `assistant_get_research_packet_summary`.
- Dispatch opens `_ro_uri(...)` + `PRAGMA query_only=ON`, threads `conn=`.
- **No build/apply/final-answer/action tool.**

New assistant remote tool total = **42** (36 + 6). `ai_outputs_card_upsert` remains the only remote write.

Proof: `test_fastapi_analytics_research_packets.py` (7), `test_nas_mcp_research_packets.py` (7) — GET-only +
`_assert_safe` + 404 + bounded; RO snapshot; kill switch scoped; 6-tool count; existing tool sets preserved
BY NAME (subset asserts); `ai_outputs_card_upsert` only write.
