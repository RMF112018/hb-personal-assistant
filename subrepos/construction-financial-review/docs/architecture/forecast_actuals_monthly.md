# Forecast Monthly Actuals Export — Architecture

A shared, additive **evidence/export contract**: every generated forecast package emits month-by-month
**actual incurred cost** for each canonical budget code, sourced **only** from CostEntries/Sage. It never
changes a forecast recommendation value, never mutates an actual, and is deterministic.

Shared module: `src/construction_financial_review/forecast_actuals/actuals_export.py`
(CSV helper added to `common/io.py` → `write_csv`, `csv.QUOTE_ALL`, `\n`, no BOM).

## Source of truth (CostEntries only)

Read **only** `context/canonical/monthly_actuals_by_budget_code.jsonl` (each row carries
`source: "CostEntries"`). `load_costentries_monthly()` asserts every row's `source == "CostEntries"`
and sets `contamination_ok = False` (excluding the row) for anything else. This structurally guarantees
owner/subcontractor pay-applications, prior forecasts, staffing plans, schedule data, and operator
controls are never treated as actuals. Per-key truth for reconciliation is
`actuals.actual_cost_all_source_to_date` from `summaries/budget_code_forecast_context.jsonl` (or the
accepted recommendation rows in `forecast_monthly`).

## Output files (seven, identical in every package)

- `actuals_monthly_by_budget_code.jsonl` — **dense**: one row per (canonical budget_code_key, month) on
  the contiguous actuals month axis. Months with no CostEntries activity emit `actual_cost: "0.00"`,
  `entry_count: 0`, `first/last_cost_entry_date: null`, but **`is_actual: true`** (no `month: null`
  sentinel). Fields: `project_key, budget_code_key, cost_code, cost_type, budget_code_description,
  month, actual_cost, entry_count, first_cost_entry_date, last_cost_entry_date, actual_source
  ("CostEntries"), actual_source_role ("accounting_truth"), is_actual`.
- `actuals_monthly_by_cost_code.jsonl` — dense per (cost_code, month) rollup.
- `actuals_monthly_project_total.jsonl` — one row per month (project total + entry_count).
- `actuals_to_forecast_bridge_by_budget_code.jsonl` — one row per canonical key: `actual_cost_to_date`,
  `exported_monthly_actuals_total`, `reconciliation_difference`, `latest_actual_month`,
  `last_nonzero_actual_month`, `forecast_start_month`, `remaining_forecast_cost_to_complete` (when
  available), `reconciliation_status`, `reconciles`.
- `actuals_monthly_by_budget_code.csv` — matrix: one row per code (sorted by `budget_code_key`), columns
  `budget_code_key,cost_code,cost_type,budget_code_description,<month…>` (ascending, first→latest actual
  month), missing cells `0.00`.
- `actuals_monthly_by_cost_code.csv` — matrix sorted by `cost_code`; columns
  `cost_code,cost_code_description,<month…>`.
- `audit/actuals_monthly_reconciliation_audit.json` — per-key Σ-months vs actual-cost-to-date; cost-code
  rollup == Σ its budget keys; project total == Σ all keys == Σ all months; variance lists; cent
  tolerance.

Money is Decimal-string (2dp) throughout (no floats). Rows and month columns are deterministically
ordered → byte-identical under a frozen stamp.

## Recommendation-row fields (forecast_accuracy_next only)

`forecast_intelligence` (which produces `forecast_accuracy_next_package_*`) adds five **additive** fields
to each `forecast_recommendations_by_budget_code.jsonl` row — `actuals_monthly_total_to_date`,
`actuals_latest_month`, `actuals_latest_month_amount`, `actuals_month_count_nonzero`,
`actuals_last_nonzero_month`. Recommendation values are **unchanged**.

## Packages updated + posture

`forecast_intelligence` (forecast_accuracy_next), `forecast_monthly`, `forecast_probability`, and
`forecast_comprehensive` each build the seven files from the discovered context canonical and include
them in their `DATA_FILES` (write + determinism byte-diff), manifest hashes, and validation gates.
`forecast_comprehensive` **re-emits** them so the final package is self-contained. Every package emits
byte-identical actuals from the same CostEntries source.

## Validation gates (each package, fail-closed)

`actuals_export.validation_gates()` →
`actuals_monthly_by_budget_code_jsonl_present`, `actuals_monthly_by_budget_code_csv_present`,
`all_canonical_keys_in_actuals`, `no_non_canonical_keys_in_actuals`,
`actuals_reconcile_to_actual_cost_to_date`, `actuals_project_total_reconciles`,
`actuals_source_is_costentries_only`. Each package folds these into its `validation_report.json` checks.

## Tropical (2026-June) facts

127 canonical budget codes; actuals month axis **2023-06 → 2026-06** (37 months); dense
budget-code JSONL = **127 × 37 = 4,699 rows**; budget-code CSV = 127 rows × 41 columns; project actuals
total **$47,559,197.97**; all 127 codes reconcile to `actual_cost_all_source_to_date` (zero variance).
