# Procore Null Projection Audit

## Executive Summary

- Tables audited: `86`
- Columns audited: `3694`
- All-null fields: `579`
- Mostly-null fields: `67`
- Suspected projection defects: `0`
- Expected optional fields: `279`
- Support/guardrail fields: `1040`
- Empty tables: `4`
- Explicitly deferred fields: `123`

## High-Priority Remediation Review

| table | column | table rows | null % | classification | root cause | endpoint | recommendation |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| procore_ep_budget_detail_row_cells | company_id | 225131 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_detail_row_cells | company_id_hash | 225131 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_detail_row_cells | currency_iso_code | 225131 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_endpoint_raw_payloads | company_id | 49287 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_endpoint_raw_payloads | company_id_hash | 49287 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_items_response_set_responses | company_id | 10068 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspection_items_response_set_responses | parent_item_id | 10068 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_items_response_set_responses | payload_sidecar_json | 10068 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals_approvers | company_id | 7260 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_submittals_approvers | parent_item_id | 7260 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals_approvers_attachments | company_id | 6566 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_submittals_approvers_attachments | payload_sidecar_json | 6566 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis_assignees | company_id | 3371 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_rfis_assignees | parent_item_id | 3371 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis_assignees | payload_sidecar_json | 3371 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_items | company_id | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspection_items | company_id_hash | 3363 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_items | company_template_item_details | 3363 | 100.0 | all_null | expected_optional_no_current_project_usage | inspection-items | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_inspection_items | item_response | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspection_items | parent_item_id_col | 3363 | 100.0 | all_null | expected_optional_no_current_project_usage | inspection-items | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_inspection_items | response | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspection_items | response_set | 3363 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_change_events_change_items | budget_impact_budget_change | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | budget_impact_budget_modification | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_commitment_currency_configuration_base_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_commitment_currency_configuration_currency_exchange_rate | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_commitment_currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_contract_confirmed | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_non_commitment_amount | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_request_for_quote_currency_configuration_base_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_request_for_quote_currency_configuration_currency_exchange_rate | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_request_for_quote_currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | cost_impact_vendor_confirmed | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | deleted_at | 2816 | 100.0 | all_null | registry_path_not_present_in_payload | change-events | Review registry path against current payload shape before changing schema. |
| procore_ep_change_events_change_items | parent_item_id | 2816 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_change_events_change_items | revenue_impact_change_order_currency_configuration_base_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | revenue_impact_change_order_currency_configuration_currency_exchange_rate | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events_change_items | revenue_impact_change_order_currency_configuration_currency_iso_code | 2816 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_dcrs | company_id | 2623 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_dcrs | company_id_hash | 2623 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_dcrs | deleted_at | 2623 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-dcrs | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_dcrs | location | 2623 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-dcrs | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_dcrs | parent_record_id | 2623 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_dcrs | parent_record_id_hash | 2623 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_detail_rows | actual_cost | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_detail_rows | company_id | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_detail_rows | company_id_hash | 2496 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_detail_rows | cost_type | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_detail_rows | cost_type_id | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_detail_rows | line_item_type_id | 2496 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_change_events_attachments | parent_item_id | 2335 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_change_events_attachments | payload_sidecar_json | 2335 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_change_events_markup_items | parent_item_id | 2150 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis | company_id | 1960 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_rfis | company_id_hash | 1960 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis | connect_export_origin | 1960 | 100.0 | all_null | expected_optional_no_current_project_usage | rfis | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_rfis | parent_record_id | 1960 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis | parent_record_id_hash | 1960 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis | prefix | 1960 | 100.0 | all_null | expected_optional_no_current_project_usage | rfis | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_rfis | priority_name | 1960 | 100.0 | all_null | expected_optional_no_current_project_usage | rfis | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_rfis | priority_value | 1960 | 100.0 | all_null | expected_optional_no_current_project_usage | rfis | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_rfis | project_stage_formatted_parent_name | 1960 | 100.0 | all_null | expected_optional_no_current_project_usage | rfis | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_rfis | project_stage_parent_id | 1960 | 100.0 | all_null | expected_optional_no_current_project_usage | rfis | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_rfis_questions | company_id | 1960 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_rfis_questions | parent_item_id | 1960 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals | buffer_time | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | submittals | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_submittals | company_id | 1760 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_submittals | company_id_hash | 1760 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals | location_parent_id | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | submittals | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_submittals | parent_record_id | 1760 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals | parent_record_id_hash | 1760 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals | rejected_submittal_log_approver_id | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | submittals | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_submittals | scheduled_task | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | submittals | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_submittals | sub_job | 1760 | 100.0 | all_null | expected_optional_no_current_project_usage | submittals | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_submittals | submittal_package | 1760 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_submittals | submittal_workflow_template | 1760 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_notes_attachments | company_id | 1188 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_notes_attachments | parent_item_id | 1188 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_notes_attachments | payload_sidecar_json | 1188 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_change_events | currency_configuration_currency_iso_code | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events | deleted_at | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events | external_data | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_change_events | parent_record_id | 1054 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_change_events | parent_record_id_hash | 1054 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_change_events | source | 1054 | 100.0 | all_null | expected_optional_no_current_project_usage | change-events | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices | company_id | 981 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_subcontractor_invoices | company_id_hash | 981 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_subcontractor_invoices | currency_configuration_base_currency_iso_code | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoices | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices | currency_configuration_currency_iso_code | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoices | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices | electronic_signature_id | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoices | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices | origin_data | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoices | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices | origin_id | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoices | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices | parent_record_id | 981 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_subcontractor_invoices | parent_record_id_hash | 981 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_subcontractor_invoices | payment_date | 981 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoices | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoices_attachments | company_id | 981 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_subcontractor_invoices_attachments | parent_item_id | 981 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_subcontractor_invoices_attachments | payload_sidecar_json | 981 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_manpower | company_id | 921 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_manpower | company_id_hash | 921 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_manpower | contact | 921 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_manpower | contact_job_title | 921 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-manpower | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_manpower | contact_login_information_id | 921 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-manpower | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_manpower | contact_vendor_name | 921 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-manpower | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_manpower | cost_code | 921 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_manpower | deleted_at | 921 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-manpower | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_manpower | location | 921 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_manpower | parent_record_id | 921 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_manpower | parent_record_id_hash | 921 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_manpower | trade | 921 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-manpower | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_dcrs_attachments | company_id | 783 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_dcrs_attachments | parent_item_id | 783 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_dcrs_attachments | payload_sidecar_json | 783 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_manpower_attachments | company_id | 781 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_manpower_attachments | parent_item_id | 781 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_manpower_attachments | payload_sidecar_json | 781 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspections_attachments | company_id | 363 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspections_attachments | parent_item_id | 363 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspections_attachments | payload_sidecar_json | 363 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_detail_columns | company_id | 276 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_detail_columns | company_id_hash | 276 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_detail_columns | visible | 276 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_commitment_contracts | approval_letter_date | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_contracts | company_id | 243 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_commitment_contracts | company_id_hash | 243 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_commitment_contracts | contract_date | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_contracts | currency_configuration_currency_iso_code | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_contracts | execution_date | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_contracts | issued_on_date | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_contracts | letter_of_intent_date | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_contracts | parent_record_id | 243 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_commitment_contracts | parent_record_id_hash | 243 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_commitment_contracts | returned_date | 243 | 100.0 | all_null | expected_optional_no_current_project_usage | commitment-contracts | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_observations | assignee | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | assignee_vendor | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | company_id | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | company_id_hash | 215 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_observations | deleted_at | 215 | 100.0 | all_null | expected_optional_no_current_project_usage | observations | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_observations | location | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | origin | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | parent_record_id | 215 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_observations | parent_record_id_hash | 215 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_observations | permissions | 215 | 100.0 | all_null | expected_optional_no_current_project_usage | observations | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_observations | specification_section | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | specification_section_viewable_document_id | 215 | 100.0 | all_null | expected_optional_no_current_project_usage | observations | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_observations | trade | 215 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_observations | type_name_translations | 215 | 100.0 | all_null | expected_optional_no_current_project_usage | observations | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_inspections_distribution_members | company_id | 213 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspections_distribution_members | parent_item_id | 213 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspections_distribution_members | payload_sidecar_json | 213 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals_ball_in_court | company_id | 179 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_submittals_ball_in_court | parent_item_id | 179 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_submittals_ball_in_court | payload_sidecar_json | 179 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_subcontractor_invoice_contract_detail_items | comment | 152 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoice-contract-detail-items | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_subcontractor_invoice_contract_detail_items | company_id | 152 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_subcontractor_invoice_contract_detail_items | company_id_hash | 152 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_subcontractor_invoice_contract_detail_items | currency_configuration_currency_iso_code | 152 | 100.0 | all_null | expected_optional_no_current_project_usage | subcontractor-invoice-contract-detail-items | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_budget_modifications | company_id | 148 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_budget_modifications | company_id_hash | 148 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_modifications | origin_data | 148 | 100.0 | all_null | expected_optional_no_current_project_usage | budget-modifications | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_budget_modifications | origin_id | 148 | 100.0 | all_null | expected_optional_no_current_project_usage | budget-modifications | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_budget_modifications | parent_record_id | 148 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_modifications | parent_record_id_hash | 148 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_budget_modifications | payload_sidecar_json | 148 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis_ball_in_courts | company_id | 146 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_rfis_ball_in_courts | parent_item_id | 146 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_rfis_ball_in_courts | payload_sidecar_json | 146 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_sections | company_id | 139 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_inspection_sections | company_id_hash | 139 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_sections | parent_record_id | 139 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_sections | parent_record_id_hash | 139 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_inspection_sections | payload_sidecar_json | 139 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_weather | average | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | calamity | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | comments | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | company_id | 129 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_weather | company_id_hash | 129 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_weather | created_by | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | daily_log_segment | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | daily_log_segment_id | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | deleted_at | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | ground | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | is_weather_delay | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | location | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | parent_record_id | 129 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_weather | parent_record_id_hash | 129 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_weather | precipitation | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | sky | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | temperature | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | vendor | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_weather | wind | 129 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-weather | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_inspections | company_id | 114 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_inspections | company_id_hash | 114 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_inspections | deleted_at | 114 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-inspections | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_daily_log_inspections | location | 114 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |
| procore_ep_daily_log_inspections | parent_record_id | 114 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_inspections | parent_record_id_hash | 114 | 100.0 | all_null | support_or_guardrail_field |  | No remediation; preserve guardrail/provenance semantics. |
| procore_ep_daily_log_inspections | vendor | 114 | 100.0 | all_null | expected_optional_no_current_project_usage | daily-log-inspections | No immediate remediation; document as optional unless new evidence shows missing projection. |
| procore_ep_commitment_compliance_insurance_documents__52b7bf | company_id | 105 | 100.0 | all_null | schema_column_not_in_projection_registry |  | No immediate projection remediation; preserve documented deferral unless separate source-path proof approves mapping or deprecation. |

## Root-Cause Notes

- `procore_ep_budget_detail_row_cells.company_id`: `schema_column_not_in_projection_registry`; rows=225131; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_budget_detail_row_cells.company_id_hash`: `support_or_guardrail_field`; rows=225131; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_detail_row_cells.currency_iso_code`: `schema_column_not_in_projection_registry`; rows=225131; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
  Deferred: `Batch C` / `deferred_budget_detail_convenience_or_optional_field`; Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
- `procore_endpoint_raw_payloads.company_id`: `support_or_guardrail_field`; rows=49287; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_endpoint_raw_payloads.company_id_hash`: `support_or_guardrail_field`; rows=49287; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items_response_set_responses.company_id`: `schema_column_not_in_projection_registry`; rows=10068; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_inspection_items_response_set_responses.parent_item_id`: `support_or_guardrail_field`; rows=10068; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items_response_set_responses.payload_sidecar_json`: `support_or_guardrail_field`; rows=10068; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals_approvers.company_id`: `schema_column_not_in_projection_registry`; rows=7260; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_submittals_approvers.parent_item_id`: `support_or_guardrail_field`; rows=7260; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals_approvers_attachments.company_id`: `schema_column_not_in_projection_registry`; rows=6566; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_submittals_approvers_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=6566; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis_assignees.company_id`: `schema_column_not_in_projection_registry`; rows=3371; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_rfis_assignees.parent_item_id`: `support_or_guardrail_field`; rows=3371; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis_assignees.payload_sidecar_json`: `support_or_guardrail_field`; rows=3371; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items.company_id`: `schema_column_not_in_projection_registry`; rows=3363; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_inspection_items.company_id_hash`: `support_or_guardrail_field`; rows=3363; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_items.company_template_item_details`: `expected_optional_no_current_project_usage`; rows=3363; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.company_template_item_details` inspected=3363 present=3363 missing=0 values_emitted=false.
- `procore_ep_inspection_items.item_response`: `schema_column_not_in_projection_registry`; rows=3363; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_inspection_items.parent_item_id_col`: `expected_optional_no_current_project_usage`; rows=3363; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.parent_item_id` inspected=3363 present=3363 missing=0 values_emitted=false.
- `procore_ep_inspection_items.response`: `schema_column_not_in_projection_registry`; rows=3363; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_inspection_items.response_set`: `schema_column_not_in_projection_registry`; rows=3363; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_change_events_change_items.budget_impact_budget_change`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.budget_impact.budget_change` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.budget_impact_budget_modification`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.budget_impact.budget_modification` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.commitment.currency_configuration.base_currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_currency_exchange_rate`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.commitment.currency_configuration.currency_exchange_rate` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.commitment.currency_configuration.currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_contract_confirmed`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.contract.confirmed` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_non_commitment_amount`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.non_commitment.amount` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.request_for_quote.currency_configuration.base_currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_currency_exchange_rate`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.request_for_quote.currency_configuration.currency_exchange_rate` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.request_for_quote.currency_configuration.currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.cost_impact_vendor_confirmed`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.cost_impact.vendor.confirmed` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.currency_configuration.currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.deleted_at`: `registry_path_not_present_in_payload`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads contain the parent path without this leaf.
  Path presence: `$.change_items.deleted_at` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.parent_item_id`: `support_or_guardrail_field`; rows=2816; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.revenue_impact.change_order.currency_configuration.base_currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_currency_exchange_rate`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.revenue_impact.change_order.currency_configuration.currency_exchange_rate` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=2816; null_rate=100.0%; Registry path was mapped, but current raw payloads do not show usage for this path.
  Path presence: `$.change_items.revenue_impact.change_order.currency_configuration.currency_iso_code` inspected=2652 present=0 missing=2652 values_emitted=false.
- `procore_ep_daily_log_dcrs.company_id`: `schema_column_not_in_projection_registry`; rows=2623; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_dcrs.company_id_hash`: `support_or_guardrail_field`; rows=2623; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_dcrs.deleted_at`: `expected_optional_no_current_project_usage`; rows=2623; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=2623 present=2623 missing=0 values_emitted=false.
- `procore_ep_daily_log_dcrs.location`: `expected_optional_no_current_project_usage`; rows=2623; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.location` inspected=2623 present=2623 missing=0 values_emitted=false.
- `procore_ep_daily_log_dcrs.parent_record_id`: `support_or_guardrail_field`; rows=2623; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_dcrs.parent_record_id_hash`: `support_or_guardrail_field`; rows=2623; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_detail_rows.actual_cost`: `schema_column_not_in_projection_registry`; rows=2496; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
  Deferred: `Batch C` / `deferred_budget_detail_convenience_or_optional_field`; Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
- `procore_ep_budget_detail_rows.company_id`: `schema_column_not_in_projection_registry`; rows=2496; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_budget_detail_rows.company_id_hash`: `support_or_guardrail_field`; rows=2496; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_detail_rows.cost_type`: `schema_column_not_in_projection_registry`; rows=2496; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
  Deferred: `Batch C` / `deferred_budget_detail_convenience_or_optional_field`; Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
- `procore_ep_budget_detail_rows.cost_type_id`: `schema_column_not_in_projection_registry`; rows=2496; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
  Deferred: `Batch C` / `deferred_budget_detail_convenience_or_optional_field`; Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
- `procore_ep_budget_detail_rows.line_item_type_id`: `schema_column_not_in_projection_registry`; rows=2496; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
  Deferred: `Batch C` / `deferred_budget_detail_convenience_or_optional_field`; Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
- `procore_ep_change_events_attachments.parent_item_id`: `support_or_guardrail_field`; rows=2335; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=2335; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events_markup_items.parent_item_id`: `support_or_guardrail_field`; rows=2150; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.company_id`: `schema_column_not_in_projection_registry`; rows=1960; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_rfis.company_id_hash`: `support_or_guardrail_field`; rows=1960; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.connect_export_origin`: `expected_optional_no_current_project_usage`; rows=1960; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.connect_export_origin` inspected=1992 present=1992 missing=0 values_emitted=false.
- `procore_ep_rfis.parent_record_id`: `support_or_guardrail_field`; rows=1960; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.parent_record_id_hash`: `support_or_guardrail_field`; rows=1960; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis.prefix`: `expected_optional_no_current_project_usage`; rows=1960; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.prefix` inspected=1992 present=1992 missing=0 values_emitted=false.
- `procore_ep_rfis.priority_name`: `expected_optional_no_current_project_usage`; rows=1960; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.priority.name` inspected=1992 present=1992 missing=0 values_emitted=false.
- `procore_ep_rfis.priority_value`: `expected_optional_no_current_project_usage`; rows=1960; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.priority.value` inspected=1992 present=1992 missing=0 values_emitted=false.
- `procore_ep_rfis.project_stage_formatted_parent_name`: `expected_optional_no_current_project_usage`; rows=1960; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.project_stage.formatted_parent_name` inspected=1992 present=469 missing=1523 values_emitted=false.
- `procore_ep_rfis.project_stage_parent_id`: `expected_optional_no_current_project_usage`; rows=1960; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.project_stage.parent_id` inspected=1992 present=469 missing=1523 values_emitted=false.
- `procore_ep_rfis_questions.company_id`: `schema_column_not_in_projection_registry`; rows=1960; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_rfis_questions.parent_item_id`: `support_or_guardrail_field`; rows=1960; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.buffer_time`: `expected_optional_no_current_project_usage`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.buffer_time` inspected=1872 present=1872 missing=0 values_emitted=false.
- `procore_ep_submittals.company_id`: `schema_column_not_in_projection_registry`; rows=1760; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_submittals.company_id_hash`: `support_or_guardrail_field`; rows=1760; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.location_parent_id`: `expected_optional_no_current_project_usage`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.location.parent_id` inspected=1872 present=157 missing=1715 values_emitted=false.
- `procore_ep_submittals.parent_record_id`: `support_or_guardrail_field`; rows=1760; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.parent_record_id_hash`: `support_or_guardrail_field`; rows=1760; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals.rejected_submittal_log_approver_id`: `expected_optional_no_current_project_usage`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.rejected_submittal_log_approver_id` inspected=1872 present=1872 missing=0 values_emitted=false.
- `procore_ep_submittals.scheduled_task`: `expected_optional_no_current_project_usage`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.scheduled_task` inspected=1872 present=1872 missing=0 values_emitted=false.
- `procore_ep_submittals.sub_job`: `expected_optional_no_current_project_usage`; rows=1760; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.sub_job` inspected=1872 present=1872 missing=0 values_emitted=false.
- `procore_ep_submittals.submittal_package`: `schema_column_not_in_projection_registry`; rows=1760; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_submittals.submittal_workflow_template`: `schema_column_not_in_projection_registry`; rows=1760; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_daily_log_notes_attachments.company_id`: `schema_column_not_in_projection_registry`; rows=1188; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_notes_attachments.parent_item_id`: `support_or_guardrail_field`; rows=1188; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_notes_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=1188; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.currency_iso_code` inspected=2652 present=2652 missing=0 values_emitted=false.
- `procore_ep_change_events.deleted_at`: `expected_optional_no_current_project_usage`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=2652 present=2652 missing=0 values_emitted=false.
- `procore_ep_change_events.external_data`: `expected_optional_no_current_project_usage`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.external_data` inspected=2652 present=2652 missing=0 values_emitted=false.
- `procore_ep_change_events.parent_record_id`: `support_or_guardrail_field`; rows=1054; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events.parent_record_id_hash`: `support_or_guardrail_field`; rows=1054; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_change_events.source`: `expected_optional_no_current_project_usage`; rows=1054; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.source` inspected=2652 present=2652 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.company_id`: `schema_column_not_in_projection_registry`; rows=981; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_subcontractor_invoices.company_id_hash`: `support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices.currency_configuration_base_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.base_currency_iso_code` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.currency_iso_code` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.electronic_signature_id`: `expected_optional_no_current_project_usage`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.electronic_signature_id` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.origin_data`: `expected_optional_no_current_project_usage`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.origin_data` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.origin_id`: `expected_optional_no_current_project_usage`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.origin_id` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices.parent_record_id`: `support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices.parent_record_id_hash`: `support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices.payment_date`: `expected_optional_no_current_project_usage`; rows=981; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.payment_date` inspected=1034 present=1034 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoices_attachments.company_id`: `schema_column_not_in_projection_registry`; rows=981; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_subcontractor_invoices_attachments.parent_item_id`: `support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoices_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=981; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower.company_id`: `schema_column_not_in_projection_registry`; rows=921; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_manpower.company_id_hash`: `support_or_guardrail_field`; rows=921; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower.contact`: `schema_column_not_in_projection_registry`; rows=921; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_daily_log_manpower.contact_job_title`: `expected_optional_no_current_project_usage`; rows=921; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.contact.job_title` inspected=921 present=920 missing=1 values_emitted=false.
- `procore_ep_daily_log_manpower.contact_login_information_id`: `expected_optional_no_current_project_usage`; rows=921; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.contact.login_information_id` inspected=921 present=920 missing=1 values_emitted=false.
- `procore_ep_daily_log_manpower.contact_vendor_name`: `expected_optional_no_current_project_usage`; rows=921; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.contact.vendor_name` inspected=921 present=920 missing=1 values_emitted=false.
- `procore_ep_daily_log_manpower.cost_code`: `schema_column_not_in_projection_registry`; rows=921; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_daily_log_manpower.deleted_at`: `expected_optional_no_current_project_usage`; rows=921; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=921 present=921 missing=0 values_emitted=false.
- `procore_ep_daily_log_manpower.location`: `schema_column_not_in_projection_registry`; rows=921; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_daily_log_manpower.parent_record_id`: `support_or_guardrail_field`; rows=921; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower.parent_record_id_hash`: `support_or_guardrail_field`; rows=921; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower.trade`: `expected_optional_no_current_project_usage`; rows=921; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.trade` inspected=921 present=921 missing=0 values_emitted=false.
- `procore_ep_daily_log_dcrs_attachments.company_id`: `schema_column_not_in_projection_registry`; rows=783; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_dcrs_attachments.parent_item_id`: `support_or_guardrail_field`; rows=783; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_dcrs_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=783; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower_attachments.company_id`: `schema_column_not_in_projection_registry`; rows=781; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_manpower_attachments.parent_item_id`: `support_or_guardrail_field`; rows=781; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_manpower_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=781; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspections_attachments.company_id`: `schema_column_not_in_projection_registry`; rows=363; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_inspections_attachments.parent_item_id`: `support_or_guardrail_field`; rows=363; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspections_attachments.payload_sidecar_json`: `support_or_guardrail_field`; rows=363; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_detail_columns.company_id`: `schema_column_not_in_projection_registry`; rows=276; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_budget_detail_columns.company_id_hash`: `support_or_guardrail_field`; rows=276; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_detail_columns.visible`: `schema_column_not_in_projection_registry`; rows=276; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
  Deferred: `Batch C` / `deferred_budget_detail_convenience_or_optional_field`; Reviewed Budget Detail field; Batch 2 triage did not prove a stable row-level source requiring projection into this convenience column.
- `procore_ep_commitment_contracts.approval_letter_date`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.approval_letter_date` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_commitment_contracts.company_id`: `schema_column_not_in_projection_registry`; rows=243; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_commitment_contracts.company_id_hash`: `support_or_guardrail_field`; rows=243; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_commitment_contracts.contract_date`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.contract_date` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_commitment_contracts.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.currency_iso_code` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_commitment_contracts.execution_date`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.execution_date` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_commitment_contracts.issued_on_date`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.issued_on_date` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_commitment_contracts.letter_of_intent_date`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.letter_of_intent_date` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_commitment_contracts.parent_record_id`: `support_or_guardrail_field`; rows=243; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_commitment_contracts.parent_record_id_hash`: `support_or_guardrail_field`; rows=243; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_commitment_contracts.returned_date`: `expected_optional_no_current_project_usage`; rows=243; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.returned_date` inspected=346 present=346 missing=0 values_emitted=false.
- `procore_ep_observations.assignee`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_observations.assignee_vendor`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_observations.company_id`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_observations.company_id_hash`: `support_or_guardrail_field`; rows=215; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_observations.deleted_at`: `expected_optional_no_current_project_usage`; rows=215; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=215 present=215 missing=0 values_emitted=false.
- `procore_ep_observations.location`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_observations.origin`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_observations.parent_record_id`: `support_or_guardrail_field`; rows=215; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_observations.parent_record_id_hash`: `support_or_guardrail_field`; rows=215; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_observations.permissions`: `expected_optional_no_current_project_usage`; rows=215; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.permissions` inspected=215 present=215 missing=0 values_emitted=false.
- `procore_ep_observations.specification_section`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_observations.specification_section_viewable_document_id`: `expected_optional_no_current_project_usage`; rows=215; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.specification_section.viewable_document_id` inspected=215 present=9 missing=206 values_emitted=false.
- `procore_ep_observations.trade`: `schema_column_not_in_projection_registry`; rows=215; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_observations.type_name_translations`: `expected_optional_no_current_project_usage`; rows=215; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.type.name_translations` inspected=215 present=215 missing=0 values_emitted=false.
- `procore_ep_inspections_distribution_members.company_id`: `schema_column_not_in_projection_registry`; rows=213; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_inspections_distribution_members.parent_item_id`: `support_or_guardrail_field`; rows=213; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspections_distribution_members.payload_sidecar_json`: `support_or_guardrail_field`; rows=213; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals_ball_in_court.company_id`: `schema_column_not_in_projection_registry`; rows=179; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_submittals_ball_in_court.parent_item_id`: `support_or_guardrail_field`; rows=179; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_submittals_ball_in_court.payload_sidecar_json`: `support_or_guardrail_field`; rows=179; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoice_contract_detail_items.comment`: `expected_optional_no_current_project_usage`; rows=152; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.comment` inspected=152 present=152 missing=0 values_emitted=false.
- `procore_ep_subcontractor_invoice_contract_detail_items.company_id`: `schema_column_not_in_projection_registry`; rows=152; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_subcontractor_invoice_contract_detail_items.company_id_hash`: `support_or_guardrail_field`; rows=152; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_subcontractor_invoice_contract_detail_items.currency_configuration_currency_iso_code`: `expected_optional_no_current_project_usage`; rows=152; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.currency_configuration.currency_iso_code` inspected=152 present=152 missing=0 values_emitted=false.
- `procore_ep_budget_modifications.company_id`: `schema_column_not_in_projection_registry`; rows=148; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_budget_modifications.company_id_hash`: `support_or_guardrail_field`; rows=148; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_modifications.origin_data`: `expected_optional_no_current_project_usage`; rows=148; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.origin_data` inspected=148 present=148 missing=0 values_emitted=false.
- `procore_ep_budget_modifications.origin_id`: `expected_optional_no_current_project_usage`; rows=148; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.origin_id` inspected=148 present=148 missing=0 values_emitted=false.
- `procore_ep_budget_modifications.parent_record_id`: `support_or_guardrail_field`; rows=148; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_modifications.parent_record_id_hash`: `support_or_guardrail_field`; rows=148; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_budget_modifications.payload_sidecar_json`: `support_or_guardrail_field`; rows=148; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis_ball_in_courts.company_id`: `schema_column_not_in_projection_registry`; rows=146; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_rfis_ball_in_courts.parent_item_id`: `support_or_guardrail_field`; rows=146; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_rfis_ball_in_courts.payload_sidecar_json`: `support_or_guardrail_field`; rows=146; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_sections.company_id`: `schema_column_not_in_projection_registry`; rows=139; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_inspection_sections.company_id_hash`: `support_or_guardrail_field`; rows=139; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_sections.parent_record_id`: `support_or_guardrail_field`; rows=139; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_sections.parent_record_id_hash`: `support_or_guardrail_field`; rows=139; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_inspection_sections.payload_sidecar_json`: `support_or_guardrail_field`; rows=139; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_weather.average`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.average` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.calamity`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.calamity` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.comments`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.comments` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.company_id`: `schema_column_not_in_projection_registry`; rows=129; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_weather.company_id_hash`: `support_or_guardrail_field`; rows=129; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_weather.created_by`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.created_by` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.daily_log_segment`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.daily_log_segment` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.daily_log_segment_id`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.daily_log_segment_id` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.deleted_at`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.ground`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.ground` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.is_weather_delay`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.is_weather_delay` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.location`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.location` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.parent_record_id`: `support_or_guardrail_field`; rows=129; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_weather.parent_record_id_hash`: `support_or_guardrail_field`; rows=129; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_weather.precipitation`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.precipitation` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.sky`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.sky` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.temperature`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.temperature` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.vendor`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.vendor` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_weather.wind`: `expected_optional_no_current_project_usage`; rows=129; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.wind` inspected=129 present=129 missing=0 values_emitted=false.
- `procore_ep_daily_log_inspections.company_id`: `schema_column_not_in_projection_registry`; rows=114; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
- `procore_ep_daily_log_inspections.company_id_hash`: `support_or_guardrail_field`; rows=114; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_inspections.deleted_at`: `expected_optional_no_current_project_usage`; rows=114; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.deleted_at` inspected=114 present=114 missing=0 values_emitted=false.
- `procore_ep_daily_log_inspections.location`: `schema_column_not_in_projection_registry`; rows=114; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
  Deferred: `Batch B` / `documented_object_container_or_child_field_decomposition`; Reviewed high-value operational object/container field; registry projects scalar child fields or child rows instead of promoting the bare object container column.
- `procore_ep_daily_log_inspections.parent_record_id`: `support_or_guardrail_field`; rows=114; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_inspections.parent_record_id_hash`: `support_or_guardrail_field`; rows=114; null_rate=100.0%; Metadata, provenance, guardrail, or support-table field.
- `procore_ep_daily_log_inspections.vendor`: `expected_optional_no_current_project_usage`; rows=114; null_rate=100.0%; Registry path is present only as null/empty in current raw payloads.
  Path presence: `$.vendor` inspected=114 present=114 missing=0 values_emitted=false.
- `procore_ep_commitment_compliance_insurance_documents__52b7bf.company_id`: `schema_column_not_in_projection_registry`; rows=105; null_rate=100.0%; Explicitly deferred with documented rationale: Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.
  Deferred: `Batch C` / `deferred_broad_company_id_policy`; Reviewed broad company_id field; no global company_id propagation/backfill is applied without a separately approved table convention proof.

## Table-by-Table Null Profile

| table | rows | columns | all-null columns | suspected defects |
| --- | ---: | ---: | ---: | ---: |
| procore_endpoint_capture_errors | 0 | 10 | 10 | 0 |
| procore_endpoint_capture_pages | 0 | 14 | 14 | 0 |
| procore_endpoint_capture_runs | 0 | 18 | 18 | 0 |
| procore_endpoint_contracts | 0 | 20 | 20 | 0 |
| procore_endpoint_raw_payloads | 49287 | 36 | 2 | 0 |
| procore_ep_billing_periods | 20 | 31 | 5 | 0 |
| procore_ep_budget_change_history | 95 | 32 | 5 | 0 |
| procore_ep_budget_detail_columns | 276 | 33 | 3 | 0 |
| procore_ep_budget_detail_row_cells | 225131 | 30 | 3 | 0 |
| procore_ep_budget_detail_rows | 2496 | 52 | 6 | 0 |
| procore_ep_budget_modifications | 148 | 32 | 7 | 0 |
| procore_ep_budget_views | 35 | 33 | 4 | 0 |
| procore_ep_change_events | 1054 | 55 | 6 | 0 |
| procore_ep_change_events_attachments | 2335 | 23 | 2 | 0 |
| procore_ep_change_events_change_items | 2816 | 139 | 17 | 0 |
| procore_ep_change_events_change_items_budget_code_seg_2dff22 | 8448 | 25 | 0 | 0 |
| procore_ep_change_events_markup_items | 2150 | 31 | 1 | 0 |
| procore_ep_change_events_markup_items_wbs_code_segment_items | 6450 | 25 | 0 | 0 |
| procore_ep_commitment_attachments | 16 | 28 | 3 | 0 |
| procore_ep_commitment_change_orders | 100 | 68 | 12 | 0 |
| procore_ep_commitment_compliance | 7 | 32 | 9 | 0 |
| procore_ep_commitment_compliance_insurance_documents | 58 | 28 | 3 | 0 |
| procore_ep_commitment_compliance_insurance_documents__52b7bf | 105 | 24 | 2 | 0 |
| procore_ep_commitment_contracts | 243 | 72 | 11 | 0 |
| procore_ep_commitment_line_items | 63 | 38 | 5 | 0 |
| procore_ep_daily_log_dcrs | 2623 | 56 | 6 | 0 |
| procore_ep_daily_log_dcrs_attachments | 783 | 28 | 3 | 0 |
| procore_ep_daily_log_deliveries | 59 | 43 | 8 | 0 |
| procore_ep_daily_log_deliveries_attachments | 18 | 28 | 3 | 0 |
| procore_ep_daily_log_inspections | 114 | 52 | 7 | 0 |
| procore_ep_daily_log_inspections_attachments | 14 | 28 | 3 | 0 |
| procore_ep_daily_log_manpower | 921 | 62 | 12 | 0 |
| procore_ep_daily_log_manpower_attachments | 781 | 28 | 3 | 0 |
| procore_ep_daily_log_notes | 92 | 46 | 7 | 0 |
| procore_ep_daily_log_notes_attachments | 1188 | 28 | 3 | 0 |
| procore_ep_daily_log_visitor | 2 | 43 | 7 | 0 |
| procore_ep_daily_log_weather | 129 | 49 | 19 | 0 |
| procore_ep_inspection_items | 3363 | 64 | 7 | 0 |
| procore_ep_inspection_items_response_set_responses | 10068 | 24 | 3 | 0 |
| procore_ep_inspection_sections | 139 | 28 | 5 | 0 |
| procore_ep_inspections | 74 | 91 | 17 | 0 |
| procore_ep_inspections_attachments | 363 | 30 | 3 | 0 |
| procore_ep_inspections_distribution_members | 213 | 24 | 3 | 0 |
| procore_ep_inspections_inspectors | 101 | 24 | 3 | 0 |
| procore_ep_inspections_signature_requests | 8 | 33 | 3 | 0 |
| procore_ep_meetings | 97 | 45 | 6 | 0 |
| procore_ep_observations | 215 | 77 | 14 | 0 |
| procore_ep_observations_assignees | 7 | 25 | 3 | 0 |
| procore_ep_prime_change_order_line_items | 2 | 37 | 4 | 0 |
| procore_ep_prime_change_orders | 63 | 66 | 14 | 0 |
| procore_ep_prime_contract_line_items | 47 | 34 | 5 | 0 |
| procore_ep_prime_contracts | 6 | 113 | 39 | 0 |
| procore_ep_projects | 14 | 88 | 13 | 0 |
| procore_ep_projects_custom_fields_custom_field_163287_value | 10 | 23 | 3 | 0 |
| procore_ep_projects_custom_fields_custom_field_163290_value | 6 | 23 | 3 | 0 |
| procore_ep_projects_custom_fields_custom_field_163293_value | 4 | 23 | 3 | 0 |
| procore_ep_projects_custom_fields_custom_field_163296_value | 2 | 23 | 3 | 0 |
| procore_ep_projects_custom_fields_custom_field_163299_value | 2 | 23 | 3 | 0 |
| procore_ep_projects_custom_fields_custom_field_163302_value | 2 | 23 | 3 | 0 |
| procore_ep_projects_custom_fields_custom_field_163305_value | 2 | 23 | 3 | 0 |
| procore_ep_punch_items | 36 | 75 | 14 | 0 |
| procore_ep_punch_items_assignees | 48 | 25 | 4 | 0 |
| procore_ep_punch_items_assignments | 48 | 38 | 2 | 0 |
| procore_ep_punch_items_ball_in_court | 23 | 25 | 4 | 0 |
| procore_ep_purchase_order_contracts | 10 | 128 | 38 | 0 |
| procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65 | 1 | 23 | 3 | 0 |
| procore_ep_purchase_order_line_items | 12 | 63 | 4 | 0 |
| procore_ep_purchase_order_line_items_cost_code_line_i_779dbd | 24 | 25 | 3 | 0 |
| procore_ep_rfis | 1960 | 95 | 10 | 0 |
| procore_ep_rfis_assignees | 3371 | 25 | 3 | 0 |
| procore_ep_rfis_ball_in_courts | 146 | 24 | 3 | 0 |
| procore_ep_rfis_questions | 1960 | 22 | 2 | 0 |
| procore_ep_rfqs | 7 | 105 | 11 | 0 |
| procore_ep_rfqs_attachments | 11 | 24 | 3 | 0 |
| procore_ep_rfqs_change_event_attachments | 31 | 24 | 3 | 0 |
| procore_ep_rfqs_change_event_change_event_line_items | 52 | 120 | 13 | 0 |
| procore_ep_rfqs_change_event_change_event_line_items__0a3e8d | 57 | 25 | 2 | 0 |
| procore_ep_schedules | 1 | 38 | 6 | 0 |
| procore_ep_subcontractor_invoice_change_order_items | 24 | 55 | 4 | 0 |
| procore_ep_subcontractor_invoice_contract_detail_items | 152 | 52 | 4 | 0 |
| procore_ep_subcontractor_invoices | 981 | 83 | 10 | 0 |
| procore_ep_subcontractor_invoices_attachments | 981 | 25 | 3 | 0 |
| procore_ep_submittals | 1760 | 108 | 11 | 0 |
| procore_ep_submittals_approvers | 7260 | 35 | 2 | 0 |
| procore_ep_submittals_approvers_attachments | 6566 | 24 | 2 | 0 |
| procore_ep_submittals_ball_in_court | 179 | 24 | 3 | 0 |

## Body-Free Privacy Attestation

- Raw payload JSON was inspected only for key/path presence counts.
- The JSON and Markdown reports emit path names and counts only, not payload fragments or values.
- `raw_payload_values_emitted` is `false` for every column/path record.

## Remediation Not Applied

No schema, registry, migration, projection, scheduled-refresh, live-fetch, or read-model remediation was applied by this audit.
