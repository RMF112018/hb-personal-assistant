# 09 — MCP Tool Surface & Safety Proof (remote)

MCP-side safety, kept **separate** from the API proof (clarification #4). Source:
`tests/test_nas_mcp_assistant_nav.py` (12 tests, all pass), plus a live broker smoke.

The `assistant_*` tools serve navigation **plus bounded deep content** by intentional operator decision
(see `02`). "Deep content" changes only what authenticated reads return — every structural safeguard
below is retained; the tools are read-only, snapshot-backed, and bounded.

## Surface
12 static `@mcp.tool()` `assistant_*` wrappers registered in `nas_mcp/tool_registration.py`, gated by
`assistant_nav_enabled()` (default ON). Each forwards to `broker.dispatch(...)` → broker `_invoke`
`assistant_` branch → `_invoke_assistant`. Registration proofs:
- `test_registration_adds_12_assistant_tools_when_enabled` — exactly the 12 `ASSISTANT_NAV_TOOLS`
  register; existing `hb_data_freshness` / `ai_outputs_card_upsert` still present (not renamed/removed).
- `test_registration_omits_assistant_tools_when_disabled` — with `HB_MCP_ASSISTANT_NAV=0`, zero
  assistant tools register; unrelated tools unaffected.
- `test_obsidian_tool_count_unchanged` — `list_nas_obsidian_tool_names()` == **56** (the pinned count;
  `assistant_*` are NOT obsidian tools, so `test_nas_mcp_files_rw.py::==56` still passes).

## Read-only snapshot, no live-DB fallback
`_invoke_assistant` opens `sqlite3.connect(_ro_uri(db), uri=True)` (`mode=ro&immutable=1`) +
`PRAGMA query_only=ON` and threads that connection via `conn=` into the shared service.
- `test_snapshot_is_read_only` — on that connection, `CREATE TABLE` and `UPDATE` both raise
  `sqlite3.OperationalError` ("attempt to write a readonly database"). There is no live/writable handle
  in the assistant path.

## Write posture unchanged
- `test_assistant_reads_are_not_writes` — assistant reads succeed in safe mode; `ai_outputs_card_upsert`
  is denied in safe mode → it remains the ONLY write, and assistant tools are not writes
  (`write_attempted=False`, capability tier 1, access_mode "read").
- `test_denied_tools_stay_denied` — `raw_sql/sql/shell/exec/read_file_absolute/hb_output_delete` all
  deny with `action_denied_by_policy`.

## Auth & observability
- Origin auth is hard-on in `remote_cloudflare` (`profile.origin_auth_required()`), so `assistant_*`
  tools are reachable only by an authenticated caller (no new unauthenticated path).
- `test_mcp_status_reports_assistant` — `hb_mcp_status` reports `assistant_nav_enabled=true` and the
  full 12-tool list.
- `test_kill_switch` — `HB_MCP_ASSISTANT_NAV=0` → `assistant_*` deny with `assistant_nav_disabled`.

## No profile/allowlist widening
No edit to `db_allowlist.py` (still only `schema_migrations`), no positive read-allowlist added to
`profile.py`, no new write gate. The `assistant_*` tools use fixed parameterized queries via the
service — they do not widen `hb_db_select` or add raw SQL.
