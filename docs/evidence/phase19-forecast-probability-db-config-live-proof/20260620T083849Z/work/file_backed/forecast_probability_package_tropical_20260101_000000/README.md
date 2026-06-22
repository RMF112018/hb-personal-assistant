# forecast_probability_package_tropical (20260101_000000)

Probabilistic VALIDATION of the accepted deterministic forecast for Tropical World Nursery (tropical / 23-435-01 / 2026-June). Monte Carlo stress-test (10000 runs, seed 20260614); it does not replace the deterministic forecast.

- Project final cost: P10 57023554.14 · P50 60698821.65 · P80 65128273.00 · P90 68990479.43 · P95 73163046.29 (mean 62197835.03).
- Deterministic recommended 60953919.06 sits at simulated percentile 52.66; worst-credible 61773528.16 at percentile 59.56.
- P(final ≥ recommended) = 0.4734; P(final > current projected total) = 0.9859.
- Revised budget total 55656959.71: P(final > revised budget) = 0.9817; expected overrun vs revised budget 6549242.24 (P90 13333519.72).
- VaR(P90) 68990479.43; CVaR(P90) 75632953.19; systemic variance share 0.4949.

**Method.** Per code, cost-to-complete is a lognormal whose median equals the deterministic recommended cost-to-complete (recommended = per-code P50) and whose high quantile maps to the worst-credible cost-to-complete; spread is widened by burn volatility, backtest MAPE, model divergence and low confidence; overrun-existence confidence fattens the right tail. Codes are linked by a one-factor Gaussian copula. Actual cost to date is the ONLY floor; nothing is capped above any reference. Subcontractor invoice & owner pay-app values are evidence only.

See `probabilistic_final_cost_by_budget_code.jsonl` (per-code P10..P95 + overrun probabilities), `downside_exposure_ranking.jsonl` (codes driving the project P90), `probabilistic_monthly_project_forecast.jsonl` + `monthly_risk_ranking.json` (timing), `sensitivity_analysis.json` (which assumptions matter), and `probabilistic_backtest_results.json` (PIT + coverage calibration). Quant core is deterministic (validation_report.json `determinism`); `llm/` narratives are advisory and excluded.

**Compatibility aliases** (additive; canonical files preserved): `simulation_results_project.json`, `simulation_results_by_budget_code.jsonl`, `simulation_results_by_month.jsonl` (project-month), `probabilistic_overrun_risk_register.jsonl` (material rows only — probability + dollar/pct gate), `budget_code_sensitivity.jsonl`, `division_sensitivity.jsonl`, `owner_scope_sensitivity.jsonl`. `audit/no_upper_cap_audit.json` proves, per code, that nothing is capped above actuals against any reference (ERP / revised budget / committed / owner SOV / pay-app / prior output).
