# Forecast Probabilistic Validation Package — Schema

Money is Decimal-string (2dp); probabilities/ratios are 4dp Decimal strings in [0,1]. Simulation internals are float64; values are quantized at the JSON boundary.

## Key files
- `probabilistic_final_cost_by_budget_code.jsonl` — per code: P10/P50/P80/P90/P95, mean, std, deterministic recommended/worst, and P(exceeds current projected / revised budget / recommended).
- `code_overrun_probabilities.jsonl` — per code: overrun probabilities + expected and conditional overrun vs current projected cost.
- `downside_exposure_ranking.jsonl` / `top_downside_drivers.json` — per-code co-tail contribution to the project P90 (which codes drive the bad case), ranked.
- `probabilistic_monthly_by_budget_code.jsonl` / `probabilistic_monthly_project_forecast.jsonl` / `monthly_risk_ranking.json` — simulated monthly P50/P90 cost and cumulative overrun probability; months ranked by cost and by overrun risk.
- `probabilistic_project_summary.json` — project P10..P95, mean/std, VaR/CVaR, probability the recommended/worst-credible/current-projected/revised-budget totals are met or exceeded, where each falls as a simulated percentile, the systemic variance share, project-level revised-budget overrun (`probability_project_exceeds_revised_budget_total`, `expected_project_overrun_vs_revised_budget_total`, P80/P90/P95 overrun vs revised budget), and a `window_reconciliation` block (accounting actual + deterministic prior-month forecast + simulated window CTC = simulated final).
- `sensitivity_analysis.json` — one-at-a-time ΔP90 by spread source (authoritative), Spearman code drivers, and systemic-vs-idiosyncratic variance share.
- `probabilistic_backtest_results.json` — PIT + coverage calibration: predictive shifted-lognormal-on-CTC at each as-of point (40/60/80% owner progress) vs realized final on the near-complete cohort (coverage at P10-P90 / P05-P95, PIT uniformity KS, per-point detail), with a dispersion-adequacy ratio vs historical MAPE as a secondary view; honest about the small cohort.
- `simulation_inputs_by_budget_code.jsonl` — the calibrated mu/sigma + each sigma source per code (full audit of how each draw was parameterized), plus the carry-forward breakdown (`accounting_actual_cost_to_date`, `deterministic_prior_forecast_before_probability_window`, `probability_window_recommended/worst_credible_cost_to_complete`).
- `calibration_summary.json` — methodology, parameters, numpy/scipy versions, seed, runs.

## Compatibility aliases (additive; canonical files preserved, first-class outputs)
- `simulation_results_project.json` = `probabilistic_project_summary.json`; `simulation_results_by_budget_code.jsonl` = `probabilistic_final_cost_by_budget_code.jsonl`; `simulation_results_by_month.jsonl` = `probabilistic_monthly_project_forecast.jsonl` (PROJECT-month totals, distinct from the per-code-month canonical file).
- `probabilistic_overrun_risk_register.jsonl` — MATERIAL overrun rows only: a code is included iff P(exceeds current projected) >= 0.20 AND (expected overrun >= $25,000 OR >= 5% of current projected). Each row carries `materiality_threshold_basis`. Not merely all codes with expected_overrun > 0.
- `budget_code_sensitivity.jsonl` — per code: co-tail downside contribution to project P90 + Spearman driver. `division_sensitivity.jsonl` / `owner_scope_sensitivity.jsonl` — risk contribution aggregated by division / authoritative owner SOV scope (owner-scope falls back to a single explicit unavailable row only when no crosswalk assignment resolves).
- `audit/no_upper_cap_audit.json` — one record per code: distribution family, actual floor applied, upper_cap_applied (false), upper_cap_source (null), reference_values_reported_only, P95-vs-current-projected/revised-budget/worst-credible, validation_status.
- `audit/*` — db_inventory (schema+counts only), source_files_used, safety_scan_report, no_upper_cap_audit. `validation_report.json` carries a `determinism` block. `llm/*` advisory only, excluded from determinism.

## Rules
- Actual cost to date is the ONLY hard floor; simulated finals are never capped at ERP projected / revised budget / committed / owner SOV / Procore pay-app / prior model output.
- The deterministic recommended final cost is the per-code simulated P50 by construction.
- Subcontractor invoice & owner pay-app values are progress/exposure/timing evidence, never actuals. The local LLM produces advisory text only — no numeric simulation result.
- A later `--forecast-start-month` validates only the REMAINING window: the prior-month deterministic recommended/worst CTC is carried forward as a fixed addend (never reallocated into the shortened window, never treated as actual cost). Simulated final reconciles to accounting actual + deterministic prior-month forecast + simulated window CTC.
- Deterministic: same seed + same frozen stamp => byte-identical quantitative core (canonical + alias files).
