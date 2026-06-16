# Forecast analysis package — schema reference

Per-budget-code forecast recommendations for human review. Recommendations derive from accounting
actuals; pay-app values are evidence only.

## forecast_recommendations_by_budget_code.jsonl (127)
Key fields: `budget_amount` (= revised_budget), `current_projected_cost` (= projected_costs), actuals
(all/through-May/June), owner + Procore latest evidence, `evidence_depth`, `forecast_action`
{hold_current_forecast, increase_forecast, decrease_forecast, review_required, mapping_required,
insufficient_evidence}, `recommended_forecast_adjustment`, `recommended_projected_cost`,
`recommended_cost_to_complete`, `confidence` {high, medium, low, none}, `risk_flags`, `review_notes`.

Rules: materiality = $25,000 AND 10%. When actuals exceed projected cost →
`increase_forecast`, `recommended_projected_cost = actual_cost_all_source_to_date`,
`recommended_forecast_adjustment = actual − projected` (floor-to-actuals; absolute precedence).
Decrease only when fully gated. Actuals-only holds are `medium` unless no-exposure is proven.

## Other files
`evidence_alignment_by_budget_code.jsonl`, `forecast_risk_register.jsonl`,
`manual_mapping_review_items.jsonl`, `data_quality_warnings.jsonl`, `confidence_rollup.json`,
`summaries/{project_forecast_analysis, top_forecast_movements, top_review_items}.json`,
`summaries/{division_summary, category_summary}.jsonl`, `audit/*`. Conclusion:
`forecast_analysis_ready_with_review_items`.
