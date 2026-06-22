| Area | Current evidence | Remediation disposition |
|---|---|---|
| `company_id` / `company_id_hash` | Sync run company context exists; raw landing company columns are null | Patch run-context propagation, but wait until full remediation batch |
| `cost_type` / `cost_type_id` | Category/category_id exist in raw payloads and row cells | Require semantic policy decision: map category -> cost_type or add category columns |
| `actual_cost` | Deep key scan should decide whether any actual-cost source exists | Do not alias from direct/JTD/ERP unless explicit Actual Cost source exists |
| `line_item_type_id` | Deep key scan should decide whether any line-item-type source exists | Leave null/deprecate unless explicit source exists |
| `approved_change_orders` | wide=2522, cell=2522, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `committed_costs` | wide=1478, cell=1478, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `direct_costs` | wide=522, cell=522, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `erp_direct_costs` | wide=956, cell=956, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `erp_job_to_date_costs` | wide=956, cell=956, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `estimated_cost_at_completion` | wide=2522, cell=2522, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `forecast_to_complete` | wide=1044, cell=1044, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `job_to_date_costs` | wide=1566, cell=1566, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `pending_budget_changes` | wide=1478, cell=1478, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `projected_budget` | wide=2522, cell=2522, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `projected_costs` | wide=2522, cell=2522, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `projected_over_under` | wide=2522, cell=2522, missing_wide_for_cell=0, mismatches=0 | `ok` |
| `revised_budget` | wide=2522, cell=2522, missing_wide_for_cell=0, mismatches=0 | `ok` |
