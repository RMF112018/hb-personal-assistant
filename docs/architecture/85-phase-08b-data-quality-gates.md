# 85 — Phase 08B: Data-Quality Gate Framework (Prompt 13)

**Status:** Documented (the framework is already implemented; built incrementally across 08B prompts
02–12). Schema **V34 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `99ed374` (08B Prompt 12; 08A closeout `954a518` is ancestor).
**Scope:** The first single-source description of the Phase 08B **data-quality gate framework itself**
(docs 76–84 each describe one surface). This prompt is verify + document — no runtime gate added, no
schema change — plus a coverage-invariant regression test.

## Context

"Implement Phase 08B data-quality gates" is already satisfied in repo truth: the gate set exists, is
contract-backed, fully tested, and passing (**15 pass / 0 warning / 0 fail / 1 deferred**). This doc
captures the framework's shape so it is legible as a whole rather than only as the sum of per-surface
prompts.

## The gate set

`construction/second_brain/data_quality.py::evaluate_phase_08b_data_quality_gates(db_path=…)` is
read-only and persists nothing. It builds the gates named in `PHASE_08B_GATE_NAMES` (16 entries) and
returns a consolidated report. Gate taxonomy:

- **Receipt-persistence gates** (`_receipt_gate`, guard-column presence on the table):
  `agent_run_receipt_persistence`, `agent_model_receipt_persistence`, `delivery_handoff_durability`.
- **Policy / contract gates:** `automation_policy_seed` (`validate_phase_08b_automation_policy`),
  `observability_reason_codes` (contract carries a structured reason-code vocabulary).
- **Per-surface proof-gates** (`_proof_gate(name, build_*_proof())` — each builds a deterministic
  temp-DB proof exercising its surface's success/failure/blocked/stale/dry-run paths):
  `automation_health` (P03), `launchd_install` (P04), `run_registry_locking` (P05), `retry_recovery`
  (P06), `freshness_observability` (P07), `daily_brief_job_health` (P08), `daily_brief_delivery`
  (P09), `daily_brief_html_render` (P10), `daily_brief_notification` (P11), `daily_brief_open` (P12).
- **Deferred surface** (`deferred_not_blocking`, never reported as pass): `automation_execution` —
  the full executor (weekend gating + local alerting emission + morning-orchestrator wiring) owned by
  a later prompt.

## Consolidated verdict

The report carries: `ok` (= `status_counts["fail_blocking"] == 0`), `by_field_status` (per-gate
status), `status_counts` (pass / warning / fail_blocking / deferred_not_blocking),
`required_fields_covered` (`sorted(by_field_status) == sorted(contract.required_fields)`),
`readiness_overstated=False`, and `schema_version` / `schema_version_expected`. CLI surface:
`hb-assistant second-brain data-quality phase-08b-gates --json` (exit 0 unless any `fail_blocking`).

## Invariants (guarded by tests)

- **Gate set ≡ contract:** `PHASE_08B_GATE_NAMES` and
  `resources/json/phase_08b_data_quality_gates.json::required_fields` are kept in lock-step
  (`required_fields_covered` + `test_phase_08b_gate_coverage.py`).
- **No readiness overstatement:** a surface whose execution is owned by a later prompt is
  `deferred_not_blocking`, never `pass` (`automation_execution`).
- **Table coverage:** every 08B-era table is covered — explicitly gated (receipt/handoff/proof gates)
  or via `safety.build_second_brain_no_writeback_proof`, whose scan scope is `_PHASE_08A_TABLES`. The
  new `test_phase_08b_gate_coverage.py` fails closed if any live `daily_brief_%_receipts` /
  `second_brain_%_receipts` table is missing from that scope.

## Live-data integrity posture

Data quality is enforced at the DB layer and proven over live rows, not asserted in prose:
`store/connection.py::get_connection` sets `PRAGMA foreign_keys = ON` (receipt `brief_run_id` FKs
enforced); per-row guard columns (`CHECK(col = 0)`) forbid raw-content persistence; channel/target/
mode domains are `CHECK`-pinned (`obsidian_vault` / `local_macos` / `vault|html`; `dry_run|apply`).
`build_second_brain_no_writeback_proof` (schema 34) derives the guard map from each table's CREATE
SQL, scans **live stored values** for secrets/forbidden tokens, and validates dry-run generated
outputs — fail-closed on any absent expected table.

## Known limitations / next

- `automation_execution` stays the lone deferred gate — flipping it is the final 08B build target
  (the executor that consumes the observability + substrate + delivery + render + notify + open
  surfaces).
- The 08B gate set is intentionally scoped to the `second-brain data-quality phase-08b-gates` command
  (not rolled up into the construction-agent top-level surface).
