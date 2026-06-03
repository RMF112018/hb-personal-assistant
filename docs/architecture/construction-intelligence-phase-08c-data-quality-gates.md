# Phase 08C — Data Quality Gates

Design record for the Phase 08C financial data-quality gate evaluator and its evidence proof.
Read-only, local-first, advisory-only. Repo code, tests, and evidence are authoritative.

## Purpose

Aggregate the Phase 08C financial substrate into one conformance report with an honest
`pass / warning / fail_blocking / deferred_not_blocking` taxonomy, and write a tamper-evident
`phase-08c-gates-proof.json` (+ `.md`). The proof **never passes when required evidence is missing**.

## Evaluator — `evaluate_phase_08c_data_quality_gates(*, db_path=None)`

`construction/second_brain/data_quality.py`. Read-only; persists nothing. Gates (in order):

- `schema_contracts` — `data_quality_gates_contract` loads → `pass`, else `fail_blocking`
  (`CONTRACT_LOAD_FAILED`).
- `endpoint_inventory` — coverage contract families present → `pass`/`warning`.
- the **ten V35 financial tables** — for each: table absent → `fail_blocking` (`TABLE_ABSENT_IN_V35`);
  any required guard column missing from the DDL (`advisory_only`,
  `raw_financial_source_payload_persisted`, `financial_determination_performed`,
  `payment_decision_performed`, `claim_or_entitlement_decision_performed`,
  `external_writeback_performed`) → `fail_blocking` (`GUARD_COLUMN_MISSING`); else `pass`.
- `amount_normalization`, `currency_completeness`, `wbs_cost_code_completeness`, `source_coverage`,
  `exposure_marts`, `readiness_agent` — real builder calls; `pass` on success, `warning` on error.
- `forecast_readiness` — inherits the Prompt 08 forecast evaluator `gate_status` (can be
  `fail_blocking` when fail-closed source shells exist).
- `review_required_policy`, `cli_operator_status` — `pass`.
- `no_writeback_no_raw_financial_output` — real, **non-writing** attestation via
  `financial_no_writeback.run_financial_no_writeback_checks(conn)` (guard columns + money-not-float +
  evidence redaction + no-live posture); all checks pass → `pass`, else `fail_blocking`.

### Honest aggregation
- `status_counts` counts all four statuses from `gate_status` (no hardcoded `0`); `ok = fail_blocking == 0`.
- `readiness_overstated` (`_compute_readiness_overstated`) — `True` when a readiness-claiming gate
  (`readiness_agent` / `forecast_readiness` / `review_required_policy`) is `pass` while **any** gate is
  `fail_blocking`; `False` otherwise. Honors the "readiness never overstated" guardrail by detecting it.
- `required_fields_covered` — `True` iff every required gate name from the contract is present.

Pure, unit-tested helpers: `_count_gate_statuses`, `_compute_readiness_overstated`,
`_missing_required_evidence` (gates that are `fail_blocking` due to `TABLE_ABSENT_IN_V35` /
`CONTRACT_LOAD_FAILED` / `GUARD_COLUMN_MISSING`).

## Proof — `build_phase_08c_gates_proof(*, db_path=None, out_dir=None)`

Runs the evaluator, then writes `phase-08c-gates-proof.json` (+ a `_render_phase_08c_gates_md` →
`.md`) to the 08C evidence dir, redaction self-scanned before write. Key fields: `proof_passed`,
`ok`, `generated_utc`, `schema_version`/`schema_version_expected`, `status_counts`, `by_field_status`,
`gates`, `required_fields_covered`, `readiness_overstated`, `missing_required_evidence`,
`stop_checks`, `guardrails`, `evidence_paths`.

**Stop condition.** `proof_passed = ok AND not readiness_overstated AND not missing_required_evidence`.
When a required table/contract/guard is missing, the offending gate is `fail_blocking` →
`missing_required_evidence` is non-empty → `proof_passed` is `False`. `stop_checks
.gates_passed_with_missing_evidence` is always `False` by construction.

## CLI

`hb-assistant second-brain data-quality phase-08c-gates [--project] [--json/--no-json]` calls
`build_phase_08c_gates_proof()` (writes the proof) and surfaces `proof_passed`, `status_counts`,
`readiness_overstated`, `missing_required_evidence`, `proof_path`, plus the shared 08C operator
envelope (`advisory_only`, `guardrails`, `attestations`, `evidence_paths`). The payload retains
`by_field_status` (so the `forecast_readiness` key remains present).

## Files

- `src/hb_assistant/construction/second_brain/data_quality.py` — evaluator honesty fixes, helpers,
  proof writer.
- `src/hb_assistant/construction/second_brain/financial_no_writeback.py` — `run_financial_no_writeback_checks`
  (non-writing) reused by the no-writeback gate.
- `src/hb_assistant/cli/second_brain.py` — gates command writes + surfaces the proof.
- `tests/test_phase_08c_gates.py` — four-status classification, `readiness_overstated`, proof writer,
  stop condition (missing evidence → not passed), migrated/unmigrated evaluator smoke.
