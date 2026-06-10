# Sampled source money-field summary (field NAMES only)

Sampled from `procore_live_records.canonical_json_redacted` on a `/tmp` DB copy. Only field
**names** and the extraction decision are recorded — **no payload bodies, no values**.

| endpoint_id (source) | structured table | money-like field names present | mapped as `amount` (precedence) | excluded |
|---|---|---|---|---|
| `subcontractor-invoice-contract-detail-items` | `procore_raw_invoice_items` | scheduled_value, subcontractor_claimed_amount, total_completed_and_stored_to_date, work_completed_this_period, materials_presently_stored, work_completed_from_previous_application, *_retainage_* | work_completed_this_period → total_completed_and_stored_to_date → subcontractor_claimed_amount → scheduled_value | retainage / materials / previous-application fields (not the headline amount) |
| `subcontractor-invoice-change-order-items` | `procore_raw_invoice_items` | (same as above) + scheduled_unit_price | (same precedence) | scheduled_unit_price (unit rate, not extended amount) |
| `subcontractor-invoices` | `procore_raw_invoices` | total_claimed_amount, summary.{current_payment_due, contract_sum_to_date, total_completed_and_stored_to_date, original_contract_sum, balance_to_finish_including_retainage, total_earned_less_retainage, total_retainage} | total_claimed_amount → summary.current_payment_due → summary.contract_sum_to_date → summary.total_completed_and_stored_to_date | retainage / balance / original-sum totals (not the headline claim) |
| `prime-change-orders` | `procore_raw_change_orders` | grand_total, schedule_impact_amount | grand_total | **schedule_impact_amount** (schedule day-count, not currency) |
| `commitment-change-orders` | `procore_raw_change_orders` | grand_total, schedule_impact_amount, due_date | grand_total | schedule_impact_amount, due_date |
| `prime-change-order-line-items` / `commitment-change-order-line-items` | `procore_raw_change_order_line_items` | amount, unit_cost | amount (generic fallback) | unit_cost |
| `commitment-line-items` / `prime-contract-line-items` / `purchase-order-line-items` | `procore_raw_contract_line_items` | amount, (extended_amount, total_amount, unit_cost) | amount (generic fallback) | unit_cost |
| `budget-detail-rows` | `procore_raw_budget_rows` | original_budget_amount, budget_forecast.{amount, automatic_amount, manual_amount} | original_budget_amount (generic fallback) | budget_forecast.* nested forecast variants |
| `payment-applications` | `procore_raw_payment_applications` | — (no source rows) | mapped for future rows; currently source-absent | — |

Sampling was performed with the in-repo `_path_value` resolver over up to 200 sampled rows per
endpoint; presence is determined by a non-empty leaf, never by emitting the value.
