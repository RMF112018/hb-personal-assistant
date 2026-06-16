# Workflow 11 — Forecast History-Informed (historical-forecast-assumption evidence)

Additive evidence layer: mines prior cash-flow + GC/GR forecasts and validates each against
CostEntries actuals. It validates/informs — it does not change — the accepted forecast packages.

## Inputs (under the Tropical 2026-June data root)

- **Historical** (fixed dir names): `cash_flow_forecast_history_json_package/`,
  `gcgr_forecast_history_json_package/` — prior forecast snapshots (read-only; never mutated).
- **Context** — `forecast_context_package_tropical_*`: `canonical/budget_codes.jsonl` (the 127-code
  mapping authority) + `summaries/budget_code_forecast_context.jsonl` (actuals truth + budget amounts).
- **Intelligence / Monthly / Probability** — latest accepted packages (recommendations, trend,
  schedule, monthly basis/shares, sigma + overrun probability). Read-only.
- Local DB read-only inventory only.

## Run

```bash
cd subrepos/construction-financial-review
# Deterministic (no model):
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-history-informed \
  --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fhi_a
# Optional advisory local-Ollama narratives (never numeric; excluded from determinism):
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-history-informed --project tropical --with-llm
```
Note: the CLI runs under the repo `.venv` (numpy/scipy live there). Determinism: two `--frozen-stamp`
runs into separate `--out-root` dirs, then `diff -rq` — the quantitative data files **and** the analytic
audit files are byte-identical (differences only in `llm/`, the run-metadata files, and environmental
audit files that carry generated paths/timestamps/DB-schema-counts).

## Output package `forecast_history_informed_package_tropical_<stamp>/`

Per code: `historical_forecast_signal_by_budget_code.jsonl` (pattern + curve shape + scores),
`historical_forecast_monthly_curve_by_budget_code.jsonl`,
`historical_vs_actual_validation_by_budget_code.jsonl` (prior forecast vs CostEntries actuals),
`historical_assumption_reliability_by_budget_code.jsonl`,
`history_informed_forecast_adjustment_by_budget_code.jsonl` (advisory, do-not-auto-apply),
`history_informed_monthly_distribution_by_budget_code.jsonl`,
`history_informed_probability_adjustments_by_budget_code.jsonl`. Rollups:
`forecast_history_informed_recommendations.jsonl`, `project_history_informed_summary.json`,
`top_history_validated_assumptions.json`, `top_history_contradicted_assumptions.json`,
`top_increasing_historical_exposures.json`, `top_zero_remaining_candidates.json`,
`historical_forecast_data_quality_warnings.jsonl`. Plus `README`, `SCHEMA`, `manifest.json`,
`input_inventory.json`, `validation_report.json`, `audit/*` (history_mapping_audit incl. watch-code
presence, history_vs_actual_reconciliation, history_curve_shape_audit, gcgr_proportionality_audit,
source_hashes_before_after, db_inventory, safety_scan_report, historical_source_files_used), advisory
`llm/*`.

## How a reviewer reads it

- **`project_history_informed_summary.json`** — counts by mapping status, pattern class, validation
  class, reliability band; zero-remaining validated candidates; contradicted assumptions.
- **`historical_vs_actual_validation_by_budget_code.jsonl`** — did the prior assumption hold up against
  CostEntries? Watch for `contradicted_escalation` (actuals overran a stale forecast) and
  `validated_zero_inactive` (a prior zero confirmed by real inactivity — only when post-snapshot
  inactive months meet the config threshold `actual_inactivity_months_for_zero_support`; otherwise
  `inconclusive_zero`, and unexpected material actuals → `contradicted_unexpected_actuals`).
- **`history_informed_forecast_adjustment_by_budget_code.jsonl`** — advisory nudge toward the prior
  EAC, weighted by reliability, floored at actuals, never capped (`do_not_auto_apply`).
- **`audit/gcgr_proportionality_audit.json`** — the GC-fee (20-18-110) taper hypothesis: reported
  `confirmed` only when the fee genuinely tracks 15-* cost-of-work progress with a stable implied total.
- **`audit/history_mapping_audit.json`** — watch-code presence (15-16-100 / 03-01-025 / 20-18-110) and
  every cost-code mapping decision (unique / rollup / unmapped).

## Guardrails

Historical forecast is prior-assumption evidence — never actual cost, never a hard cap. CostEntries/Sage
incurred cost is the primary reality check; actual cost to date is the only hard floor; nothing is
capped above any reference. Cost-code-only history maps to canonical BudgetDetails only (multi-category
codes are rollups, never force-mapped; absent codes reported explicitly; duplicates keep lineage). All
outputs are advisory (`do_not_auto_apply`, `requires_human_acceptance`); no accepted package is mutated.
Deterministic given a frozen stamp. No source/Excel/SQLite/accepted-package mutation; no live external
calls (localhost Ollama only under `--with-llm`). `audit/source_hashes_before_after.json` proves the
historical packages were not mutated. No commit unless instructed.
