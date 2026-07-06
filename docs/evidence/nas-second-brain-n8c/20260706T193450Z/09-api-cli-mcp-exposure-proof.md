# N8C-7 — API / CLI / MCP exposure (all read-only; one CLI writer)

## API — 5 read-only GET routes (`construction/analytics/api.py`)
All thin `_assistant_env(...)` delegators (guardrails envelope, `read_only: true`), bounded `limit`
(repository hard cap 200), relative-path only, coded 404s. No POST/PUT/PATCH/DELETE on the surface.

| Route | Returns |
|---|---|
| `GET /api/assistant/memory/nodes` | bounded node list + `count` |
| `GET /api/assistant/memory/search?q=` | normalized-name search + `count` |
| `GET /api/assistant/memory/nodes/{node_id}` | one node (404 `memory_node_not_found`) |
| `GET /api/assistant/memory/nodes/{node_id}/mentions` | bounded mentions + `count` |
| `GET /api/assistant/memory/nodes/{node_id}/compilations` | bounded compilations + `count` |

Proof: `test_fastapi_analytics_memory.py` — routes 200 + `read_only` + no secret/`result_json`/abs-path
leak (`_assert_safe`); GET-only route introspection (`route.methods <= {"GET","HEAD"}`); all roles
(viewer/operator/admin) allowed; missing node → 404; POST/DELETE → 401/404/405; `limit=100000` clamped.

## CLI — `hb-assistant memory` (read-only default; `compile --apply` the sole writer)
- `preview` — discover + compile a pack WITHOUT persisting (read-only).
- `compile --pack-id <id>` — **`--pack-id` is required** (pack-scoped; no global compile-all default);
  `--dry-run` (default) persists nothing, `--apply` writes **memory-owned tables only**.
- `export` — bounded JSON export of a persisted node (read-only).
- `list` — read-only node list.

Proof (CLI `--help`): `compile` shows `*  --pack-id ... [required]` and `--dry-run --apply
[default: dry-run]`. Smoke run on a temp migrated DB: dry-run left every non-memory table row-count
unchanged; `--apply` wrote 4 nodes / 4 mentions / 4 compilations and left claims/enrichment/
context-pack/source tables byte-for-byte unchanged (see `10-no-raw-no-writeback-proof.md`).

## MCP — 4 read-only remote tools (mirror the N8C-6 context-pack wiring)
`assistant_list_memory_nodes`, `assistant_get_memory_node`, `assistant_get_memory_mentions`,
`assistant_get_memory_compilations`.

- **Gated** by default-ON `assistant_memory_enabled()` (`nas_mcp/profile.py`); kill-switch
  `HB_MCP_ASSISTANT_MEMORY=0` → dispatch returns `ok:false error:"assistant_memory_disabled"`. Gate is
  independent of the write gates.
- **Read-only snapshot**: `broker._invoke_assistant_memory` opens `mode=ro&immutable=1` (`_ro_uri`) +
  `PRAGMA query_only=ON`, threads that `conn=` into `MemoryRepository`. Physically cannot write; no
  live-DB fallback. No compile/apply path is reachable remotely.
- **Surface preserved**: 12 N8C-3 nav tools + 4 N8C-6 context-pack tools + 4 N8C-7 memory tools = 20
  `assistant_*` tools. No build/apply/write/compile/persist/upsert tool added.
  `ai_outputs_card_upsert` remains the ONLY sanctioned remote write; it stays gated by safe mode.
- `hb_mcp_status` advertises `assistant_memory_enabled: true` + `assistant_memory_tools`.

Proof: `test_nas_mcp_memory.py` — tools return data from the snapshot; missing node → clean
`memory_node_not_found`; snapshot rejects `UPDATE` with `OperationalError`; kill-switch flips off;
reads survive safe mode while `ai_outputs_card_upsert` stays gated; no write/compile tool registered;
status advertises the 4 memory tools.
