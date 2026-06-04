# 114 — Phase 08D MCP Audit and Permission Agent (Prompt 10)

**Baseline**: Post-08D-P09 at `56d30f2` (broker + tools + denied + resources + prompts + Claude Desktop config/runbook). This prompt adds the audit/permission agent.

**Objective** (per prompt): Implement the audit/permission agent, registry snapshots, call/denial receipt proof, and permission audit report.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-permission-audit-report.md` + `mcp-audit-receipt-proof.json`
- `docs/architecture/114-phase-08d-mcp-audit-and-permission-agent.md` (this)
- `tests/test_phase_08d_mcp_audit.py`
- `src/hb_assistant/construction/second_brain/mcp/audit.py`, extended `store.py`, updated `__init__.py`

## Agent (`mcp/audit.py`)
- `snapshot_tool_registry()` — persists a `second_brain_mcp_tool_registry_snapshots` row (allowed=9, denied=27, registry_hash).
- `snapshot_all_registries()` — persists all four registry snapshots (server-config, tool, resource, prompt) and returns their ids.
- `run_mcp_permission_audit()` — snapshots the registries, runs the ten checks at the **registry/contract level** (`build_mcp_status`; `load_allowed_tools`/`load_global_requirements`/`load_resources`/`load_prompts`; the permission-policy seed `allow_* == false`) plus the lightweight metadata-only sub-proofs (`build_mcp_denied_tools_proof`/`build_mcp_prompts_proof`/`build_mcp_tool_broker_proof`/`build_mcp_claude_desktop_runbook_proof`), persists a metadata-only `second_brain_mcp_permission_audit_runs` row, and writes `mcp-audit-receipt-proof.json`. The heavyweight execution proofs (allowed-tools/resources, which dispatch synthesis/retrieval) are validated in their own prompts — not re-run on every audit.

## The ten checks
`server_config_safe`, `allowed_registry_safe`, `denied_registry_complete`, `resources_safe`, `prompts_safe`, `receipts_metadata_only`, `claude_config_safe`, `no_raw_access`, `no_writeback`, `no_direct_apis`. `status=ok`/`finding_count=0` when all pass.

## Store (`mcp/store.py`)
New writers `write_mcp_tool_registry_snapshot` and `write_mcp_permission_audit_run` (both metadata-only; all twenty guards 0). The tool-call and denial receipt writers already existed (Prompt 04).

## Model
Read-only, metadata-only. Snapshots store counts + hash + versions; the audit run stores status + the ten-check JSON (names/booleans/short reason codes) + finding count + evidence path — never raw content. The call/denial receipt proof attests both receipt tables hold hashes/counts/reason codes only.

## Boundary
No `mcp audit` CLI (Prompt 11); no stdio exposure. `mcp_exposure` gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (271 files; strict); `pytest tests/test_phase_08d_mcp_audit.py` **4 passed**; `run_mcp_permission_audit()` `proof_passed=true` / `status=ok` / 10-of-10 checks; four registry snapshots + the audit run persist guard-clean; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
