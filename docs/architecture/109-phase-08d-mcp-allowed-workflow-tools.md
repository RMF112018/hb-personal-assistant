# 109 — Phase 08D MCP Allowed Workflow Tools (Prompt 05)

**Baseline**: Post-08D-P04 at `a5cf1c4` (policy-gated broker with an empty wrapper registry). This prompt wires the nine real workflow wrappers.

**Objective** (per prompt): Implement the nine allowed tools as workflow wrappers only — no raw stores, arbitrary SQL, direct APIs, or writeback.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-workflow-wrapper-proof.md` + `mcp-tool-contract-proof.json`
- `docs/architecture/109-phase-08d-mcp-allowed-workflow-tools.md` (this)
- `tests/test_phase_08d_mcp_wrappers.py`
- `src/hb_assistant/construction/second_brain/mcp/wrappers.py`, extended `proof.py`, updated `policy.py` + `__init__.py`

## Wrappers (`mcp/wrappers.py`)
Nine `mcp_*_wrapper(arguments, *, db_path=None) -> dict`, each a thin adapter over an existing offline-safe, metadata-only builder (see the wrapper-proof table). Each returns `{status, provenance, results, source_count, output_classification}`; the broker adds `policy_posture` + `receipt_id` and runs the no-raw / bounding gate. Wrappers extract only safe scalar/count/class fields and degrade gracefully (never raise). `build_wrapper_registry(*, db_path=None)` binds `db_path` into each wrapper via `functools.partial` for the broker's `Callable[[dict], dict]` seam.

## Integration
- `mcp/__init__.py`: `build_default_broker(*, db_path=None, persist=True)` = `ToolBroker(wrappers=build_wrapper_registry(db_path=db_path), …)`.
- `mcp/policy.py`: the `workflow_wrappers_not_implemented_prompt_05` serve blocker is removed; `mcp_tools_registered` now reflects the registry (9). Remaining serve blockers: the two guard proofs (Prompt 13/14) + the optional SDK. `ready_to_serve` stays False; `mcp_implemented` stays False (not stdio-exposed).
- `mcp/proof.py`: `build_mcp_allowed_tools_proof()` dispatches all nine tools through the real broker against a temp DB and writes `mcp-tool-contract-proof.json`; the forbidden-field check is an exact recursive key scan (so safe keys like `no_final_determination` are not false-positives).

## Posture
Read-only / offline / mock-first; no live model or network. The only local write is `hb_memory_feedback` → a local `second_brain_operator_feedback` row (local metadata; no external/source-system writeback; no candidate promotion). `hb_open_daily_brief` reports policy/status only and never opens. No raw bodies/prompts/responses/SQL/URLs/tokens or final determinations cross the boundary; the broker bounds output to 50 results and runs `_assert_no_raw`.

## Boundary
No CLI dispatch surface (Prompt 11), resources (07), prompts (08), audit agent (10), or stdio exposure. `mcp_exposure` data-quality gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (268 files; strict); `pytest` wrappers + broker + server + contracts + schema **34 passed**; `build_mcp_allowed_tools_proof()` `proof_passed=true` (9 tools allowed; 9 metadata-only receipts; guards 0; no forbidden fields); `mcp status` `mcp_tools_registered=9`; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
