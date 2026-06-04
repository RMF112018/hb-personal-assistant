# Phase 08D — Operational Local Stdio MCP Serve Proof (Prompt 15)

Proof that the Phase 08D local MCP bridge is **operational**: with the optional `mcp`
Python SDK installed (`pip install -e ".[mcp]"`), `hb-assistant second-brain mcp serve
--stdio` runs a real low-level MCP stdio server over the existing, audit-proven safe
broker / resources / prompts, and a real MCP client completes the full protocol round
trip. Local stdio is the package's explicitly allowed transport; no network listener is
opened.

## Environment

- MCP SDK: `mcp` **1.27.2** (optional extra; absent from the base install).
- Schema: **V37** (unchanged). Server name advertised: `hb-personal-assistant`.
- Adapter: `construction/second_brain/mcp/sdk_server.py` (lazy-imports the SDK) wiring
  `list_tools/call_tool` → `ToolBroker.dispatch` (deny-first, `validate_input=False` so the
  broker is the single authority), `list_resources/read_resource` → `read_resource`,
  `list_prompts/get_prompt` → `render_prompt`.

## In-process client↔server round trip (`create_connected_server_and_client_session`)

Driven against `build_mcp_app(db_path=<temp>)` with a real `mcp.ClientSession`:

| Step | Result |
| --- | --- |
| `initialize` | ok — server `hb-personal-assistant` |
| `list_tools` | **9** tools |
| `list_resources` | **5** resources |
| `list_prompts` | **5** prompts |
| `call_tool("hb_status", {})` | `decision=allowed`, metadata-only envelope, **receipt written** |
| `call_tool("hb_delete_everything", {})` (unknown) | `decision=denied`, `reason_code=tool_not_allowed`, **denial receipt written** |
| `read_resource("hb://status/system")` | bounded JSON payload (`application/json`) |
| `get_prompt("ask_project_question", …)` | 2 messages (advisory posture mapped to `user`) |

No raw content / token / URL appeared in any tool envelope, resource payload, prompt
render, or receipt (the broker's `_assert_no_raw` output fence + the metadata-only receipt
schema enforce this).

## End-to-end subprocess over real stdio pipes

The exact command Claude Desktop launches — `hb-assistant second-brain mcp serve --stdio
--json` — was spawned as a separate OS process (temp app-support DB via `HB_PA_CONFIG`,
migrated to V37 first) and driven with the SDK's `stdio_client` + `ClientSession`:

- `initialize` ok; `list_tools`=9; `list_resources`=5; `list_prompts`=5.
- `call_tool("hb_status")` → `allowed` + receipt; `call_tool("raw_sqlite_query", {"sql": …})`
  → `denied` (`action_denied_by_policy`) + denial receipt.
- `read_resource` and `get_prompt` resolved bounded payloads.
- Receipts persisted in the temp DB: **1 allowed + 1 denial** (metadata-only; all guard
  `CHECK(... = 0)` columns hold).
- The serve envelope (`served=true`, `ready_to_serve=true`, `foundation_ok=true`) is emitted
  to **stderr only** — stdout carried solely the JSON-RPC stream, so the client parsed every
  message cleanly. Client exit code **0**.

## Fail-closed posture preserved

- Without the SDK (`mcp_sdk_not_installed`) or on a failing foundation check (e.g. an
  uninitialized DB below schema V37), `serve_stdio` refuses: `served=false`, the CLI exits
  non-zero, and no loop is entered.
- `second-brain mcp serve --stdio --json --dry-run` reports readiness without serving
  (exit 0 when `ready_to_serve`, else 1).
- `serve_stdio` is gated on `build_mcp_status().ready_to_serve`, which requires schema V37,
  all registries, the fail-closed permission policy, stdio-only transport, and the Prompt
  13/14 no-raw / no-writeback guard proofs.

## Guardrails (operational)

Local-first; stdio-only (no network listener); every tool call (allowed/denied) routes
through the deny-first broker and emits a metadata-only receipt; no raw stores, arbitrary
SQL, raw files/Obsidian, direct Graph/Procore, writeback, signed/download URLs, or raw
prompt/response text; advisory only — no final determinations. Attaching the server to the
operator's Claude Desktop app remains a one-time manual paste of the (preview-only,
never-auto-written) config preview.
