# ADR 296 — Forecast Phase 2c: finish projection coverage (no migration)

## Status

Accepted.

## Context

Phases 2a (V63 run-output) and 2b (V66 decision-support) shipped the schema + read-only
projectors but, by design, populated only the cleanly-sourced subset and left several tables
`operational_empty_expected`. The schema is complete on main; this phase **extends the existing
projectors** to fill the deferred tables from additional CFR downstream packages. **No new
tables, no migration, no contract/count change** — so it is immune to the schema-version /
count-lockstep churn from the concurrent schedule sessions.

## Decision

Extend the two read-only projectors with optional, explicit downstream-package inputs (no
latest-glob), reusing every existing safety property (temp-DB only, `is_live_db_path`
fail-closed, idempotent UPSERT, `raw_json` authoritative, TEXT-Decimal). No new scoring math —
emitted values are stored verbatim; the only computation is deterministic counts/means.

**Output coverage** (`output_projection_engine` / `output_repository`) — child rows under the
analysis-derived `output_id`:
- `forecast_output_monthly` ← `forecast_monthly_package/monthly_forecast_by_budget_code.jsonl`
- `forecast_output_probability` ← `forecast_probability_package/probabilistic_final_cost_by_budget_code.jsonl` (`simulated_p10/p50/p90`)
- `forecast_output_changes` ← `forecast_comprehensive_package/integrated_change_explanation.jsonl` (`change_amount`)
- `forecast_output_staffing` ← `forecast_staffing_plan_package/staffing_plan_monthly_by_budget_code.jsonl` (unrolled monthly list; cost only — `role`/`headcount` not emitted)

**Decision-support coverage** (`decision_support_engine` / `decision_support_repository`) —
per-run rollups from the `forecast_accuracy` package:
- `forecast_method_eligibility` ← `eac_estimates_by_budget_code.jsonl` aggregated per method
  (status from applicable-count + reliability: `eligible_weighted` / `eligible_advisory` /
  `rejected_missing_data`; per-code detail summarized in `raw_json`).
- `forecast_model_selection_decisions` ← `forecast_reconciliation_by_budget_code.jsonl`
  `contributions[]` aggregated per method (mean `effective_weight`). These tables are keyed
  `UNIQUE(run_id, method)`, so the projection is a deliberate project-level rollup.

## Deferred (no clean source this phase)

- `forecast_output_commitment_exposure` — commitment is consumed as input evidence, never emitted
  as a per-row output.
- `forecast_output_schedule_phasing` — the source emits month **weights**, not phased **amounts**;
  needs a weight × final-cost allocation (a later slice).
- `forecast_operator_assumptions` / `forecast_required_assumptions` — require the operator UI.

## Consequences

- The projection layer now fills 4 more output tables and 2 decision-support tables; a future live
  cutover populates the broader picture. No behavioral change to live reads; no live write.
- `written`/`counts` from the output projector now report all output tables (extra keys at 0 when
  their package is omitted); the Phase 2a tests were adjusted from exact-dict to subset assertions
  to reflect this — behavior is unchanged when no coverage package is passed.
- Relaxed the stale exact-version assert in `test_migrator_v63_forecast_outputs.py`
  (`== 63` → `>= 63`) that the concurrent schedule version bumps (now V67) had left red.

## Verification

- `tests/test_forecast_output_coverage.py` and `tests/test_forecast_decision_support_coverage.py`
  (plan/dry-run/fail-closed-live/apply+parity/idempotent; per-method aggregation correctness).
- Existing `test_forecast_output_projection_phase2a.py` / `test_forecast_decision_support_phase2b.py`
  still pass (optional package args default off). Ruff clean on the touched modules.
