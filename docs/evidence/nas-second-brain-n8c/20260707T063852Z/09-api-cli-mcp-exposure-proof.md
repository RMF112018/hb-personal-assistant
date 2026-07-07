# 09 — API / CLI / MCP Exposure Proof

All three surfaces are **read-only**. The sole writer is the CLI `build --apply` (local, operator-driven).
No build/apply/action route or tool is exposed over HTTP or MCP.

## CLI (`cli/intelligence.py`, group `intelligence` registered in `cli/main.py`)

| command | posture |
|---|---|
| `preview --pack-id --type [--kind csv] [--json]` | read-only |
| `build --pack-id --type [--kind csv] --dry-run \| --apply [--json]` | `--apply` is the ONLY writer; default dry-run |
| `list [--type] [--status] [--json]` | read-only |
| `export --projection-id [--included-only] [--json]` | read-only, bounded JSON |

`--kind` is a comma-separated `str` (parsed in `_kinds`) to avoid the B008 list-`typer.Option` lint.

## API (`construction/analytics/api.py`) — 5 GET routes, all `role_dep` + `_assistant_env`

```
GET /api/assistant/intelligence/projections
GET /api/assistant/intelligence/projections/{projection_id}          (404 projection_not_found)
GET /api/assistant/intelligence/projections/{projection_id}/items
GET /api/assistant/intelligence/projections/{projection_id}/export
GET /api/assistant/intelligence/summary
```
Every response is wrapped by `_assistant_env` (adds `guardrails.read_only:true`). `Query` bounds `limit`.
No POST/PUT/PATCH/DELETE and no build route.

Tests (`tests/test_fastapi_analytics_intelligence.py`, green):
- `test_routes_ok_and_safe` — 200 + `guardrails.read_only is True` + `_assert_safe` (no token/secret/
  `result_json`/`/Users/` leak).
- `test_missing_returns_404` — unknown id → 404 on projection/items/export.
- `test_all_roles_allowed` — viewer/operator/admin all 200 on summary.
- `test_routes_are_get_only` — the five route methods ⊆ {GET, HEAD}.
- `test_no_write_or_build_route` — POST/DELETE on the surface → {401, 404, 405}.
- `test_bounded_limit_is_clamped` — `?limit=100000` → `<= 200` items.

## MCP (`nas_mcp/{profile,broker,tool_registration}.py`) — 5 read tools, default-ON independent kill switch

```
assistant_list_intelligence_projections
assistant_get_intelligence_projection
assistant_get_intelligence_projection_items
assistant_get_intelligence_projection_export
assistant_get_intelligence_summary
```
- `profile.assistant_intelligence_enabled()` reads `HB_MCP_ASSISTANT_INTELLIGENCE` (default-ON), added to
  `gate_status()`; independent of the nav/context-pack/memory/decision/review gates.
- `broker._invoke_assistant_intelligence` opens a read-only snapshot (`_ro_uri(...)` `mode=ro&immutable=1`
  + `PRAGMA query_only=ON`) and threads `conn=` into the repository reads.
- `tool_registration` registers the five tools only when the gate is enabled.

Tests (`tests/test_nas_mcp_intelligence.py`, green):
- `test_snapshot_is_read_only` — UPDATE on the snapshot raises `sqlite3.OperationalError`.
- `test_kill_switch_disables_only_intelligence` — `HB_MCP_ASSISTANT_INTELLIGENCE=0` disables ONLY the
  intelligence tools (`assistant_intelligence_disabled`); review + decision tools stay enabled.
- `test_reads_are_not_writes_safe_mode` — reads OK under safe mode; `ai_outputs_card_upsert` still gated.
- `test_no_write_or_action_tool_registered` — existing tool sets preserved **BY NAME** (subset asserts on
  NAV=12, CONTEXT_PACK=4, MEMORY=4, DECISION=6, REVIEW=5, INTELLIGENCE=5); assert no registered assistant
  tool name contains extract/apply/write/create/delete/persist/upsert/close/reopen/accept/reject/defer/
  dispose/build/send/remind; `len(ASSISTANT_INTELLIGENCE_TOOLS) == 5`.
- `test_status_reports_intelligence` — `hb_mcp_status` advertises the 5 tools; `ai_outputs_card_upsert`
  is not among them.

`ai_outputs_card_upsert` remains the ONLY sanctioned remote write. New assistant remote tool total = 36
(31 prior + 5).
