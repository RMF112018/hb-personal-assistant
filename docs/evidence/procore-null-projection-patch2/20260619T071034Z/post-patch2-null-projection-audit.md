# Procore Null Projection Audit

## Executive Summary

- Tables audited: `86`
- Columns audited: `3694`
- All-null fields: `579`
- Mostly-null fields: `67`
- Raw suspected projection defects: `123`
- High-confidence scalar mapping candidates after source proof: `0`
- Date/datetime mapping candidates: `0`
- Patch 1 scalar decomposition defects: `0`
- Expected optional fields: `279`
- Support/guardrail fields: `1040`
- Empty tables: `4`
- Source proof required: `True`

## High-Priority Remediation Review

| table | column | table rows | null % | classification | raw root cause | decision class | mapping candidate | endpoint | recommendation |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| procore_ep_budget_detail_row_cells | company_id | 225131 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_read_model_schema_artifact | False |  | document_schema_artifact |
| procore_ep_budget_detail_row_cells | currency_iso_code | 225131 | 100.0 | all_null | schema_column_not_in_projection_registry | expected_optional_no_action | False |  | no_action_expected_optional |
| procore_ep_inspection_items_response_set_responses | company_id | 10068 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_submittals_approvers | company_id | 7260 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_submittals_approvers_attachments | company_id | 6571 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfis_assignees | company_id | 3390 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspection_items | company_id | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspection_items | item_response | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspection_items | response | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspection_items | response_set | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_daily_log_dcrs | company_id | 2628 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_budget_detail_rows | actual_cost | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_dead_convenience_column | False |  | no_action_dead_column_candidate |
| procore_ep_budget_detail_rows | company_id | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_read_model_schema_artifact | False |  | document_schema_artifact |
| procore_ep_budget_detail_rows | cost_type | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_dead_convenience_column | False |  | no_action_dead_column_candidate |
| procore_ep_budget_detail_rows | cost_type_id | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_dead_convenience_column | False |  | no_action_dead_column_candidate |
| procore_ep_budget_detail_rows | line_item_type_id | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_dead_convenience_column | False |  | no_action_dead_column_candidate |
| procore_ep_rfis | company_id | 1967 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfis_questions | company_id | 1967 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_submittals | company_id | 1760 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_submittals | submittal_package | 1760 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_submittals | submittal_workflow_template | 1760 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_daily_log_notes_attachments | company_id | 1188 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_subcontractor_invoices | company_id | 981 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_subcontractor_invoices_attachments | company_id | 981 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_manpower | company_id | 921 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_manpower | contact | 921 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_daily_log_manpower | cost_code | 921 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_daily_log_manpower | location | 921 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_daily_log_dcrs_attachments | company_id | 793 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_manpower_attachments | company_id | 781 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspections_attachments | company_id | 363 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_budget_detail_columns | company_id | 276 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_read_model_schema_artifact | False |  | document_schema_artifact |
| procore_ep_budget_detail_columns | visible | 276 | 100.0 | all_null | schema_column_not_in_projection_registry | budget_detail_read_model_schema_artifact | False |  | document_schema_artifact |
| procore_ep_commitment_contracts | company_id | 243 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_observations | assignee | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_observations | assignee_vendor | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_observations | company_id | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_observations | location | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_observations | origin | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_observations | specification_section | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_observations | trade | 215 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections_distribution_members | company_id | 213 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_submittals_ball_in_court | company_id | 181 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_subcontractor_invoice_contract_detail_items | company_id | 152 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_budget_modifications | company_id | 148 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfis_ball_in_courts | company_id | 148 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspection_sections | company_id | 139 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_weather | company_id | 130 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_inspections | company_id | 114 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_inspections | location | 114 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_commitment_compliance_insurance_documents__52b7bf | company_id | 105 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspections_inspectors | company_id | 101 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_commitment_change_orders | change_order_change_reason | 100 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_commitment_change_orders | company_id | 100 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_commitment_change_orders | designated_reviewer | 100 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_commitment_change_orders | received_from | 100 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_commitment_change_orders | reviewed_by | 100 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_meetings | company_id | 97 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_meetings | distributed_by | 97 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_budget_change_history | company_id | 95 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_notes | company_id | 92 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_notes | location | 92 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections | closed_by | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections | company_id | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspections | location | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections | point_of_contact | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections | responsible_contractor | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections | specification_section | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections | trade | 74 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_commitment_line_items | company_id | 63 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_prime_change_orders | change_order_change_reason | 63 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_prime_change_orders | company_id | 63 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_prime_change_orders | designated_reviewer | 63 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_prime_change_orders | received_from | 63 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_daily_log_deliveries | company_id | 59 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_commitment_compliance_insurance_documents | company_id | 58 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfqs_change_event_change_event_line_items__0a3e8d | company_id | 57 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfqs_change_event_change_event_line_items | company_id | 52 | 100.0 | all_null | schema_column_not_in_projection_registry | company_id_policy_deferred | False |  | defer_company_id_policy |
| procore_ep_punch_items_assignees | company_id | 48 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_punch_items_assignments | company_id | 48 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_prime_contract_line_items | company_id | 47 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_punch_items | company_id | 36 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_budget_views | company_id | 35 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfqs_change_event_attachments | company_id | 31 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_purchase_order_line_items_cost_code_line_i_779dbd | company_id | 24 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_subcontractor_invoice_change_order_items | company_id | 24 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_punch_items_ball_in_court | company_id | 23 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_billing_periods | company_id | 20 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_deliveries_attachments | company_id | 18 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_commitment_attachments | company_id | 16 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_inspections_attachments | company_id | 14 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects | company_id | 14 | 100.0 | all_null | schema_column_not_in_projection_registry | company_id_policy_deferred | False |  | defer_company_id_policy |
| procore_ep_projects | project_stage | 14 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_purchase_order_line_items | company_id | 12 | 100.0 | all_null | schema_column_not_in_projection_registry | company_id_policy_deferred | False |  | defer_company_id_policy |
| procore_ep_rfqs_attachments | company_id | 11 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163287_value | company_id | 10 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_purchase_order_contracts | assignee | 10 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_purchase_order_contracts | company_id | 10 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_purchase_order_contracts | custom_fields_custom_field_214072_value | 10 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_purchase_order_contracts | custom_fields_custom_field_214078_value | 10 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_purchase_order_contracts | custom_fields_custom_field_214087_value | 10 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_inspections_signature_requests | company_id | 8 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_inspections_signature_requests | signature | 8 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_commitment_compliance | company_id | 7 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_observations_assignees | company_id | 7 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_observations_assignees | vendor | 7 | 100.0 | all_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_rfqs | company_id | 7 | 100.0 | all_null | schema_column_not_in_projection_registry | company_id_policy_deferred | False |  | defer_company_id_policy |
| procore_ep_prime_contracts | company_id | 6 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163290_value | company_id | 6 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163293_value | company_id | 4 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_daily_log_visitor | company_id | 2 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_prime_change_order_line_items | company_id | 2 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163296_value | company_id | 2 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163299_value | company_id | 2 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163302_value | company_id | 2 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_projects_custom_fields_custom_field_163305_value | company_id | 2 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65 | company_id | 1 | 100.0 | all_null | schema_column_not_in_projection_registry | source_absent_in_current_payloads | False |  | no_action_source_absent_current_payloads |
| procore_ep_rfis | ball_in_court | 1967 | 97.3 | mostly_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_rfis | cost_code | 1967 | 98.5 | mostly_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_rfis | location | 1967 | 96.1 | mostly_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_rfis | sub_job | 1967 | 96.8 | mostly_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_submittals | location | 1760 | 98.2 | mostly_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_change_events | event_origin | 1054 | 99.5 | mostly_null | schema_column_not_in_projection_registry | object_container_requires_decomposition_or_deprecation | False |  | approve_decomposition_schema_design_next_or_deprecation |
| procore_ep_budget_detail_row_cells | company_id_hash | 225131 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_endpoint_raw_payloads | company_id | 49355 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_endpoint_raw_payloads | company_id_hash | 49355 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_inspection_items_response_set_responses | parent_item_id | 10068 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_inspection_items_response_set_responses | payload_sidecar_json | 10068 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_submittals_approvers | parent_item_id | 7260 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_submittals_approvers_attachments | payload_sidecar_json | 6571 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_rfis_assignees | parent_item_id | 3390 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_rfis_assignees | payload_sidecar_json | 3390 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_inspection_items | company_id_hash | 3363 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_inspection_items | company_template_item_details | 3363 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | inspection-items | no_action_expected_optional |
| procore_ep_inspection_items | parent_item_id_col | 3363 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | inspection-items | no_action_expected_optional |
| procore_ep_change_events_change_items | budget_impact_budget_change | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | budget_impact_budget_modification | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_commitment_currency_configuration_base_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_commitment_currency_configuration_currency_exchange_rate | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_commitment_currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_contract_confirmed | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_non_commitment_amount | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_request_for_quote_currency_configuration_base_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_request_for_quote_currency_configuration_currency_exchange_rate | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_request_for_quote_currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_vendor_confirmed | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | deleted_at | 2816 | 100.0 | all_null | registry_path_not_present_in_payload | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | parent_item_id | 2816 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events_change_items | revenue_impact_change_order_currency_configuration_base_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | revenue_impact_change_order_currency_configuration_currency_exchange_rate | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events_change_items | revenue_impact_change_order_currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_daily_log_dcrs | company_id_hash | 2628 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_daily_log_dcrs | deleted_at | 2628 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | daily-log-dcrs | no_action_expected_optional |
| procore_ep_daily_log_dcrs | location | 2628 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | daily-log-dcrs | no_action_expected_optional |
| procore_ep_daily_log_dcrs | parent_record_id | 2628 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_daily_log_dcrs | parent_record_id_hash | 2628 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_budget_detail_rows | company_id_hash | 2496 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events_attachments | parent_item_id | 2335 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events_attachments | payload_sidecar_json | 2335 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events_markup_items | parent_item_id | 2150 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_rfis | company_id_hash | 1967 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_rfis | connect_export_origin | 1967 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | rfis | no_action_expected_optional |
| procore_ep_rfis | parent_record_id | 1967 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_rfis | parent_record_id_hash | 1967 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_rfis | prefix | 1967 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | rfis | no_action_expected_optional |
| procore_ep_rfis | priority_name | 1967 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | rfis | no_action_expected_optional |
| procore_ep_rfis | priority_value | 1967 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | rfis | no_action_expected_optional |
| procore_ep_rfis | project_stage_formatted_parent_name | 1967 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | rfis | no_action_expected_optional |
| procore_ep_rfis | project_stage_parent_id | 1967 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | rfis | no_action_expected_optional |
| procore_ep_rfis_questions | parent_item_id | 1967 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_submittals | buffer_time | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | submittals | no_action_expected_optional |
| procore_ep_submittals | company_id_hash | 1760 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_submittals | location_parent_id | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | submittals | no_action_expected_optional |
| procore_ep_submittals | parent_record_id | 1760 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_submittals | parent_record_id_hash | 1760 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_submittals | rejected_submittal_log_approver_id | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | submittals | no_action_expected_optional |
| procore_ep_submittals | scheduled_task | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | submittals | no_action_expected_optional |
| procore_ep_submittals | sub_job | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | submittals | no_action_expected_optional |
| procore_ep_daily_log_notes_attachments | parent_item_id | 1188 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_daily_log_notes_attachments | payload_sidecar_json | 1188 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events | currency_configuration_currency_iso_code | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events | deleted_at | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events | external_data | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_change_events | parent_record_id | 1054 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events | parent_record_id_hash | 1054 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_change_events | source | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | change-events | no_action_expected_optional |
| procore_ep_subcontractor_invoices | company_id_hash | 981 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_subcontractor_invoices | currency_configuration_base_currency_iso_code | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | subcontractor-invoices | no_action_expected_optional |
| procore_ep_subcontractor_invoices | currency_configuration_currency_iso_code | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | subcontractor-invoices | no_action_expected_optional |
| procore_ep_subcontractor_invoices | electronic_signature_id | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | subcontractor-invoices | no_action_expected_optional |
| procore_ep_subcontractor_invoices | origin_data | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | subcontractor-invoices | no_action_expected_optional |
| procore_ep_subcontractor_invoices | origin_id | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | subcontractor-invoices | no_action_expected_optional |
| procore_ep_subcontractor_invoices | parent_record_id | 981 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_subcontractor_invoices | parent_record_id_hash | 981 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_subcontractor_invoices | payment_date | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | subcontractor-invoices | no_action_expected_optional |
| procore_ep_subcontractor_invoices_attachments | parent_item_id | 981 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_subcontractor_invoices_attachments | payload_sidecar_json | 981 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_daily_log_manpower | company_id_hash | 921 | 100.0 | all_null | support_or_guardrail_field | support_or_guardrail_field | False |  | no_action_support_or_guardrail |
| procore_ep_daily_log_manpower | contact_job_title | 921 | 100.0 | all_null | expected_optional_no_current_project_usage | expected_optional_no_action | False | daily-log-manpower | no_action_expected_optional |

## Root-Cause Notes

- `procore_ep_budget_detail_row_cells.company_id`: `schema_column_not_in_projection_registry`; decision=`budget_detail_read_model_schema_artifact`; rows=225131; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_row_cells.currency_iso_code`: `schema_column_not_in_projection_registry`; decision=`expected_optional_no_action`; rows=225131; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspection_items_response_set_responses.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=10068; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals_approvers.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=7260; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals_approvers_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=6571; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis_assignees.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=3390; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspection_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=3363; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspection_items.item_response`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=3363; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspection_items.response`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=3363; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspection_items.response_set`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=3363; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_dcrs.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2628; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_rows.actual_cost`: `schema_column_not_in_projection_registry`; decision=`budget_detail_dead_convenience_column`; rows=2496; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_rows.company_id`: `schema_column_not_in_projection_registry`; decision=`budget_detail_read_model_schema_artifact`; rows=2496; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_rows.cost_type`: `schema_column_not_in_projection_registry`; decision=`budget_detail_dead_convenience_column`; rows=2496; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_rows.cost_type_id`: `schema_column_not_in_projection_registry`; decision=`budget_detail_dead_convenience_column`; rows=2496; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_rows.line_item_type_id`: `schema_column_not_in_projection_registry`; decision=`budget_detail_dead_convenience_column`; rows=2496; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=1967; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis_questions.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=1967; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=1760; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals.submittal_package`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1760; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals.submittal_workflow_template`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1760; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_notes_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=1188; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_subcontractor_invoices.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=981; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_subcontractor_invoices_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=981; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_manpower.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=921; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_manpower.contact`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=921; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_manpower.cost_code`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=921; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_manpower.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=921; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_dcrs_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=793; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_manpower_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=781; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=363; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_columns.company_id`: `schema_column_not_in_projection_registry`; decision=`budget_detail_read_model_schema_artifact`; rows=276; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_columns.visible`: `schema_column_not_in_projection_registry`; decision=`budget_detail_read_model_schema_artifact`; rows=276; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_contracts.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=243; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.assignee`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.assignee_vendor`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.origin`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.specification_section`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations.trade`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=215; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections_distribution_members.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=213; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals_ball_in_court.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=181; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_subcontractor_invoice_contract_detail_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=152; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_modifications.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=148; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis_ball_in_courts.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=148; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspection_sections.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=139; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_weather.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=130; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_inspections.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=114; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_inspections.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=114; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_compliance_insurance_documents__52b7bf.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=105; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections_inspectors.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=101; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_change_orders.change_order_change_reason`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=100; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_change_orders.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=100; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_change_orders.designated_reviewer`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=100; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_change_orders.received_from`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=100; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_change_orders.reviewed_by`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=100; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_meetings.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=97; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_meetings.distributed_by`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=97; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_change_history.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=95; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_notes.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=92; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_notes.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=92; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.closed_by`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.point_of_contact`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.responsible_contractor`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.specification_section`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections.trade`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=74; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_line_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=63; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_change_orders.change_order_change_reason`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=63; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_change_orders.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=63; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_change_orders.designated_reviewer`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=63; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_change_orders.received_from`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=63; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_deliveries.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=59; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_compliance_insurance_documents.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=58; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfqs_change_event_change_event_line_items__0a3e8d.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=57; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfqs_change_event_change_event_line_items.company_id`: `schema_column_not_in_projection_registry`; decision=`company_id_policy_deferred`; rows=52; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_punch_items_assignees.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=48; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_punch_items_assignments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=48; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_contract_line_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=47; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_punch_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=36; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_views.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=35; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfqs_change_event_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=31; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_line_items_cost_code_line_i_779dbd.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=24; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_subcontractor_invoice_change_order_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=24; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_punch_items_ball_in_court.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=23; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_billing_periods.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=20; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_deliveries_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=18; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=16; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_inspections_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=14; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects.company_id`: `schema_column_not_in_projection_registry`; decision=`company_id_policy_deferred`; rows=14; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects.project_stage`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=14; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_line_items.company_id`: `schema_column_not_in_projection_registry`; decision=`company_id_policy_deferred`; rows=12; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfqs_attachments.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=11; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163287_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=10; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_contracts.assignee`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=10; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_contracts.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=10; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_contracts.custom_fields_custom_field_214072_value`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=10; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_contracts.custom_fields_custom_field_214078_value`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=10; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_contracts.custom_fields_custom_field_214087_value`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=10; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections_signature_requests.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=8; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_inspections_signature_requests.signature`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=8; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_commitment_compliance.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=7; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations_assignees.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=7; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_observations_assignees.vendor`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=7; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfqs.company_id`: `schema_column_not_in_projection_registry`; decision=`company_id_policy_deferred`; rows=7; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_contracts.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=6; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163290_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=6; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163293_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=4; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_daily_log_visitor.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_prime_change_order_line_items.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163296_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163299_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163302_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_projects_custom_fields_custom_field_163305_value.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=2; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65.company_id`: `schema_column_not_in_projection_registry`; decision=`source_absent_in_current_payloads`; rows=1; null_rate=100.0%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis.ball_in_court`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1967; null_rate=97.3%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis.cost_code`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1967; null_rate=98.5%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1967; null_rate=96.1%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_rfis.sub_job`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1967; null_rate=96.8%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_submittals.location`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1760; null_rate=98.2%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_change_events.event_origin`: `schema_column_not_in_projection_registry`; decision=`object_container_requires_decomposition_or_deprecation`; rows=1054; null_rate=99.5%; Column exists in SQLite but no committed projection-registry mapping was found.
- `procore_ep_budget_detail_row_cells.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=225131; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_endpoint_raw_payloads.company_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=49355; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_endpoint_raw_payloads.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=49355; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items_response_set_responses.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=10068; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items_response_set_responses.payload_sidecar_json`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=10068; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals_approvers.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=7260; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals_approvers_attachments.payload_sidecar_json`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=6571; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis_assignees.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=3390; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis_assignees.payload_sidecar_json`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=3390; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=3363; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items.company_template_item_details`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=3363; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.company_template_item_details` inspected=3363 present=3363 missing=0 values_emitted=false.
- `procore_ep_inspection_items.parent_item_id_col`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=3363; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.parent_item_id` inspected=3363 present=3363 missing=0 values_emitted=false.
- `procore_ep_change_events_change_items.budget_impact_budget_change`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.budget_impact.budget_change` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.budget_impact_budget_modification`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.budget_impact.budget_modification` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.commitment.currency_configuration.base_currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_currency_exchange_rate`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.commitment.currency_configuration.currency_exchange_rate` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.commitment.currency_configuration.currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_contract_confirmed`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.contract.confirmed` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_non_commitment_amount`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.non_commitment.amount` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.request_for_quote.currency_configuration.base_currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_currency_exchange_rate`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.request_for_quote.currency_configuration.currency_exchange_rate` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.request_for_quote.currency_configuration.currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_vendor_confirmed`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.vendor.confirmed` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.currency_configuration.currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.deleted_at`: `registry_path_not_present_in_payload`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads contain the parent path without this leaf.
  Path presence: `$.change_items.deleted_at` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2816; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.revenue_impact.change_order.currency_configuration.base_currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_currency_exchange_rate`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.revenue_impact.change_order.currency_configuration.currency_exchange_rate` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.revenue_impact.change_order.currency_configuration.currency_iso_code` inspected=2656 present=0 missing=2656 values_emitted=false.
- `procore_ep_daily_log_dcrs.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2628; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_dcrs.deleted_at`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2628; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=2629 present=2629 missing=0 values_emitted=false.
- `procore_ep_daily_log_dcrs.location`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=2628; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.location` inspected=2629 present=2629 missing=0 values_emitted=false.
- `procore_ep_daily_log_dcrs.parent_record_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2628; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_dcrs.parent_record_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2628; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_detail_rows.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2496; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_attachments.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2335; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_attachments.payload_sidecar_json`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2335; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_markup_items.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=2150; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1967; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.connect_export_origin`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1967; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.connect_export_origin` inspected=2008 present=2008 missing=0 values_emitted=false.
- `procore_ep_rfis.parent_record_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1967; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.parent_record_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1967; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.prefix`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1967; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.prefix` inspected=2008 present=2008 missing=0 values_emitted=false.
- `procore_ep_rfis.priority_name`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1967; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.priority.name` inspected=2008 present=2008 missing=0 values_emitted=false.
- `procore_ep_rfis.priority_value`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1967; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.priority.value` inspected=2008 present=2008 missing=0 values_emitted=false.
- `procore_ep_rfis.project_stage_formatted_parent_name`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1967; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.project_stage.formatted_parent_name` inspected=2008 present=478 missing=1530 values_emitted=false.
- `procore_ep_rfis.project_stage_parent_id`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1967; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.project_stage.parent_id` inspected=2008 present=478 missing=1530 values_emitted=false.
- `procore_ep_rfis_questions.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1967; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.buffer_time`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.buffer_time` inspected=1900 present=1900 missing=0 values_emitted=false.
- `procore_ep_submittals.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1760; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.location_parent_id`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.location.parent_id` inspected=1900 present=184 missing=1716 values_emitted=false.
- `procore_ep_submittals.parent_record_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1760; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.parent_record_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1760; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.rejected_submittal_log_approver_id`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.rejected_submittal_log_approver_id` inspected=1900 present=1900 missing=0 values_emitted=false.
- `procore_ep_submittals.scheduled_task`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.scheduled_task` inspected=1900 present=1900 missing=0 values_emitted=false.
- `procore_ep_submittals.sub_job`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.sub_job` inspected=1900 present=1900 missing=0 values_emitted=false.
- `procore_ep_daily_log_notes_attachments.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1188; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_notes_attachments.payload_sidecar_json`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1188; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.currency_iso_code` inspected=2656 present=2656 missing=0 values_emitted=false.
- `procore_ep_change_events.deleted_at`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=2656 present=2656 missing=0 values_emitted=false.
- `procore_ep_change_events.external_data`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.external_data` inspected=2656 present=2656 missing=0 values_emitted=false.
- `procore_ep_change_events.parent_record_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1054; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events.parent_record_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=1054; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events.source`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.source` inspected=2656 present=2656 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices.currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.base_currency_iso_code` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.currency_iso_code` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.electronic_signature_id`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.electronic_signature_id` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.origin_data`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.origin_data` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.origin_id`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.origin_id` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.parent_record_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices.parent_record_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices.payment_date`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.payment_date` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices_attachments.parent_item_id`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices_attachments.payload_sidecar_json`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower.company_id_hash`: `support_or_guardrail_field`; decision=`support_or_guardrail_field`; rows=921; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower.contact_job_title`: `expected_optional_no_current_project_usage`; decision=`expected_optional_no_action`; rows=921; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.contact.job_title` inspected=921 present=920 missing=1 values_emitted=false.

## Table-by-Table Null Profile

| table | rows | columns | all-null columns | suspected defects |
| --- | ---: | ---: | ---: | ---: |
| procore_endpoint_capture_errors | 0 | 10 | 10 | 0 |
| procore_endpoint_capture_pages | 0 | 14 | 14 | 0 |
| procore_endpoint_capture_runs | 0 | 18 | 18 | 0 |
| procore_endpoint_contracts | 0 | 20 | 20 | 0 |
| procore_endpoint_raw_payloads | 49355 | 36 | 2 | 0 |
| procore_ep_billing_periods | 20 | 31 | 5 | 1 |
| procore_ep_budget_change_history | 95 | 32 | 5 | 1 |
| procore_ep_budget_detail_columns | 276 | 33 | 3 | 2 |
| procore_ep_budget_detail_row_cells | 225131 | 30 | 3 | 2 |
| procore_ep_budget_detail_rows | 2496 | 52 | 6 | 5 |
| procore_ep_budget_modifications | 148 | 32 | 7 | 1 |
| procore_ep_budget_views | 35 | 33 | 4 | 1 |
| procore_ep_change_events | 1054 | 55 | 6 | 1 |
| procore_ep_change_events_attachments | 2335 | 23 | 2 | 0 |
| procore_ep_change_events_change_items | 2816 | 139 | 17 | 0 |
| procore_ep_change_events_change_items_budget_code_seg_2dff22 | 8448 | 25 | 0 | 0 |
| procore_ep_change_events_markup_items | 2150 | 31 | 1 | 0 |
| procore_ep_change_events_markup_items_wbs_code_segment_items | 6450 | 25 | 0 | 0 |
| procore_ep_commitment_attachments | 16 | 28 | 3 | 1 |
| procore_ep_commitment_change_orders | 100 | 68 | 12 | 5 |
| procore_ep_commitment_compliance | 7 | 32 | 9 | 1 |
| procore_ep_commitment_compliance_insurance_documents | 58 | 28 | 3 | 1 |
| procore_ep_commitment_compliance_insurance_documents__52b7bf | 105 | 24 | 2 | 1 |
| procore_ep_commitment_contracts | 243 | 72 | 11 | 1 |
| procore_ep_commitment_line_items | 63 | 38 | 5 | 1 |
| procore_ep_daily_log_dcrs | 2628 | 56 | 6 | 1 |
| procore_ep_daily_log_dcrs_attachments | 793 | 28 | 3 | 1 |
| procore_ep_daily_log_deliveries | 59 | 43 | 8 | 1 |
| procore_ep_daily_log_deliveries_attachments | 18 | 28 | 3 | 1 |
| procore_ep_daily_log_inspections | 114 | 52 | 7 | 2 |
| procore_ep_daily_log_inspections_attachments | 14 | 28 | 3 | 1 |
| procore_ep_daily_log_manpower | 921 | 62 | 12 | 4 |
| procore_ep_daily_log_manpower_attachments | 781 | 28 | 3 | 1 |
| procore_ep_daily_log_notes | 92 | 46 | 7 | 2 |
| procore_ep_daily_log_notes_attachments | 1188 | 28 | 3 | 1 |
| procore_ep_daily_log_visitor | 2 | 43 | 7 | 1 |
| procore_ep_daily_log_weather | 130 | 49 | 19 | 1 |
| procore_ep_inspection_items | 3363 | 64 | 7 | 4 |
| procore_ep_inspection_items_response_set_responses | 10068 | 24 | 3 | 1 |
| procore_ep_inspection_sections | 139 | 28 | 5 | 1 |
| procore_ep_inspections | 74 | 91 | 17 | 7 |
| procore_ep_inspections_attachments | 363 | 30 | 3 | 1 |
| procore_ep_inspections_distribution_members | 213 | 24 | 3 | 1 |
| procore_ep_inspections_inspectors | 101 | 24 | 3 | 1 |
| procore_ep_inspections_signature_requests | 8 | 33 | 3 | 2 |
| procore_ep_meetings | 97 | 45 | 6 | 2 |
| procore_ep_observations | 215 | 77 | 14 | 7 |
| procore_ep_observations_assignees | 7 | 25 | 3 | 2 |
| procore_ep_prime_change_order_line_items | 2 | 37 | 4 | 1 |
| procore_ep_prime_change_orders | 63 | 66 | 14 | 4 |
| procore_ep_prime_contract_line_items | 47 | 34 | 5 | 1 |
| procore_ep_prime_contracts | 6 | 113 | 39 | 1 |
| procore_ep_projects | 14 | 88 | 13 | 2 |
| procore_ep_projects_custom_fields_custom_field_163287_value | 10 | 23 | 3 | 1 |
| procore_ep_projects_custom_fields_custom_field_163290_value | 6 | 23 | 3 | 1 |
| procore_ep_projects_custom_fields_custom_field_163293_value | 4 | 23 | 3 | 1 |
| procore_ep_projects_custom_fields_custom_field_163296_value | 2 | 23 | 3 | 1 |
| procore_ep_projects_custom_fields_custom_field_163299_value | 2 | 23 | 3 | 1 |
| procore_ep_projects_custom_fields_custom_field_163302_value | 2 | 23 | 3 | 1 |
| procore_ep_projects_custom_fields_custom_field_163305_value | 2 | 23 | 3 | 1 |
| procore_ep_punch_items | 36 | 75 | 14 | 1 |
| procore_ep_punch_items_assignees | 48 | 25 | 4 | 1 |
| procore_ep_punch_items_assignments | 48 | 38 | 2 | 1 |
| procore_ep_punch_items_ball_in_court | 23 | 25 | 4 | 1 |
| procore_ep_purchase_order_contracts | 10 | 128 | 38 | 5 |
| procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65 | 1 | 23 | 3 | 1 |
| procore_ep_purchase_order_line_items | 12 | 63 | 4 | 1 |
| procore_ep_purchase_order_line_items_cost_code_line_i_779dbd | 24 | 25 | 3 | 1 |
| procore_ep_rfis | 1967 | 95 | 10 | 5 |
| procore_ep_rfis_assignees | 3390 | 25 | 3 | 1 |
| procore_ep_rfis_ball_in_courts | 148 | 24 | 3 | 1 |
| procore_ep_rfis_questions | 1967 | 22 | 2 | 1 |
| procore_ep_rfqs | 7 | 105 | 11 | 1 |
| procore_ep_rfqs_attachments | 11 | 24 | 3 | 1 |
| procore_ep_rfqs_change_event_attachments | 31 | 24 | 3 | 1 |
| procore_ep_rfqs_change_event_change_event_line_items | 52 | 120 | 13 | 1 |
| procore_ep_rfqs_change_event_change_event_line_items__0a3e8d | 57 | 25 | 2 | 1 |
| procore_ep_schedules | 1 | 38 | 6 | 0 |
| procore_ep_subcontractor_invoice_change_order_items | 24 | 55 | 4 | 1 |
| procore_ep_subcontractor_invoice_contract_detail_items | 152 | 52 | 4 | 1 |
| procore_ep_subcontractor_invoices | 981 | 83 | 10 | 1 |
| procore_ep_subcontractor_invoices_attachments | 981 | 25 | 3 | 1 |
| procore_ep_submittals | 1760 | 108 | 11 | 4 |
| procore_ep_submittals_approvers | 7260 | 35 | 2 | 1 |
| procore_ep_submittals_approvers_attachments | 6571 | 24 | 2 | 1 |
| procore_ep_submittals_ball_in_court | 181 | 24 | 3 | 1 |

## Body-Free Privacy Attestation

- Raw payload JSON was inspected only for key/path presence counts.
- The JSON and Markdown reports emit path names and counts only, not payload fragments or values.
- `raw_payload_values_emitted` is `false` for every column/path record.

## Remediation Not Applied

No schema, registry, migration, projection, scheduled-refresh, live-fetch, or read-model remediation was applied by this audit.
