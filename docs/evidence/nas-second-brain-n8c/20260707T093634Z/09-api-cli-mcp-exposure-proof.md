# 09 — API / CLI / MCP Exposure

## API (read-only, GET only) — construction/analytics/api.py
`_source_connector_ctx()` factory (repo + `load_config()`) + GET routes, each `role=role_dep` + `del role`,
`Query`-bounded, `_assistant_env`-wrapped, lazy `HTTPException`:
- `GET /api/assistant/source-index/status`  (literal path; `/sources/status` would be shadowed by N8C-3
  `/sources/{source_id}` — repo-truth naming fix)
- `GET /api/assistant/source-roots`
- `GET /api/assistant/source-files/search`  ← declared BEFORE `/{source_id}` (shadowing lesson)
- `GET /api/assistant/source-files` (list)
- `GET /api/assistant/source-files/{source_id}` (metadata; 404 `source_not_found`)
- `GET /api/assistant/source-files/{source_id}/read`
No POST/PUT/PATCH/DELETE; no scan/reindex/card-generate/write route. Cursor-aware; relative paths only.

## CLI — cli/source_connector.py (group `source-connector`, registered cli/main.py)
`status`, `roots`, `search`, `list`, `metadata`, `read` — all `--json`, read-only. `read` has
`--prefer-live/--indexed`. No scan/reindex/generate/mutation command.

## MCP (read-only) — nas_mcp/{profile,broker,tool_registration}.py
- `assistant_source_connector_enabled()` reads `HB_MCP_ASSISTANT_SOURCE_CONNECTOR` (default-ON, independent
  kill switch; in `gate_status()`).
- `ASSISTANT_SOURCE_CONNECTOR_TOOLS` (6) + dispatch branch + `_invoke_assistant_source_connector` opening
  `_ro_uri(...)` + `PRAGMA query_only=ON`, threading `conn=` into the service.
- `hb_mcp_status` advertises `assistant_source_connector_enabled` + the 6 tool names.

New assistant remote tool total = **48** (42 + 6); `ai_outputs_card_upsert` remains the only remote write.

## Proof
`test_fastapi_analytics_source_connector.py` (10: GET-only, `_assert_safe`, 404, 400 bad cursor, all roles,
clamp, no write/scan route), `test_nas_mcp_source_connector.py` (8: RO snapshot + `query_only`, kill-switch
scoped, tool sets preserved BY NAME, 6-tool count, `hb_root_*` unchanged, status reports the flag/tools,
`ai_outputs_card_upsert` only write, raw obsidian source tools stay blocked).
