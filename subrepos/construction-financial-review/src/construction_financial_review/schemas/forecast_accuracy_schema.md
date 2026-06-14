# Forecast Accuracy Package — Schema Reference

Output of `construction_financial_review.forecast_accuracy.generate_forecast_accuracy_package`.
Money is Decimal-string (2dp); JSONL sorted by `budget_code_key`; **every EAC ≥ actual-to-date**.

## Files

| File | Grain | Notes |
|------|-------|-------|
| `signal_bundle_by_budget_code.jsonl` | 127 | actuals/monthly burn + volatility, all budget amounts, owner/procore/commitment, schedule rollup, two horizons, `evidence_depth` |
| `eac_estimates_by_budget_code.jsonl` | 127 | per code: list of estimates `{method, source, applicable, eac, etc, floored_to_actuals, reliability, inputs, note}` |
| `forecast_reconciliation_by_budget_code.jsonl` | 127 | `model_reconciled_eac`, `model_recommended_projected_cost` (floored, advisory), `model_eac_low/high/median`, `model_divergence`, `model_vs_erp_gap`, `contributions`, `requires_human_acceptance` |
| `forecast_confidence_by_budget_code.jsonl` | 127 | `calibrated_confidence` (0–1), `confidence_band`, `components`, `confidence_drivers` |
| `forecast_adequacy_by_budget_code.jsonl` | 127 | `forecast_adequacy` (likely_low/adequate/likely_high/indeterminate), `adequacy_severity`, gap/% |
| `forecast_accuracy_recommendations.jsonl` | 127 | authoritative rule-based action + advisory model number + adequacy + confidence + `requires_human_acceptance` |
| `backtest/backtest_accuracy_by_method.json` | — | per-method MAPE/bias, `calibration_weights`, methodology |
| `backtest/backtest_detail.jsonl` | cohort | per-code as-of reconstruction + predicted EAC + APE/bias |
| `llm/forecast_narratives.jsonl` | subset | advisory; `source` = `ollama:<model>` or `deterministic_template`; never a number |
| `llm/llm_receipts.jsonl` | subset | hash-only (`model`, `status`, `fallback_used`, `input_facts_hash`, `output_hash`, `safety_passed`) |
| `summaries/` | — | `project_forecast_accuracy_summary.json`, `top_forecast_adequacy_gaps.json`, review/exec `.md` |
| `audit/` | — | `source_files_used.json`, `calibration_snapshot.json`, `safety_scan_report.json` |
| `manifest.json`, `input_inventory.json`, `validation_report.json` | — | per-file sha256, generation metadata (incl. ollama status/model), validation gate |

## Validation checks (`validation_report.json.checks`)

`output_files_parse`, `one_row_per_canonical_key`, `model_recommended_floored_to_actuals`,
`every_estimate_floored_to_actuals`, `confidence_in_unit_interval`, `backtest_cohort_present`,
`safety_scan_passed`. `passed` = AND of all checks.

## Estimators (independent unless noted)

`burn_rate` (gated off near-complete), `owner_percent_complete`, `commitment_floor`, `schedule_etc`,
`cpi_proxy`; ERP baselines `baseline_projected`, `baseline_erp_eac` (`source=erp`, comparison only).
Reconciliation weight = reliability × backtest calibration multiplier.
