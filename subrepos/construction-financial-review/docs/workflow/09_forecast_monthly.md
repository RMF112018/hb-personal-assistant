# Workflow 09 — Forecast Monthly (time-phased month-by-month forecast)

Time-phases the accepted forecast-intelligence final-cost package across the remaining forecast months.
Additive; nothing in the earlier pipeline changes.

## Inputs (latest packages under the Tropical 2026-June data root)

- **Anchor** — `forecast_accuracy_next_package_tropical_*` (recommended/worst cost-to-complete + final
  costs, current projected, revised budget, overrun flags, confidence, schedule association).
- **CostEntries monthly** — context pkg `canonical/monthly_actuals_by_budget_code.jsonl` (+ embedded
  `actuals.monthly_actuals`; June = `june_2026_to_date` partial).
- **Subcontractor invoice** — context pkg
  `canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl` (28 monthly periods, 42 codes).
- **Schedule** — `project_schedule_json_package` (latest activity finish 2026-11-03) +
  `schedule_integrated_forecast_package_*`. Local DB read-only inventory only.

## Run

```bash
cd subrepos/construction-financial-review
# Deterministic mock (no model), default start = system month:
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-monthly \
  --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fm_a
# Override the start month:
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-monthly \
  --project tropical --forecast-start-month 2026-08
# Delivered run with live local-Ollama advisory narratives:
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-monthly --project tropical --with-llm
```

Determinism: two `--frozen-stamp` mock runs into separate `--out-root` dirs, then `diff -rq`
(identical except `llm/`). The package also self-checks determinism (see `validation_report.json`
`determinism` block).

## Output package `forecast_monthly_package_tropical_<stamp>/`

Per-code × month (127 × N): `monthly_forecast_by_budget_code.jsonl`. Rollups:
`monthly_forecast_by_{owner_scope,division}.jsonl`, `monthly_project_forecast.jsonl`,
`project_monthly_cashflow_summary.json`. Evidence: `cost_entry_monthly_trends_*`,
`subcontractor_invoice_monthly_trends_*`, `schedule_monthly_phasing_*`,
`remaining_work_monthly_distribution_*`. Risk: `monthly_overrun_risk_register.jsonl`,
`top_monthly_overruns.json`. Confidence/change: `monthly_forecast_confidence_*`,
`monthly_forecast_change_explanation.jsonl`. Accuracy: `monthly_backtest_results.json`,
`monthly_calibration_summary.json`. Plus `README`, `SCHEMA`, `manifest.json`, `input_inventory.json`,
`validation_report.json`, `data_quality_warnings.jsonl`, `audit/*`, advisory `llm/*`.

## How a reviewer reads it

- **`monthly_project_forecast.jsonl`** — per-month spend and cumulative, active codes, and two overrun
  counts: `number_of_cumulative_codes_exceeding_current_projected_cost` (any crossing by that month) and
  `number_of_material_projected_overrun_codes` (only crossings meeting the $25k AND 10% materiality
  rule; always ≤ the cumulative count).
- **`top_monthly_overruns.json` / `monthly_overrun_risk_register.jsonl`** — the month each code first
  exceeds current projected (and revised budget), amount, severity, and split confidence.
- **`monthly_forecast_by_budget_code.jsonl`** — `recommended_month_cost` vs `worst_credible_month_cost`,
  cumulative + remaining, `monthly_forecast_basis`, both trend signals, and the three split confidences.
- **`remaining_work_monthly_distribution_*`** — the blended monthly weights and the source shares
  (cost_entries / invoice / schedule / flat) behind each code's phasing.
- **`monthly_calibration_summary.json`** — WAPE (primary) + MAE + MAPE; whether adding invoice timing
  improved monthly phasing over CostEntries-only (with stated schedule/cohort limitations).

## Guardrails

Subcontractor invoice & owner pay-app values are progress/exposure/timing evidence, never actuals.
Project-level schedule association is context only. Actuals the only hard floor; nothing capped at
ERP/budget/commitment/owner SOV/pay-app. Current month is day-aware (no double count). No
source/Excel/SQLite/external mutation (DB read-only). Every row requires human acceptance. No commit
unless instructed.
