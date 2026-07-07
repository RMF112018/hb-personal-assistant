# 09 — API / CLI / MCP exposure

## API (read-only, GET only) — `construction/analytics/api.py`
- `GET /api/assistant/review/items` (bounded `limit`, filters: target_kind/review_type/review_state/
  effective_state/include_superseded)
- `GET /api/assistant/review/items/{review_item_id}` (404 `review_item_not_found`)
- `GET /api/assistant/review/items/{review_item_id}/dispositions`
- `GET /api/assistant/review/effective-state/{target_kind}/{target_id}`
- `GET /api/assistant/review/summary`

All wrapped in `_assistant_env` (guardrails `read_only: true`), role-gated (all roles read; `del role`),
relative-paths only, bounded. NO POST/PUT/PATCH/DELETE; NO disposition write route. Proof
`tests/test_fastapi_analytics_review.py` (`test_routes_are_get_only`, `test_no_write_or_disposition_route`,
`_assert_safe` forbids tokens/`/Users/`/`result_json`, `test_bounded_limit_is_clamped`).

## CLI (local) — `hb-assistant review` (`cli/review.py`, wired in `cli/main.py`)
- `preview --pack-id [--kind a,b] [--limit]` — read-only.
- `build --pack-id [--kind] --dry-run/--apply` — `--dry-run` (default) read-only; `--apply` writes only
  `assistant_review_items`.
- `list [--state --type --effective-state --include-superseded --limit]` — read-only.
- `effective-state --item-id` — read-only.
- `export [--state --type --limit]` — read-only bounded JSON.
- `disposition --item-id --accept|--reject|--defer|--not-required|--request-context --reason
  [--operator-id] --dry-run/--apply` — `--dry-run` read-only; `--apply` appends only to the review
  ledger + events. No action-execution / reminder / scheduler / N8D command.

## MCP (read-only) — `nas_mcp/{profile,broker,tool_registration}.py`
5 tools: `assistant_list_review_items`, `assistant_get_review_item`,
`assistant_get_review_dispositions`, `assistant_get_effective_review_state`,
`assistant_get_review_summary`. Served over the read-only snapshot (`_ro_uri` = `mode=ro&immutable=1` +
`PRAGMA query_only=ON`, threaded `conn=`). Kill switch `HB_MCP_ASSISTANT_REVIEW=0` (default-ON,
independent of write gates). NO build/apply/disposition/action MCP tool. Assistant tool total = 31
(nav 12 + context-pack 4 + memory 4 + decision-memory 6 + review 5). `ai_outputs_card_upsert` remains the
only sanctioned remote write. Proof `tests/test_nas_mcp_review.py` (RO snapshot, scoped kill switch,
`test_no_write_or_action_tool_registered` with `len(ASSISTANT_REVIEW_TOOLS)==5`, existing tools preserved,
`hb_mcp_status` advertises the flag + tool set).
