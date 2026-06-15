# Forecast Staffing Plan — Architecture

Operator-supplied planned-staffing forecast layer. Ingests the extracted staffing JSON package
(`staffing_json_package_tropical_*`) as an explicit planned staffing source and turns it into a
deterministic, fail-closed forecast package that feeds the cost-frequency, monthly, and comprehensive
slices. Module: `src/construction_financial_review/forecast_staffing_plan/`. CLI: `forecast-staffing-plan`.

## Why

The model previously projected future staffing only by inferring cadence/trend from historical
CostEntries. When an explicit operator staffing schedule exists, it is a stronger forward-looking signal.
This slice consumes that schedule for **future months only** — it never overwrites, reinterprets, or
mutates historical actuals, the source Excel, the extracted staffing package, accepted packages, or
SQLite, and makes no live external calls.

## LAB-only mapping (operator-directed)

The staffing workbook carries `cost_code` only (no `budget_code_key`, no LAB/LBN suffix). For each source
cost code the resolver (`mapping.py`):

1. Builds the canonical role/description family for the cost code (`.LAB`/`.LBN`/`.MAT`, role = the middle
   token of `budget_code_description`, e.g. `SUPERINTENDENT 2`).
2. Requires a **unique** resolution — exactly one role-family stem AND exactly one `.LAB` key.
3. Applies numeric staffing dollars **only** to that `.LAB` key (allocation 1.0000) AND only when an
   operator override row (`config/forecast_staffing/<project>/staffing_budget_code_mapping.jsonl`) with
   `acceptance_status: accepted` targets that exact `.LAB` key.
4. Records the whole `.LAB`/`.LBN`/`.MAT` family as **date-context targets** (timing/review/closeout/
   conflict context only — no numeric dollars).

Fail-closed statuses: `ambiguous_multiple_lab_or_family`, `override_target_not_canonical` (invented),
`override_target_disagrees_with_resolver` (mismatch), `unmapped_no_canonical_match`,
`resolved_unique_lab_pending_acceptance`. No LAB/LBN/MAT split is ever fabricated.

## Dual forecast (no hidden stale CTC)

The defining rule: timing-only reconciliation must never mask a stale or excessive accepted
cost-to-complete. For every applied `.LAB` code `apply.py` emits BOTH:

- `staffing_plan_implied_monthly_forecast` — the operator plan dollars by month (sums to the plan total);
- `current_ctc_reconciled_monthly_forecast` — the accepted CTC distributed over the SAME plan month-shape
  (sums to the accepted CTC),

plus the **bridge**: `actual_cost_to_date`, `current_accepted_final_cost` / `current_accepted_cost_to_complete`,
`staffing_plan_implied_remaining_cost`, `staffing_plan_implied_final_cost = actual + implied_remaining`,
`delta_vs_current_accepted_ctc`, `delta_vs_current_accepted_final_cost`, and
`requires_operator_acceptance` (true when the difference is material at the project materiality threshold).
Plan-driven final-cost changes stay **advisory** until an explicit operator-acceptance mechanism accepts
them. Actuals are the only floor (`implied_final >= actual`); no reference is ever a cap.

## Conflicts

`staffing_plan_conflicts_with_current_accepted_ctc` (accepted CTC materially above or below plan-implied
remaining), `staffing_plan_changes_final_cost_materially`, `staffing_plan_conflicts_with_recent_actual_burn`,
`staffing_plan_conflicts_with_cost_frequency` (plan supersedes cadence; cadence kept diagnostic),
`staffing_plan_ends_before_forecast_horizon`, `staffing_plan_monthly_total_reconciliation_failure`,
`staffing_plan_unmapped_cost_code`, `staffing_plan_ambiguous_mapping`.

## Downstream integration

- **forecast_cost_frequency** — annotates each mapped `.LAB` code: `forward_looking_timing_source =
  operator_staffing_plan`, `staffing_plan_supersedes_cadence_for_future_months = true`, cadence
  classification preserved for diagnostics (`audit/staffing_plan_consumption.json`).
- **forecast_monthly** — `monthly_reconcile` carves a staffing-plan timing share (before schedule/
  frequency/cost) for mapped codes; the monthly forecast stays reconciled to the accepted CTC, and each
  row discloses `staffing_plan_raw/applied/implied_amount`, `staffing_plan_weight`,
  `ctc_reconciliation_applied`, `staffing_plan_is_numeric_driver`, `staffing_plan_is_recommendation_only`,
  `operator_acceptance_required` (`audit/staffing_plan_applied.json`).
- **forecast_comprehensive** — `operator_staffing_plan` evidence family (independence group
  `staffing_plan`), per-code bridge attached to `per_code`, staffing conflicts surfaced into the
  integrated conflict register + review queue; advisory (always `requires_human_acceptance`,
  `do_not_auto_apply`).

## Determinism + validation

Deterministic under a frozen stamp (Decimal money; byte-identical quantitative core + audits). Validation
fails closed if: the source package is missing/invalid, file hashes do not match, parsed monthly totals do
not reconcile to source totals, an allocation share exceeds 1.0, an accepted mapping targets a
non-canonical key, an ambiguous/unmapped code is applied, the implied final falls below actuals, a hidden
cap is applied, monthly reconciliation fails, or output is nondeterministic.

## Config

`config/projects/<project>.json` → `forecast_staffing_plan` block (`enabled`, `package_glob`,
`mapping_file`, `require_mapping_acceptance`, `fail_on_ambiguous_mapping`, `zero_after_staffing_plan_end`,
`preserve_actuals_floor`, `allow_final_cost_recommendation`, `materiality_threshold`). Override file:
`config/forecast_staffing/<project>/staffing_budget_code_mapping.jsonl`.
