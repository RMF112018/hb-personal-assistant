# N8C-8 — API / CLI / MCP exposure (all read-only; one CLI writer)

## API — 6 read-only GET routes (`construction/analytics/api.py`)
Thin `_assistant_env(...)` delegators (guardrails envelope, `read_only: true`), bounded `limit`
(repository hard cap 200), relative-path only, coded 404s. No write route on the surface.

| Route | Returns |
|---|---|
| `GET /api/assistant/decisions` (`?decision_type&status&limit`) | bounded list + `count` |
| `GET /api/assistant/decisions/{decision_id}` | one decision (404 `decision_not_found`) |
| `GET /api/assistant/preferences` (`?preference_type&status&limit`) | bounded list + `count` |
| `GET /api/assistant/preferences/{preference_id}` | one preference (404 `preference_not_found`) |
| `GET /api/assistant/open-loops` (`?open_loop_type&status&limit`) | bounded list + `count` |
| `GET /api/assistant/open-loops/{open_loop_id}` | one open loop (404 `open_loop_not_found`) |

Proof (`test_fastapi_analytics_decision_memory.py`): routes 200 + `read_only` + no secret/`result_json`/
abs-path leak (`_assert_safe`); GET-only route introspection; all roles (viewer/operator/admin); 404s;
POST/DELETE → 401/404/405; `limit=100000` clamped ≤200.

## CLI — `hb-assistant decision-memory` (read-only default; `extract --apply` the sole writer)
- `preview --pack-id` — discover + build records WITHOUT persisting (read-only).
- `extract --pack-id` — **`--pack-id` required**; `--dry-run` (default) persists nothing, `--apply`
  writes N8C-8-owned tables only.
- `export --kind decisions|preferences|open-loops` — bounded JSON (read-only).
- `list --kind …` — read-only list.

Proof (CLI smoke on a temp migrated DB): preview + `extract --dry-run` left every non-N8C-8 table
unchanged; `extract --apply` wrote records and left claim/enrichment/context-pack/memory tables
unchanged; `export` had no absolute-path leak. No action-execution / reminder / scheduler command exists.

## MCP — 6 read-only remote tools (mirror N8C-6/7 wiring)
`assistant_list_decisions`, `assistant_get_decision`, `assistant_list_preferences`,
`assistant_get_preference`, `assistant_list_open_loops`, `assistant_get_open_loop`.

- **Gated** by default-ON `assistant_decision_memory_enabled()` (`nas_mcp/profile.py`); kill-switch
  `HB_MCP_ASSISTANT_DECISION_MEMORY=0` → `ok:false error:"assistant_decision_memory_disabled"`.
  Independent of the write gates.
- **Read-only snapshot:** `broker._invoke_assistant_decision_memory` opens `mode=ro&immutable=1`
  (`_ro_uri`) + `PRAGMA query_only=ON`, threads that `conn=` into `DecisionMemoryRepository`. Physically
  cannot write; no live-DB fallback. No extract/apply path is reachable remotely.
- **Surface preserved:** 12 nav + 4 context-pack + 4 memory + 6 decision = 26 `assistant_*` tools. No
  extract/apply/write/close/reopen/accept/reject/action tool added. `ai_outputs_card_upsert` remains the
  ONLY sanctioned remote write; it stays gated by safe mode.
- `hb_mcp_status` advertises `assistant_decision_memory_enabled: true` + `assistant_decision_memory_tools`.

Proof (`test_nas_mcp_decision_memory.py`): tools return snapshot data; missing → clean
`*_not_found`; snapshot rejects `UPDATE` with `OperationalError`; kill-switch flips off; reads survive
safe mode while `ai_outputs_card_upsert` stays gated; no write/action tool registered; status advertises
the 6 tools.
