# Mapping-discrepancy workpaper — schema reference

Explains each `owner_procore_mismatch` as a true progress discrepancy or a structural comparison
problem. Advisory only — does not modify the analysis package.

## Crosswalks
- `owner_sov_to_budget_code_crosswalk.jsonl` — owner SOV scope → BudgetDetails candidates.
- `procore_commitment_to_budget_code_crosswalk.jsonl` — Procore commitment/WBS → BudgetDetails.
- `owner_sov_to_procore_scope_crosswalk.jsonl` — owner scope ↔ Procore scope (+ synthetic procore_only).

## Classification
- `owner_procore_discrepancy_classification.jsonl` — `discrepancy_type` ∈ {scope_aggregation_difference,
  owner_sell_value_vs_subcontract_cost, timing_difference, owner_sov_placeholder_family,
  pcco_or_change_order_scope, deductive_change_order_credit, internal_or_non_subcontract_cost,
  missing_procore_commitment_scope, missing_owner_sov_scope, mapping_ambiguity, true_progress_discrepancy,
  no_discrepancy, unresolved}; `comparison_basis` ∈ {percent_complete, remaining_exposure,
  dollars_with_markup_caution, not_comparable}. `true_progress_discrepancy` requires a comparable basis
  (hard guard). MAT is not auto-internal (only LAB/LBN/OVH or clearly internal scope).

## Other
`budget_code_scope_reconciliation.jsonl`, `manual_crosswalk_review_items.jsonl`,
`discrepancy_resolution_summary.json`, `owner_procore_mismatch_recalibration_inputs.jsonl`, `audit/*`.
Conclusion: `mapping_discrepancy_workpaper_ready_with_unresolved_items`.
