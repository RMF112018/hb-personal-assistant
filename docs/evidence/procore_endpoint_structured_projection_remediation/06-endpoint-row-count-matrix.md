# 06 — Endpoint Row-Count Matrix

- Total primary rows: `10089` · Total child rows: `22042` · external_writeback violations: `0`
- Reprocess: primary_written=`10105` child_written=`22089` degraded=`0` skipped_higher=`0` (2.2s)

| endpoint | primary | raw-linked | child tables | child rows | wb violations |
|---|--:|--:|--:|--:|--:|
| billing-periods | 20 | 20 | 0 | 0 | 0 |
| budget-change-history | 95 | 95 | 0 | 0 | 0 |
| budget-modifications | 148 | 148 | 0 | 0 | 0 |
| budget-views | 6 | 6 | 0 | 0 | 0 |
| change-events | 199 | 199 | 5 | 3778 | 0 |
| commitment-attachments | 16 | 16 | 0 | 0 | 0 |
| commitment-change-orders | 100 | 100 | 0 | 0 | 0 |
| commitment-compliance | 7 | 7 | 2 | 163 | 0 |
| commitment-contracts | 137 | 137 | 0 | 0 | 0 |
| commitment-line-items | 63 | 63 | 0 | 0 | 0 |
| daily-log-dcrs | 2541 | 2541 | 1 | 546 | 0 |
| daily-log-deliveries | 59 | 59 | 1 | 18 | 0 |
| daily-log-inspections | 114 | 114 | 1 | 14 | 0 |
| daily-log-manpower | 883 | 883 | 1 | 771 | 0 |
| daily-log-notes | 92 | 92 | 1 | 1188 | 0 |
| daily-log-visitor | 2 | 2 | 0 | 0 | 0 |
| daily-log-weather | 104 | 104 | 0 | 0 | 0 |
| inspection-items | 3363 | 3363 | 1 | 10068 | 0 |
| inspection-sections | 139 | 139 | 0 | 0 | 0 |
| inspections | 74 | 74 | 4 | 685 | 0 |
| meetings | 97 | 97 | 0 | 0 | 0 |
| observations | 215 | 215 | 1 | 7 | 0 |
| prime-change-order-line-items | 2 | 2 | 0 | 0 | 0 |
| prime-change-orders | 63 | 63 | 0 | 0 | 0 |
| prime-contract-line-items | 47 | 47 | 0 | 0 | 0 |
| prime-contracts | 5 | 5 | 0 | 0 | 0 |
| projects | 7 | 7 | 7 | 14 | 0 |
| punch-items | 4 | 4 | 3 | 12 | 0 |
| purchase-order-contracts | 10 | 10 | 1 | 1 | 0 |
| purchase-order-line-items | 12 | 12 | 1 | 24 | 0 |
| rfis | 606 | 606 | 3 | 1696 | 0 |
| rfqs | 7 | 7 | 4 | 151 | 0 |
| schedules | 1 | 1 | 0 | 0 | 0 |
| subcontractor-invoice-change-order-items | 24 | 24 | 0 | 0 | 0 |
| subcontractor-invoice-contract-detail-items | 152 | 152 | 0 | 0 | 0 |
| subcontractor-invoices | 226 | 226 | 1 | 212 | 0 |
| submittals | 449 | 449 | 3 | 2694 | 0 |

## Child table row counts
- `procore_ep_change_events_attachments`: 234
- `procore_ep_change_events_change_items`: 313
- `procore_ep_change_events_change_items_budget_code_seg_2dff22`: 939
- `procore_ep_change_events_markup_items`: 573
- `procore_ep_change_events_markup_items_wbs_code_segment_items`: 1719
- `procore_ep_commitment_compliance_insurance_documents`: 58
- `procore_ep_commitment_compliance_insurance_documents__52b7bf`: 105
- `procore_ep_daily_log_dcrs_attachments`: 546
- `procore_ep_daily_log_deliveries_attachments`: 18
- `procore_ep_daily_log_inspections_attachments`: 14
- `procore_ep_daily_log_manpower_attachments`: 771
- `procore_ep_daily_log_notes_attachments`: 1188
- `procore_ep_inspection_items_response_set_responses`: 10068
- `procore_ep_inspections_attachments`: 363
- `procore_ep_inspections_distribution_members`: 213
- `procore_ep_inspections_inspectors`: 101
- `procore_ep_inspections_signature_requests`: 8
- `procore_ep_observations_assignees`: 7
- `procore_ep_projects_custom_fields_custom_field_163287_value`: 5
- `procore_ep_projects_custom_fields_custom_field_163290_value`: 3
- `procore_ep_projects_custom_fields_custom_field_163293_value`: 2
- `procore_ep_projects_custom_fields_custom_field_163296_value`: 1
- `procore_ep_projects_custom_fields_custom_field_163299_value`: 1
- `procore_ep_projects_custom_fields_custom_field_163302_value`: 1
- `procore_ep_projects_custom_fields_custom_field_163305_value`: 1
- `procore_ep_punch_items_assignees`: 4
- `procore_ep_punch_items_assignments`: 4
- `procore_ep_punch_items_ball_in_court`: 4
- `procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65`: 1
- `procore_ep_purchase_order_line_items_cost_code_line_i_779dbd`: 24
- `procore_ep_rfis_assignees`: 1016
- `procore_ep_rfis_ball_in_courts`: 74
- `procore_ep_rfis_questions`: 606
- `procore_ep_rfqs_attachments`: 11
- `procore_ep_rfqs_change_event_attachments`: 31
- `procore_ep_rfqs_change_event_change_event_line_items`: 52
- `procore_ep_rfqs_change_event_change_event_line_items__0a3e8d`: 57
- `procore_ep_subcontractor_invoices_attachments`: 212
- `procore_ep_submittals_approvers`: 1519
- `procore_ep_submittals_approvers_attachments`: 1094
- `procore_ep_submittals_ball_in_court`: 81
