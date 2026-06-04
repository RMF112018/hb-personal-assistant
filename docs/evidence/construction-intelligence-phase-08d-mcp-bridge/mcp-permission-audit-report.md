# Phase 08D — Prompt 10: MCP Permission Audit Report

**Evidence artifacts:** `mcp-permission-audit-report.md` (this) + `mcp-audit-receipt-proof.json` (generated)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-04 · **Base HEAD:** `56d30f2` · **Schema:** V37
**Scope:** Audit/permission agent (backing service; the `mcp audit` CLI is Prompt 11). Snapshots all four registries, runs the ten permission-audit checks, persists a metadata-only permission-audit run, and emits the call/denial receipt proof.

---

## 1. Posture

Local-first, read-only, metadata-only. Registry snapshots and the permission-audit run store
**only** counts, hashes, status, and reason codes — never raw content; every row carries the
twenty `CHECK(=0)` guard columns. The audit verifies **policy/registry posture**: the
allowed-tools and resources surfaces are checked at the registry/contract level (fast), plus
the lightweight metadata-only sub-proofs (denied/prompts/broker/runbook). The heavyweight
execution proofs that dispatch synthesis/retrieval are validated in their own prompts, not
re-run on every audit. It reads, never mutates external systems.

---

## 2. The ten permission-audit checks (all pass)

| # | Check | Verifies |
|---|---|---|
| 1 | `server_config_safe` | stdio transport + foundation startup checks pass |
| 2 | `allowed_registry_safe` | the nine approved workflow tools, bounded, no forbidden fields |
| 3 | `denied_registry_complete` | raw / direct-API / writeback / determination / URL actions all denied |
| 4 | `resources_safe` | five resources, approved-workflow-sourced, fail-closed |
| 5 | `prompts_safe` | five prompts route through allowed tools only |
| 6 | `receipts_metadata_only` | tool-call + denial receipts: hashes only, no raw columns, guards 0 |
| 7 | `claude_config_safe` | Claude Desktop preview is stdio-only and never auto-written |
| 8 | `no_raw_access` | no raw stores/files/payloads via tools/resources/prompts |
| 9 | `no_writeback` | permission policy `allow_* = false` + writeback actions denied |
| 10 | `no_direct_apis` | permission policy `allow_* = false` + direct-API/SQL actions denied |

`status = ok`, `finding_count = 0`, `proof_passed = true`.

---

## 3. Registry snapshots (four, guard-clean)

The agent persists a metadata-only snapshot of each registry:
- `second_brain_mcp_server_config_snapshots` (transport, config_hash)
- `second_brain_mcp_tool_registry_snapshots` (**allowed_tool_count=9**, **denied_action_count=27**, registry_hash)
- `second_brain_mcp_resource_registry_snapshots` (resource_count=5)
- `second_brain_mcp_prompt_registry_snapshots` (prompt_count=5)

All rows have every guard column 0.

## 4. Permission-audit run + receipt proof

A `second_brain_mcp_permission_audit_runs` row is persisted with `status`,
`checks_json` (the ten metadata-only check results), `finding_count`, policy/schema version,
and `evidence_path` (guards 0). The call/denial receipt proof (`mcp-audit-receipt-proof.json`)
attests both receipt tables (`second_brain_mcp_tool_call_receipts`,
`second_brain_mcp_denial_receipts`) store hashes/counts/reason codes only — no raw
arguments/results/content, no raw columns, all guards 0.

---

## 5. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (module + test) | All checks passed |
| `mypy src` | Success — no issues in **271** source files (strict) |
| `pytest tests/test_phase_08d_mcp_audit.py` | **4 passed** |
| `run_mcp_permission_audit()` | `proof_passed=true`, `status=ok`, `finding_count=0`, 10/10 checks |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the audit surface + the three no-writeback proofs,
per the validation-minimum rule. Closed-phase evidence churned by the proof runs was restored.
Full matrix at Prompt 15.

---

## 6. Deferred / scope statement

- **`mcp audit` CLI** + the other MCP CLI surfaces: Prompt 11; **MCP data-quality gates**:
  Prompt 12; **MCP no-raw-access / no-writeback proofs**: Prompts 13/14.
- The audit is the backing agent only; not yet exposed over CLI or stdio. `mcp_implemented`
  stays False; `mcp_exposure` gate `deferred_not_blocking`.

**Verdict:** the audit/permission agent snapshots all four registries, passes all ten
permission-audit checks, persists a metadata-only permission-audit run, and proves the
receipt structure is metadata-only. Cleared for Prompt 11 (MCP CLI surfaces).
