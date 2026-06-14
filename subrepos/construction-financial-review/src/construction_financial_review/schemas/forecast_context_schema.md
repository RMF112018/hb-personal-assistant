# Forecast context package — schema reference

Master, agent-ingestible context that reconciles BudgetDetails, CostEntries, owner pay-apps, and
Procore subcontractor pay-apps. BudgetDetails is the master budget-code universe (127 keys); keys are
`sub_job.cost_code.category` (e.g. `1000.15-16-110.SUB`).

## canonical/
- `budget_codes.jsonl` (127) — master budget rows (amounts, tiers, descriptions).
- `cost_entries.jsonl` — accounting actual-cost truth; `actual_period_bucket` ∈
  {through_may_2026, june_2026_to_date, after_june_2026, undated}.
- `monthly_actuals_by_budget_code.jsonl`, `owner_pay_app_line_items_mapped.jsonl`,
  `owner_pay_app_totals.jsonl`, `procore_subcontractor_payment_app_headers.jsonl`,
  `procore_subcontractor_payment_app_line_items_mapped.jsonl`,
  `procore_latest_subcontractor_invoice_by_budget_code.jsonl`, `procore_commitments.jsonl`.

## mapping/
Deterministic mapping decisions, ambiguous candidates, unmapped rows, owner cost-code family crosswalk,
enriched forecast mapping template. No fuzzy matching.

## summaries/
- `budget_code_forecast_context.jsonl` (127) — the primary per-budget-code context (budget_amounts,
  actuals, owner_pay_app, procore_subcontractor_pay_apps, commitments, flags).
- `project_forecast_context.json`, `mapping_coverage_summary.json`, `data_gap_register.json`,
  `cost_code_rollup_forecast_context.jsonl`.

## audit/
Source validation reports + manifests, `safety_scan_report.json`, `reconciliation_report.json`.

Money fields are 2-decimal strings (or null); `budget_amounts.*` are source numbers. Conclusion:
`forecast_context_ready_with_mapping_gaps`.
