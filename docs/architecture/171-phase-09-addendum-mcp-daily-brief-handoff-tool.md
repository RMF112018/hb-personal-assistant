# 171 — Phase 09 Addendum: MCP Daily Brief Handoff Tool (hb_daily_brief_packet)

**Status:** New narrow MCP workflow-wrapper tool exposing the `DailyBriefHandoffPacketV1` for Claude scheduled rendering only.
**Schema:** unchanged (V39; no migration; persists only the existing metadata-only MCP tool-call receipt). **Version:** 1.0.0-phase-09-addendum (package: Daily Brief / MCP Handoff & Rendering, Prompt 02).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/mcp-daily-brief-handoff-tool.{json,md}` + `mcp-daily-brief-handoff-proof.{json,md}`.
**Builds on:** record 170 (daily-brief packet builder), records 107–119 (Phase 08D MCP bridge).

---

## 1. Objective

Expose the approved metadata-only daily-brief packet (record 170) through **one** narrow MCP tool so
Claude can render the scheduled brief — without duplicating retrieval logic in MCP or opening any raw /
DB / vector / Graph / Procore path. This is the first and only Phase 09 surface deliberately added to
the otherwise Phase-08D-isolated MCP bridge.

## 2. The tool

`hb_daily_brief_packet` (repo `hb_*` convention; maps to the suggested
`construction_daily_brief_packet` / `get_daily_brief_handoff`). Wrapper
`mcp_daily_brief_packet_wrapper` (`mcp/wrappers.py`) reuses `build_daily_brief_packet` (record 170) and
returns the full `DailyBriefHandoffPacketV1` at `result.results[0]` via the standard bounded envelope.

Inputs: `date` (optional, default local today), `project_scope` (optional, default `all` → no project
filter), `include_rendering_instructions` (optional, default true; when false the packet drops the
rendering-instructions block but always keeps guardrails). Fails closed to a safe degraded metadata
error (`packet_unavailable`) on any failure — never raises into the broker.

## 3. Registration & policy (existing broker patterns)

One allowlist entry added to `phase_08d_mcp_allowed_tools_contract.json`
(`wrapper`/`maps_to`/`risk: low`/`receipt_required: true`) and one binding in
`build_wrapper_registry`. The tool flows through the unchanged `ToolBroker.dispatch` gate:
deny-first → allowed-registry → arg validation → wrapper → bounded + `_assert_no_raw` output → metadata-only
receipt. Deny-first is preserved: memory mutation, vector search, and daily-brief apply are **not**
allowlisted (denied as `tool_not_allowed`); DB/Graph/Procore/writeback actions stay explicitly denied;
denied tokens riding in arguments are denied.

The allowed-tool count moves **9 → 10**. All count-dependent invariants were updated to the new true
total (and stay truthful/green): the 08D data-quality gates `allowed_tools`/`workflow_wrappers`
expected counts (`data_quality.py`), `audit.py` registry-safe check, `proof.py` no-writeback
wrapper-count surface, and the corresponding test assertions across the 08D MCP suite. No guardrail was
weakened — the new tool is read-only, workflow-wrapper-only, no-raw, no-writeback, no-determination.

A naive substring check in `test_phase_08d_mcp_wrappers.py` was corrected to the broker's actual
exact-key gate (`_collect_keys`), because the mandated guardrails key `no_final_determinations`
contains the substring `final_determination` — a legitimate safety flag, not a leaked raw field.

## 4. Proof & CLI

`mcp/daily_brief_handoff_proof.py` → `build_mcp_daily_brief_handoff_proof` dispatches the tool through a
real broker against a controlled seeded temp DB and attests: tool registered, dispatch allowed, output
matches the packet contract (top-level + per-item fields), no raw / no forbidden result field names,
read-only (0 `daily_brief_runs`, ≥1 metadata-only call receipt), missing-input fail-safe, deny-first
preserved, and the MCP no-raw + no-writeback proofs still pass. CLI:
`hb-assistant second-brain mcp daily-brief-handoff-proof --json` (plus existing `mcp audit` /
`mcp no-raw-access` / `mcp no-writeback`).

## 5. Validation

`ruff`/`mypy` clean. `tests/test_phase_09_mcp_daily_brief_handoff.py` (10 tests) green, plus the updated
08D MCP suite (broker/wrappers/cli/server/audit/gates) at the new count of ten and the record-170
packet suite. `mcp audit`, `mcp no-raw-access`, `mcp no-writeback`, and the new handoff proof all report
`proof_passed=true`. The pre-existing `test_phase_08d_schema_v37` lifecycle-classification failure (V39
`second_brain_review_burden_*` tables) is unrelated — it fails identically on clean `HEAD`.
