# 09 — API / CLI / MCP exposure proof (N8C-6)

## API — read-only GET only
Six routes added to `construction/analytics/api.py` (closures in `create_app`, `role_dep`, wrapped by
`_assistant_env` → guardrails, `limit` bounded, relative-path only, coded 404s):
- `GET /api/assistant/enrichment/review` (limit, job_type, review_tier)
- `GET /api/assistant/enrichment/review/{item_id}`
- `GET /api/assistant/context-packs` (pack_type, status, limit)
- `GET /api/assistant/context-packs/{pack_id}`
- `GET /api/assistant/context-packs/{pack_id}/items`
- `GET /api/assistant/context-packs/{pack_id}/export`

Proofs (`test_fastapi_analytics_context_packs.py`):
- `test_routes_are_get_only` — route introspection asserts each path's `methods ⊆ {GET, HEAD}`.
- `test_no_write_route_on_surface` — POST/DELETE return `{401,404,405}`.
- `test_review_and_pack_routes_ok_and_safe` — 200 + `guardrails.read_only is True` + `_assert_safe`
  (no `access_token/refresh_token/client_secret/Bearer /eyJ/BEGIN PRIVATE KEY/result_json//Users/`).
- `test_all_roles_allowed` — viewer/operator/admin all 200. `test_missing_returns_404` — coded 404s.
- Export is bounded JSON (whitelisted keys, bounded excerpts, relative paths); no build/apply route
  exists — persistence is CLI-only.

## CLI — read-only default, `--apply` the only writer
`hb-assistant context-pack` (new `cli/context_pack.py`, registered in `cli/main.py`):
- `preview` — read-only (returns a `draft` pack, persists nothing).
- `build --dry-run` (default) — read-only; `build --apply` — the ONLY writer, into context-pack tables.
- `export` / `list` — read-only.
Mirrors the N8C-5 `qwen-worker` `--dry-run/--apply` posture; JSON out via a local `_emit`.

## MCP — four read-only remote tools, gated, snapshot-served (clarification #3)
- Gate: new `assistant_context_packs_enabled()` in `nas_mcp/profile.py` — read-only, independent of
  the three write gates, default-ON, kill-switch `HB_MCP_ASSISTANT_CONTEXT_PACKS=0`.
- Tools (`nas_mcp/tool_registration.py`, gated block): `assistant_list_context_packs`,
  `assistant_get_context_pack`, `assistant_get_context_pack_items`,
  `assistant_list_enrichment_review_items`. No build/apply/write tool is registered.
- Broker (`nas_mcp/broker.py`): `ASSISTANT_CONTEXT_PACK_TOOLS` allowlist; dispatched via
  `_invoke_assistant_context_packs` over a snapshot opened `mode=ro&immutable=1` + `PRAGMA
  query_only=ON`, threaded via `conn=` (physically cannot write, no live-DB fallback).

Proofs (`test_nas_mcp_context_packs.py`):
- `test_context_pack_tools_return_data` — the 4 tools return bounded data.
- `test_snapshot_is_read_only` — a write on the snapshot raises `OperationalError`.
- `test_kill_switch` — with the env kill-switch, dispatch returns `assistant_context_packs_disabled`.
- `test_reads_are_not_writes_safe_mode` — reads survive safe mode; `ai_outputs_card_upsert` stays gated.
- `test_no_context_pack_write_tool_registered` — nav tools preserved (⊇ 12), our 4 present, and no
  registered `assistant_*` name contains build/apply/write/create/delete/persist/upsert.
- `test_status_reports_context_packs` — `hb_mcp_status` advertises the new gate + tool list.

Preserved boundaries (`test_nas_mcp_assistant_nav.py`, `test_enrichment_no_autostart.py`):
- The 12 N8C-3 `assistant_*` nav tools are unchanged and still gated by `HB_MCP_ASSISTANT_NAV`.
- `ai_outputs_card_upsert` remains the ONLY sanctioned remote write; no nas_mcp module calls an
  enrichment WRITE method (queue/claim/complete/fail/heartbeat/release).
