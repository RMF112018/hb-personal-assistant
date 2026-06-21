# Procore Budget Formula Proof

## Source authority

Primary reference: [What are Procore's standard budget views?](https://support.procore.com/faq/what-are-procores-standard-budget-views) (Procore Support, official).

Secondary: [Use the Forecast to Complete feature](https://support.procore.com/products/online/user-guide/project-level/budget/tutorials/use-the-forecast-to-complete-feature).

## Proven formulas (Procore Standard Budget View)

| Local column | Procore column | Type | Formula / definition |
|--------------|----------------|------|----------------------|
| `original_budget_amount` | Original Budget Amount | Standard | Original budget per budget code |
| `approved_budget_changes` | Approved COs | Source | Approved commitment change orders (status-configurable) |
| `revised_budget` | Revised Budget | Calculated | Budget Modifications + Approved COs |
| `pending_budget_changes` | Pending Budget Changes | Source | Pending prime contract change orders |
| `projected_budget` | Projected Budget | Calculated | Revised Budget + Pending Budget Changes |
| `committed_costs` | Committed Costs | Source | Approved subcontracts/POs/COs per status rules |
| `direct_costs` | Direct Costs | Source | Pending / Revise and Resubmit / Approved direct costs |
| `job_to_date_costs` | Job to Date Costs | Calculated | Direct Costs + Subcontractor Invoices |
| `pending_cost_changes` | Pending Cost Changes | Source | Out-for-signature subcontracts, processing POs, pending COs |
| `projected_costs` | Projected Costs | Calculated | Committed Costs + Direct Costs + Pending Cost Changes |
| `forecast_to_complete` | Forecast to Complete | Standard/Calculated | Projected Budget − project costs (method may vary) |
| `estimated_cost_at_completion` | Estimated Cost at Completion | Calculated | Projected Costs + Forecast to Complete |
| `projected_over_under` | Projected Over/Under | Calculated | Projected Budget − EAC |

## Partially proven / unresolved

| Local column | Status | Blocker |
|--------------|--------|---------|
| `approved_budget_changes` | partially_proven | Local name may not map 1:1 to Procore “Approved COs” in all budget views |
| `forecast_to_complete` | partially_proven | F2C calculation method is configurable (automatic / linear / manual) |
| `actual_cost` | unresolved | Local rollup; exact Procore column mapping not proven |
| `erp_direct_costs` / `erp_job_to_date_costs` | unresolved | ERP sidecar columns; no official inclusion formula in standard view doc |

## Double-count gate implications

- **Proven calculated rollups** (`revised_budget`, `projected_budget`, `projected_costs`, `estimated_cost_at_completion`): coexistence with their documented source components is **expected** in Procore — gate reports **info** in warn mode; forecast models must not add components again.
- **Partially proven / unresolved**: remain **warning** in warn mode; never hard-fail solely on formula uncertainty.
- **Strict mode**: promotes warnings to errors for operator triage only — not production blocking without model context.

## Encoded in repo

- `docs/forecasting/semantic-catalog/budget_column_roles.yml` (v2)
- `src/hb_assistant/forecasting/budget_column_roles.py` loader
- `src/hb_assistant/forecasting/gates.py` overlap checks driven from catalog