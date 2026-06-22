# Comprehensive Integrated Forecast Package — Schema

Money is Decimal-string (2dp); weights/scores are 4dp Decimal strings. Integrated outputs are ADVISORY (human-acceptance pending); they consume accepted package OUTPUT rows and never mutate them.

## Key files
- `integrated_forecast_by_budget_code.jsonl` — master per-code row: actual floor, accepted vs integrated final cost + CTC, history final-cost weight (frequency final-cost weight = 0), evidence-family disposition, the six `*_consumption_status` fields, human-acceptance fields.
- `integrated_evidence_registry_by_budget_code.jsonl` — every normalized evidence item with lineage (`source_package_type/path/file/row_id`), `evidence_family`, `independence_group`, support flags, contradiction score.
- `integrated_evidence_weights_by_budget_code.jsonl` — bounded, de-duplicated weights + accept/downgrade/reject reason codes per code.
- `integrated_final_cost_recommendations.jsonl` — accepted base + bounded history adjustment, floored at actuals, never capped.
- `integrated_monthly_forecast_by_budget_code.jsonl` / `integrated_monthly_project_forecast.jsonl` — integrated phasing with six source shares (cost_entry/invoice/schedule/history_shape/frequency/fallback); reconciles to integrated CTC per code and project total.
- `integrated_probability_by_budget_code.jsonl` / `integrated_probability_project_summary.json` — deterministic adjustment of the accepted band (`probability_method = accepted_distribution_deterministic_adjustment`); floored at actuals; never capped.
- `integrated_risk_register.jsonl`, `integrated_human_review_queue.jsonl`, `integrated_change_explanation.jsonl`, `evidence_conflict_register.jsonl` (7 conflict classes), `model_package_inventory.json`, `project_comprehensive_forecast_summary.json`, `top_*`.
- `audit/*` — evidence_registry, evidence_weighting (no-double-count), history_consumption, frequency_consumption, monthly_reconciliation (per-code + project), probability_adjustment (deterministic, non-MC), no_upper_cap, actuals_floor, model_evidence_completeness_matrix, source_hashes_before_after, safety_scan. `llm/*` advisory only, excluded from determinism.

## Rules
- CostEntries/Sage incurred cost is the only actual-cost source; actual cost to date is the only hard floor; NO evidence is ever a hard cap.
- Accepted intelligence is the base final cost; advisory evidence is bounded + contradiction-collapsed with explicit reason codes; independence groups prevent double-counting.
- Cost-frequency shapes monthly timing + timing-risk only — never final cost by itself.
- Probability is a DETERMINISTIC transform of the accepted package, not a fresh Monte Carlo.
- Every posture-changing row carries human-acceptance fields (default pending).
- Deterministic: same frozen stamp + same input packages => byte-identical quantitative core.
