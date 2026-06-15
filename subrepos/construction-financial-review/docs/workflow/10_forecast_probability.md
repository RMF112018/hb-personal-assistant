# Workflow 10 — Forecast Probability (probabilistic validation)

Monte Carlo stress-test of the accepted deterministic forecast. Additive; it validates — it does not
change — the `forecast_intelligence` and `forecast_monthly` outputs. First slice to use numpy/scipy.

## Inputs (latest accepted packages under the Tropical 2026-June data root)

- **Anchor** — `forecast_accuracy_next_package_tropical_*`: per-code recommended/worst cost-to-complete
  + final costs, current projected, revised budget, model divergence, confidence, overrun-existence
  confidence; `model_backtest_results.json` (method MAPE + cohort size).
- **Monthly** — `forecast_monthly_package_tropical_*`: `remaining_work_monthly_distribution_*`
  (deterministic monthly weights), `monthly_forecast_confidence_*` (monthly distribution score),
  `project_monthly_cashflow_summary.json` (project totals + forecast months).
- **Context** — `forecast_context_package_tropical_*`: owner pay-app history
  (`canonical/owner_pay_app_line_items_mapped.jsonl`) + per-code actuals
  (`summaries/budget_code_forecast_context.jsonl`), used read-only to reconstruct the near-complete
  cohort for the PIT/coverage backtest. The backtest degrades to `insufficient_cohort` if absent.
- Local DB read-only inventory only.

## Run

```bash
cd subrepos/construction-financial-review
# Install deps (numpy/scipy) once:
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/pip install -e .

# Deterministic mock (no model), default 10000 runs / seed 20260614:
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-probability \
  --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fp_a
# Fewer runs / a different seed / a later start month (validates only the REMAINING window —
# prior-month deterministic forecast is carried forward, not reallocated; see Guardrails):
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-probability \
  --project tropical --runs 5000 --seed 7 --forecast-start-month 2026-08
# Delivered run with live local-Ollama advisory narratives:
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-probability --project tropical --with-llm
```

Determinism: two `--frozen-stamp` + same `--seed` runs into separate `--out-root` dirs, then `diff -rq`
(identical except `llm/`, `audit/`, and the run-metadata files). The package also self-checks
determinism (see `validation_report.json` `determinism` block).

## Output package `forecast_probability_package_tropical_<stamp>/`

Per-code (127): `probabilistic_final_cost_by_budget_code.jsonl` (P10..P95 + overrun probabilities),
`code_overrun_probabilities.jsonl`, `downside_exposure_ranking.jsonl` + `top_downside_drivers.json`,
`simulation_inputs_by_budget_code.jsonl` (calibration audit + carry-forward breakdown). Monthly:
`probabilistic_monthly_by_budget_code.jsonl`, `probabilistic_monthly_project_forecast.jsonl`,
`monthly_risk_ranking.json`. Project: `probabilistic_project_summary.json` (now incl. project-level
revised-budget overrun probability + `window_reconciliation`). Diagnostics:
`sensitivity_analysis.json`, `probabilistic_backtest_results.json`, `calibration_summary.json`. Plus
`README`, `SCHEMA`, `manifest.json`, `input_inventory.json`, `validation_report.json`,
`data_quality_warnings.jsonl`, `audit/*` (incl. `no_upper_cap_audit.json`), advisory `llm/*`.

**Compatibility aliases** (additive; canonical files preserved): `simulation_results_project.json`,
`simulation_results_by_budget_code.jsonl`, `simulation_results_by_month.jsonl` (project-month),
`probabilistic_overrun_risk_register.jsonl` (material rows only — probability + dollar/percentage
threshold, with the basis recorded per row), `budget_code_sensitivity.jsonl`,
`division_sensitivity.jsonl`, `owner_scope_sensitivity.jsonl`.

## How a reviewer reads it

- **`probabilistic_project_summary.json`** — the headline: project P10/P50/P80/P90/P95, where the
  deterministic recommended / worst-credible / revised-budget totals fall as simulated percentiles, P(final ≥
  recommended), P(final > revised budget total) with expected + P80/P90/P95 overrun vs revised budget,
  VaR/CVaR at P90, the systemic variance share, and `window_reconciliation` (accounting actual +
  deterministic prior-month forecast + simulated window CTC = simulated final).
- **`probabilistic_final_cost_by_budget_code.jsonl`** — per-code P10..P95 and the probability each code
  exceeds current projected cost / revised budget / recommended final.
- **`downside_exposure_ranking.jsonl` / `top_downside_drivers.json`** — which codes drive the project
  P90 bad case (co-tail contribution).
- **`probabilistic_monthly_project_forecast.jsonl` / `monthly_risk_ranking.json`** — which months carry
  the most cost and the highest cumulative overrun probability.
- **`sensitivity_analysis.json`** — which assumption most moves the project P90 (one-at-a-time ΔP90),
  plus Spearman code drivers.
- **`probabilistic_backtest_results.json`** — PIT + coverage calibration: at 40/60/80% owner progress
  on the near-complete cohort, does the realized final land inside the predicted bands at the nominal
  rate? Reports `coverage_p10_p90` (nominal 0.80), `coverage_p05_p95` (nominal 0.90), `pit_mean`,
  KS uniformity, per-point detail, and a `calibration_verdict`; a dispersion-adequacy ratio vs
  historical MAPE is kept as a secondary view, with the small-cohort caveat.

## Guardrails

Actual cost to date is the only hard floor; simulated finals are never capped at ERP projected / revised
budget / committed / owner SOV / Procore pay-app / prior model output (proven per code in
`audit/no_upper_cap_audit.json`). The deterministic recommended is the per-code P50 by construction.
A later `--forecast-start-month` validates only the **remaining** window: prior-month deterministic
forecast is carried forward as a fixed addend, never reallocated into the shortened window and never
treated as actual cost (`window_reconciliation` shows the split; a validation gate fails on any full-CTC
reallocation). Subcontractor invoice & owner pay-app values are evidence only. The local LLM produces
advisory text only — no numeric simulation result. Deterministic given seed + frozen stamp. No
source/Excel/SQLite/external mutation (DB read-only). Probabilistic numbers are advisory and require
human acceptance. No commit unless instructed.
