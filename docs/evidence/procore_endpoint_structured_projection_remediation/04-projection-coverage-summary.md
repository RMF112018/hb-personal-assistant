# 04 — Projection Coverage Summary

- Audit ok: `True`
- unmapped_primary_business_fields: `0`
- unmapped_nested_business_fields: `0`
- unknown_business_field_paths: `0`
- over sidecar threshold (justified): `['prime-contracts', 'purchase-order-contracts']`
- over sidecar threshold UNJUSTIFIED: `[]`

| endpoint | primary table | cols | child | sidecar | excl | sidecar % | over? | unknown |
|---|---|--:|--:|--:|--:|--:|:-:|--:|
| billing-periods | procore_ep_billing_periods | 9 | 0 | 0 | 0 | 0.0 | no | 0 |
| budget-change-history | procore_ep_budget_change_history | 8 | 0 | 0 | 0 | 0.0 | no | 0 |
| budget-modifications | procore_ep_budget_modifications | 9 | 0 | 0 | 0 | 0.0 | no | 0 |
| budget-views | procore_ep_budget_views | 10 | 0 | 1 | 0 | 9.1 | no | 0 |
| change-events | procore_ep_change_events | 170 | 5 | 31 | 0 | 15.0 | no | 0 |
| commitment-attachments | procore_ep_commitment_attachments | 5 | 0 | 0 | 0 | 0.0 | no | 0 |
| commitment-change-orders | procore_ep_commitment_change_orders | 45 | 0 | 0 | 0 | 0.0 | no | 0 |
| commitment-compliance | procore_ep_commitment_compliance | 20 | 2 | 3 | 0 | 12.0 | no | 0 |
| commitment-contracts | procore_ep_commitment_contracts | 49 | 0 | 0 | 0 | 0.0 | no | 0 |
| commitment-line-items | procore_ep_commitment_line_items | 15 | 0 | 0 | 0 | 0.0 | no | 0 |
| daily-log-dcrs | procore_ep_daily_log_dcrs | 41 | 1 | 4 | 0 | 8.7 | no | 0 |
| daily-log-deliveries | procore_ep_daily_log_deliveries | 28 | 1 | 3 | 0 | 9.4 | no | 0 |
| daily-log-inspections | procore_ep_daily_log_inspections | 37 | 1 | 3 | 0 | 7.3 | no | 0 |
| daily-log-manpower | procore_ep_daily_log_manpower | 47 | 1 | 6 | 0 | 11.1 | no | 0 |
| daily-log-notes | procore_ep_daily_log_notes | 31 | 1 | 3 | 0 | 8.6 | no | 0 |
| daily-log-visitor | procore_ep_daily_log_visitor | 20 | 0 | 4 | 0 | 16.7 | no | 0 |
| daily-log-weather | procore_ep_daily_log_weather | 26 | 0 | 3 | 0 | 10.3 | no | 0 |
| inspection-items | procore_ep_inspection_items | 45 | 1 | 12 | 0 | 20.7 | no | 0 |
| inspection-sections | procore_ep_inspection_sections | 5 | 0 | 0 | 0 | 0.0 | no | 0 |
| inspections | procore_ep_inspections | 99 | 4 | 11 | 0 | 9.6 | no | 0 |
| meetings | procore_ep_meetings | 22 | 0 | 0 | 0 | 0.0 | no | 0 |
| observations | procore_ep_observations | 59 | 1 | 11 | 0 | 15.5 | no | 0 |
| prime-change-order-line-items | procore_ep_prime_change_order_line_items | 14 | 0 | 0 | 0 | 0.0 | no | 0 |
| prime-change-orders | procore_ep_prime_change_orders | 43 | 0 | 0 | 0 | 0.0 | no | 0 |
| prime-contract-line-items | procore_ep_prime_contract_line_items | 11 | 0 | 0 | 0 | 0.0 | no | 0 |
| prime-contracts | procore_ep_prime_contracts | 91 | 0 | 33 | 0 | 26.6 | yes(justified) | 0 |
| projects | procore_ep_projects | 86 | 7 | 20 | 0 | 17.7 | no | 0 |
| punch-items | procore_ep_punch_items | 80 | 3 | 6 | 0 | 6.7 | no | 0 |
| purchase-order-contracts | procore_ep_purchase_order_contracts | 108 | 1 | 52 | 0 | 32.3 | yes(justified) | 0 |
| purchase-order-line-items | procore_ep_purchase_order_line_items | 45 | 1 | 6 | 0 | 11.5 | no | 0 |
| rfis | procore_ep_rfis | 83 | 3 | 4 | 0 | 4.4 | no | 0 |
| rfqs | procore_ep_rfqs | 195 | 4 | 27 | 0 | 11.9 | no | 0 |
| schedules | procore_ep_schedules | 16 | 0 | 0 | 0 | 0.0 | no | 0 |
| subcontractor-invoice-change-order-items | procore_ep_subcontractor_invoice_change_order_items | 32 | 0 | 0 | 0 | 0.0 | no | 0 |
| subcontractor-invoice-contract-detail-items | procore_ep_subcontractor_invoice_contract_detail_items | 29 | 0 | 0 | 0 | 0.0 | no | 0 |
| subcontractor-invoices | procore_ep_subcontractor_invoices | 66 | 1 | 2 | 0 | 2.9 | no | 0 |
| submittals | procore_ep_submittals | 108 | 3 | 15 | 0 | 11.9 | no | 0 |
