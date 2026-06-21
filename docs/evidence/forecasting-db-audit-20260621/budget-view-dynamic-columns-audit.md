# Budget View Dynamic Columns Audit

Evidence JSON: `budget-view-dynamic-columns-evidence.json`

## Scope

Tables: `procore_ep_budget_detail_columns`, `procore_ep_budget_detail_row_cells`, `procore_ep_budget_views`

## Summary

| Budget view ID | Column defs | Distinct keys |
|----------------|-------------|---------------|
| 17941 | 66 | 11 |
| 2647 | 90 | 15 |
| 362562 | 42 | 7 |
| 362563 | 48 | 8 |
| 5885 | 78 | 13 |
| 713474 | 75 | 15 |

## Classification model

| Classification | Rule |
|----------------|------|
| `standard_known_column` | Maps to `budget_column_roles.yml` via Procore display label |
| `known_calculated_rollup` | Calculated role in catalog |
| `custom_numeric_candidate` | Numeric-looking, unmapped — **review_required** |
| `custom_status_or_dimension` | Budget Code, Vendor, Detail Type, etc. |
| `custom_text_or_note` | Notes columns — excluded from monetary parsing |
| `review_required` | `source` / `budget_forecast` data_type without role mapping |

## Key observations

- Standard Procore columns (Original Budget Amount, Committed Costs, Job to Date Costs, ERP Job to Date Costs, etc.) map cleanly via display labels.
- Custom/source columns (Change Events, Commitments, Prime, Requisitions) require operator review before model input.
- Row cells remain **source evidence**; terminal rollups live on `procore_ep_budget_detail_rows`.
- Gate `forecast_budget_dynamic_columns` warns on unmapped numeric cells; does not hard-fail.

## Catalog

`docs/forecasting/semantic-catalog/budget_dynamic_columns.yml` — classification rules and extension point for per-column entries.