# 110 — Phase 08D MCP Denied Tools and Policy Enforcement (Prompt 06)

**Baseline**: Post-08D-P05 at `8cd0800` (broker + nine workflow wrappers). The broker already denies-first; this prompt proves and refines denial enforcement.

**Objective** (per prompt): Implement explicit denied actions and metadata-only denial receipts; add tests for each denial class.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-denied-tool-proof.md` + `mcp-denied-tool-proof.json`
- `docs/architecture/110-phase-08d-mcp-denied-tools-and-policy-enforcement.md` (this)
- `tests/test_phase_08d_mcp_denied.py`
- `src/hb_assistant/construction/second_brain/mcp/broker.py` (refinement), extended `proof.py`, updated `__init__.py`

## Model
- **Deny-first**: the denied registry (27 actions from `phase_08d_mcp_denied_tools_contract.json`) is checked before the allowed registry / argument validation / dispatch.
- **Explicit naming**: a denied *tool name* is denied; a denied action riding in an *allowed* tool's arguments is also denied. Prompt 06 refines the latter so the denial receipt's `requested_action` is the **matched denied token** (previously the tool name) — denials now name the specific action in both cases.
- **Single reason code**: `action_denied_by_policy` (package prescribes one code; `requested_action` carries the specific action — no per-class enumeration, no named classes). No separate `allow_*` permission layer.

## Denial receipts (metadata-only)
`second_brain_mcp_denial_receipts` stores `requested_action`, `decision='denied'` (CHECK), `denial_reason_code`, `request_hash`, policy/schema version, correlation id + the twenty `CHECK(=0)` guards. No raw/content columns exist; raw arguments are reduced to a hash. The no-raw-echo property is proven: a denied request carrying a secret marker + URL leaves neither in any receipt column.

## Proof + tests
- `proof.py::build_mcp_denied_tools_proof()` exercises all 27 actions + the token-in-args case + the raw-content case against a temp DB and writes `mcp-denied-tool-proof.json` (`proof_passed=true`; 29 denial receipts; no raw echoed; guards 0).
- `tests/test_phase_08d_mcp_denied.py` parametrizes all 27 actions (grouped into 8 conceptual classes for readability), the token-naming case, the raw-content-not-persisted case, and the proof.

## Boundary
No CLI surface (Prompt 11), no stdio exposure (`serve` fail-closed). MCP no-raw-access / no-writeback proofs are Prompts 13/14. `mcp_exposure` gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (268 files; strict); `pytest` denied + broker + wrappers **48 passed**; `build_mcp_denied_tools_proof()` `proof_passed=true`; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
