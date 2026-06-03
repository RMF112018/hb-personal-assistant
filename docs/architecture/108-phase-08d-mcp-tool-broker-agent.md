# 108 — Phase 08D MCP Tool Broker Agent (Prompt 04)

**Baseline**: Post-08D-P03 at `0498fef` (stdio server foundation + config preview). This prompt adds the policy-gated dispatch engine.

**Objective** (per prompt): Implement the policy-gated broker — allowed/denied registry loading, argument validation, bounded output validation, metadata receipts, and fail-closed errors. The nine workflow wrappers are Prompt 05.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-tool-broker-proof.md` + `mcp-tool-broker-proof.json`
- `docs/architecture/108-phase-08d-mcp-tool-broker-agent.md` (this)
- `tests/test_phase_08d_mcp_broker.py`
- `src/hb_assistant/construction/second_brain/mcp/{registry,broker,proof}.py`, extended `store.py`, updated `policy.py` + `__init__.py`

## Components
- `registry.py` — `load_allowed_tools()` (9 specs: wrapper/maps_to/risk/receipt_required), `load_denied_actions()` (27), `load_global_requirements()`; fail-closed `RegistryUnavailable` on missing/empty.
- `broker.py` — `ToolBroker(wrappers=…, db_path=…, persist=…)`; `dispatch(tool, arguments, client_name)`. Injectable `wrappers` dispatch seam (empty in P04). `MAX_RESULTS=50`, 16 KiB arg cap. Reason codes: `action_denied_by_policy`, `tool_not_allowed`, `wrapper_unavailable`, `invalid_arguments`, `unsafe_output`, `broker_error`.
- `store.py` — `write_mcp_tool_call_receipt` / `write_mcp_denial_receipt` (metadata-only; guards 0).
- `policy.py` — status now reports `mcp_allowed_tool_specs`/`mcp_denied_actions`; serve blocker is `workflow_wrappers_not_implemented_prompt_05`.
- `proof.py` — `build_mcp_tool_broker_proof()` exercises all paths against a temp DB and writes the JSON evidence.

## Dispatch model (deny first)
correlation id → **denied registry (name or denied token in args)** → allowed registry → argument validation → wrapper present? → invoke (try/except) → bound + `_assert_no_raw` output → metadata-only receipt → safe envelope. Every error path is a fail-closed denial with a metadata-only denial receipt; raw error text is never echoed or stored.

## Receipt model
Tool-call receipts store `args_hash`/`result_hash`, decision, workflow_wrapper, output_classification, source/result counts, correlation id, policy/schema version — never raw arguments or results. Denial receipts store the action name, reason code, `request_hash`, and versions — never the raw requested content. Both tables enforce the twenty `CHECK(col = 0)` guards.

## Boundary
No workflow wrappers (Prompt 05), no resources/prompts (07/08), no CLI dispatch surface (Prompt 11). The broker is **not exposed over stdio** — `serve` stays fail-closed; all nine allowed tools currently resolve to `wrapper_unavailable`. `mcp_implemented` stays False; `mcp_exposure` gate `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (267 files; strict); `pytest` broker + server + schema + contracts **27 passed**; `build_mcp_tool_broker_proof()` `proof_passed=true` (registries 9/27; 1 tool-call + 5 denial receipts; guards all 0; receipt tables have no raw columns); `mcp status` reports the broker registries; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
