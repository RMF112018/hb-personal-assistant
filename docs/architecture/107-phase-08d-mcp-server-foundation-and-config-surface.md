# 107 — Phase 08D MCP Server Foundation and Config Surface (Prompt 03)

**Baseline**: Post-08D-P02 at `1400744` (schema V37; ten MCP tables; contracts/seeds/loader landed). This prompt adds the runtime **server foundation** only.

**Objective** (per prompt): Implement the local **stdio-only** MCP server entrypoint, fail-closed startup checks, the dependency decision for the optional `mcp` SDK, and the Claude Desktop config-preview surface. **No tools, resources, prompts, broker, or receipts** (Prompts 04–08); the server is fail-closed and refuses to serve.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-server-config-proof.md`
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/claude-desktop-config-preview.json`
- `docs/architecture/107-phase-08d-mcp-server-foundation-and-config-surface.md` (this)
- `tests/test_phase_08d_mcp_server.py`
- `src/hb_assistant/construction/second_brain/mcp/` (new module), `src/hb_assistant/cli/second_brain.py` (mcp group), `pyproject.toml` (optional `mcp` extra)

## Module layout (`construction/second_brain/mcp/`)
- `policy.py` — `evaluate_startup_checks()` (eight foundation checks + two deferred guard proofs) and `build_mcp_status()` (SDK availability via `importlib.util.find_spec`, `serve_blockers`, `ready_to_serve`, persists a metadata-only server-config snapshot). `_MCP_GUARDRAILS`.
- `config_preview.py` — `build_claude_desktop_config_preview()` (canonical preview, `assess_config_safety()`, schema-conformance vs the shipped JSON Schema, `_assert_no_raw`, persists a preview row, writes the evidence JSON). Never auto-applies; persists env **key names** only.
- `server.py` — `serve_stdio()` (fail-closed; never opens a socket/loop), `MCPUnavailable`, lazy `_import_mcp()` (`# pragma: no cover`).
- `store.py` — `write_mcp_server_config_snapshot` / `write_mcp_claude_desktop_config_preview` (canonical `SQLiteMigrator().apply()` + `get_connection` + `transaction`; all guards 0).

## CLI (`second-brain mcp …`)
`status` (foundation posture + snapshot), `config-preview --client claude-desktop` (safe preview + evidence JSON), `serve --stdio` (fail-closed, exit 1). `_AGENT_GUARDRAILS["mcp_implemented"]` unchanged (False) — no workflows exposed yet.

## Model
- **Transport**: stdio only. No HTTP/SSE/WebSocket/TCP/remote; no network from the MCP layer.
- **Fail-closed startup**: schema V37, server-policy seed (stdio-only), the four registry contracts present, fail-closed permission policy (all `allow_*` false), stdio-only transport. The MCP no-raw-access (Prompt 13) and no-writeback (Prompt 14) proofs are **deferred**; the tool broker is **not wired** (Prompt 04) — so `ready_to_serve` is always false and `serve` refuses.
- **Dependency decision**: `mcp` is an opt-in extra (`pip install -e .[mcp]`), lazy-imported, absent in the base/test environment. mypy's global `ignore_missing_imports` covers the lazy import; no pyproject mypy/ruff opt-in needed (the module is covered by the strict `construction.second_brain.*` override).

## Boundary
No tool broker, allowed/denied wrappers, resources, prompts, receipts, or real stdio loop. The two new V37 tables (`server_config_snapshots`, `claude_desktop_config_previews`) get their first metadata-only writers. `mcp_exposure` data-quality gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean (new module + CLI + test); `mypy src` clean (264 files; new module strict); focused pytest **17 passed**; broader `second_brain/mcp/cli` subset **143 passed**; `mcp status` foundation_ok=true / ready_to_serve=false; `config-preview` safe=true / schema-conformant; `serve` served=false exit 1; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
