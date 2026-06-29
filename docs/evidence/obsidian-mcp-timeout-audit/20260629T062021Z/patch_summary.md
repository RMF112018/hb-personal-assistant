# Patch Summary — Obsidian MCP tool-timeout guard + diagnostics

Branch `fix/obsidian-mcp-tool-timeout-guard` off `origin/main` (`97252eae`). **Uncommitted** pending
Bobby's authorization.

## Change

Every one of the 38 `@mcp.tool()` closures in `mcp_app.py` is converted from sync `def` to `async def`
with the **same signature** (so FastMCP's JSON-schema + `Context` introspection is unchanged). Each
closure resolves all ctx-bound values **on the event loop** (`_enforce`, `_operator_mode`,
`_principal_kind`), builds its `args` dict, then returns:

```python
return await _run_tool("<name>", ctx, lambda: svc.<method>(args), args)
```

New shared `_run_tool` (inside `build_streamable_http_app`, closes over `svc`):
- runs only the pure-I/O `svc.<method>(args)` via `await anyio.to_thread.run_sync(call, abandon_on_cancel=True)`
  — off the event loop, so one slow tool no longer freezes the whole server;
- bounds it with `with anyio.fail_after(_tool_timeout_seconds(config))`; on `TimeoutError` raises
  `ObsidianMcpToolError("tool_timeout")` (a fast structured MCP tool error). `abandon_on_cancel=True`
  is required so the deadline fires even against a truly stuck call (the worker thread is abandoned;
  atomic `tempfile`+`os.replace` writes cannot be corrupted by abandonment);
- maps any unexpected `Exception` → `ObsidianMcpToolError("internal_error")` — standardizes the error
  and stops raw exception text (which can contain a path/content fragment) leaking to the client;
- emits redacted `tool_start` / `tool_end` / `tool_error` diagnostics on logger
  `hb_assistant.obsidian_mcp.mcp` (fields: tool, status, elapsed_ms, error_code, caller_surface,
  authorization_present (bool), principal_kind, plus an allow-listed `_safe_descriptors(args)` view —
  paths/scopes/limits/flags only; `content`/`updates` as char counts; query/title/name free-text and
  raw bodies dropped). Never logs token/Authorization/content/raw body.

Config: `ObsidianMcpConfig.tool_timeout_seconds: int = 30` (validated positive; `schema_version` 1→2),
mirrored in `ObsidianMcpConfigPatch` and the API `ObsidianMcpConfigPatchRequest` so it is operator-tunable.

## Files

- `src/hb_assistant/obsidian_mcp/mcp_app.py` — imports; `_logger`, `_DEFAULT_TOOL_TIMEOUT_SECONDS`,
  `_SAFE_LOG_KEYS`/`_LEN_ONLY_LOG_KEYS`, `_tool_timeout_seconds`, `_safe_descriptors`; `_run_tool`;
  all 38 closures async + offloaded.
- `src/hb_assistant/obsidian_mcp/config.py` — `tool_timeout_seconds` field + validator + patch model + `schema_version=2`.
- `src/hb_assistant/construction/analytics/api.py` — one field on `ObsidianMcpConfigPatchRequest`.
- `tests/test_obsidian_mcp_timeout.py` — new (42 tests).

No changes to `tools.py`, `service.py`, `mutations.py`, `pathsafe.py`, `oauth_store.py` — security
posture, scope enforcement, principal threading, and return shapes are preserved by construction.

## Validation

- `tests/test_obsidian_mcp_timeout.py` — 42 passed (timeout fires fast + structured; server stays
  responsive while a tool stalls; tool_error diagnostic; no token/content leak; insufficient_scope
  rejected before any offload; strict-JSON for all 38 tools).
- Full `-k obsidian_mcp` suite — 154 passed.
- `ruff check` + `mypy` clean on `mcp_app.py` / `config.py` (api.py has 37 pre-existing ruff findings
  unrelated to the one-line addition).
- Pre/post runtime contrast: PRE-FIX unbounded 3.01 s / no timeout; POST-FIX bounded 1.01 s / `tool_timeout`.
