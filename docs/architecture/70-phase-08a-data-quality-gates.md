# 70 — Phase 08A Second-Brain Data Quality Gates

Status: implemented (Phase 08A Synthesized Prompt 14). Builds on records 57–69.

- Read-only gate evaluator; aggregates existing validators/proofs; persists nothing;
  schema/contract-table count unchanged (V26 / 141). Readiness is never overstated.

## Purpose

Provides `second-brain data-quality phase-08a-gates`: one conformance report over the Phase
08A runtime (runtime readiness, agent registry, model profile, retrieval, research packet,
evaluation, memory provenance, daily-brief handoff) plus liveness/deferred surfaces. It
distinguishes `pass` / `warning` / `fail_blocking` / `deferred_not_blocking` and surfaces
offline/mock synthesis as `warning` and unimplemented surfaces as `deferred` so readiness is
never claimed beyond what is real.

## Repo-truth reconciliation (decisive)

- **No schema change.** The gate report is computed read-only and not persisted — matching
  the established `construction/data_quality/phase_07d.py` posture (per-phase gates are not
  persisted). Schema stays V26 / 141 contract tables.
- **Reuses the established pattern.** Status vocabulary + report shape mirror `phase_07d.py`
  (`evaluate_*_data_quality_gates` → command/ok/gates/by_field_status/required_fields_covered/
  guardrails). Inputs are the existing arg-free proof builders + `load_second_brain_config`.
- **New contract.** `data_quality_gates_contract` (`phase_08a_data_quality_gates.json`,
  required_fields = the 12 gate names, `statuses` vocabulary, guardrails incl.
  `no_readiness_overstatement`) registered in `second_brain/contracts.py`. The evaluator's
  `required_fields_covered` asserts gate names == contract required_fields.
- **Separate from legacy.** The `construction-agent data-quality` (07A/07D) surface is
  unchanged; this is a parallel `second-brain data-quality` group.

## Code

- `construction/second_brain/data_quality.py` —
  `evaluate_phase_08a_data_quality_gates(*, db_path=None)` (12 gates: 8 proof-backed `pass`/
  `fail_blocking`, 1 `synthesis_liveness` warning when not live, 3 `deferred_not_blocking`)
  + `build_phase_08a_gates_proof()`. `runtime_readiness` applies the idempotent migrator then
  checks `current_version == LATEST_SCHEMA_VERSION` (same posture as every second-brain
  writer). `ok = no fail_blocking`.

## CLI

`hb-assistant second-brain data-quality phase-08a-gates [--json]` — emits the report; exit 0
when `ok`, else 3.

## Guardrails

Read-only; aggregates existing validators/proofs (temp DBs / seeds); no external systems, no
writeback, no raw content (report is metadata/status only). Statuses distinguish
pass/warning/fail_blocking/deferred_not_blocking; offline/mock synthesis → warning,
unimplemented → deferred; `readiness_overstated=false`.

## Evidence

`docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/`:
`phase-08a-gates-proof.json` (`proof_passed: true`; status_counts pass 8 / warning 1 /
fail 0 / deferred 3), with the narrative in `14-phase-08a-data-quality-gates-proof.md`.
