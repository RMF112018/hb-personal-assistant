# Stage 2 — Forecast analysis package (v1)

**Generator:** `src/construction_financial_review/analysis/generate_forecast_analysis_package.py`.

Consumes the forecast context package and produces per-budget-code forecast recommendations, a risk
register, evidence alignment, manual-review items, and summaries — **for human review only**. No
workbook/source mutation; pay-app values are evidence, never actual cost.

Approved rules: `budget_amount = revised_budget`, `current_projected_cost = projected_costs`,
materiality $25,000 AND 10%, floor-to-actuals increases (absolute precedence), fully-gated decreases,
actuals-only holds `medium` unless no-exposure proven.

Output: `forecast_analysis_package_tropical_<stamp>/`. Conclusion:
`forecast_analysis_ready_with_review_items`. See `schemas/forecast_analysis_schema.md`.

> Note: v1 compared owner vs Procore at the individual budget-code level, which over-flagged structural
> owner-summary-vs-subcontract differences. Stages 3–5 correct this.
