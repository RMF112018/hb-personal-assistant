# Procore Null Projection Audit Delta

## Executive Summary

- Prior suspected projection defects: `128`
- Current suspected projection defects: `125`
- Resolved suspected defects: `3`
- New suspected defects: `0`
- No remediation was applied during this audit delta.
- No live calls, scheduler, SourceRefreshOrchestrator, Budget Detail refresh/reconciliation, or writeback path was used.

## Defects Resolved By Prior Batches

| Field | Resolution Bucket | Prior Root Cause | Prior Rows |
| --- | --- | --- | ---: |
| `procore_ep_change_events_change_items.cost_impact_contract_confirmed` | `change_event_mapping` | `schema_column_not_in_projection_registry` | 2816 |
| `procore_ep_change_events_change_items.cost_impact_vendor_confirmed` | `change_event_mapping` | `schema_column_not_in_projection_registry` | 2816 |
| `procore_ep_prime_contracts.show_line_items_to_non_admins` | `batch1_endpoint_replay` | `registry_path_present_but_projection_not_writing` | 5 |

## New Or Reclassified Suspected Defects

| Field | Current Root Cause | Prior Root Cause | Rows | Note |
| --- | --- | --- | ---: | --- |
| _None_ |  |  |  |  |

## Remaining Suspected Defects By Root Cause

### registry_path_present_but_projection_not_writing

| Field | Endpoint | Rows | Null Rate |
| --- | --- | ---: | ---: |
| `procore_ep_punch_items.closed_at` | `punch-items` | 23 | 1.0 |
| `procore_ep_punch_items.closed_by` | `punch-items` | 23 | 1.0 |

### schema_column_not_in_projection_registry

| Field | Endpoint | Rows | Null Rate |
| --- | --- | ---: | ---: |
| `procore_ep_budget_detail_row_cells.company_id` | `` | 225131 | 1.0 |
| `procore_ep_budget_detail_row_cells.currency_iso_code` | `` | 225131 | 1.0 |
| `procore_ep_inspection_items_response_set_responses.company_id` | `` | 10068 | 1.0 |
| `procore_ep_submittals_approvers.company_id` | `` | 7260 | 1.0 |
| `procore_ep_submittals_approvers_attachments.company_id` | `` | 6566 | 1.0 |
| `procore_ep_rfis_assignees.company_id` | `` | 3371 | 1.0 |
| `procore_ep_inspection_items.company_id` | `` | 3363 | 1.0 |
| `procore_ep_inspection_items.item_response` | `` | 3363 | 1.0 |
| `procore_ep_inspection_items.response` | `` | 3363 | 1.0 |
| `procore_ep_inspection_items.response_set` | `` | 3363 | 1.0 |
| `procore_ep_daily_log_dcrs.company_id` | `` | 2623 | 1.0 |
| `procore_ep_budget_detail_rows.actual_cost` | `` | 2496 | 1.0 |
| `procore_ep_budget_detail_rows.company_id` | `` | 2496 | 1.0 |
| `procore_ep_budget_detail_rows.cost_type` | `` | 2496 | 1.0 |
| `procore_ep_budget_detail_rows.cost_type_id` | `` | 2496 | 1.0 |
| `procore_ep_budget_detail_rows.line_item_type_id` | `` | 2496 | 1.0 |
| `procore_ep_rfis.ball_in_court` | `` | 1960 | 0.972449 |
| `procore_ep_rfis.company_id` | `` | 1960 | 1.0 |
| `procore_ep_rfis.cost_code` | `` | 1960 | 0.984694 |
| `procore_ep_rfis.location` | `` | 1960 | 0.961224 |
| `procore_ep_rfis.sub_job` | `` | 1960 | 0.967857 |
| `procore_ep_rfis_questions.company_id` | `` | 1960 | 1.0 |
| `procore_ep_submittals.company_id` | `` | 1760 | 1.0 |
| `procore_ep_submittals.location` | `` | 1760 | 0.981818 |
| `procore_ep_submittals.submittal_package` | `` | 1760 | 1.0 |
| `procore_ep_submittals.submittal_workflow_template` | `` | 1760 | 1.0 |
| `procore_ep_daily_log_notes_attachments.company_id` | `` | 1188 | 1.0 |
| `procore_ep_change_events.event_origin` | `` | 1054 | 0.995256 |
| `procore_ep_subcontractor_invoices.company_id` | `` | 981 | 1.0 |
| `procore_ep_subcontractor_invoices_attachments.company_id` | `` | 981 | 1.0 |
| `procore_ep_daily_log_manpower.company_id` | `` | 921 | 1.0 |
| `procore_ep_daily_log_manpower.contact` | `` | 921 | 1.0 |
| `procore_ep_daily_log_manpower.cost_code` | `` | 921 | 1.0 |
| `procore_ep_daily_log_manpower.location` | `` | 921 | 1.0 |
| `procore_ep_daily_log_dcrs_attachments.company_id` | `` | 783 | 1.0 |
| `procore_ep_daily_log_manpower_attachments.company_id` | `` | 781 | 1.0 |
| `procore_ep_inspections_attachments.company_id` | `` | 363 | 1.0 |
| `procore_ep_budget_detail_columns.company_id` | `` | 276 | 1.0 |
| `procore_ep_budget_detail_columns.visible` | `` | 276 | 1.0 |
| `procore_ep_commitment_contracts.company_id` | `` | 243 | 1.0 |
| `procore_ep_observations.assignee` | `` | 215 | 1.0 |
| `procore_ep_observations.assignee_vendor` | `` | 215 | 1.0 |
| `procore_ep_observations.company_id` | `` | 215 | 1.0 |
| `procore_ep_observations.location` | `` | 215 | 1.0 |
| `procore_ep_observations.origin` | `` | 215 | 1.0 |
| `procore_ep_observations.specification_section` | `` | 215 | 1.0 |
| `procore_ep_observations.trade` | `` | 215 | 1.0 |
| `procore_ep_inspections_distribution_members.company_id` | `` | 213 | 1.0 |
| `procore_ep_submittals_ball_in_court.company_id` | `` | 179 | 1.0 |
| `procore_ep_subcontractor_invoice_contract_detail_items.company_id` | `` | 152 | 1.0 |
| `procore_ep_budget_modifications.company_id` | `` | 148 | 1.0 |
| `procore_ep_rfis_ball_in_courts.company_id` | `` | 146 | 1.0 |
| `procore_ep_inspection_sections.company_id` | `` | 139 | 1.0 |
| `procore_ep_daily_log_weather.company_id` | `` | 129 | 1.0 |
| `procore_ep_daily_log_inspections.company_id` | `` | 114 | 1.0 |
| `procore_ep_daily_log_inspections.location` | `` | 114 | 1.0 |
| `procore_ep_commitment_compliance_insurance_documents__52b7bf.company_id` | `` | 105 | 1.0 |
| `procore_ep_inspections_inspectors.company_id` | `` | 101 | 1.0 |
| `procore_ep_commitment_change_orders.change_order_change_reason` | `` | 100 | 1.0 |
| `procore_ep_commitment_change_orders.company_id` | `` | 100 | 1.0 |
| `procore_ep_commitment_change_orders.designated_reviewer` | `` | 100 | 1.0 |
| `procore_ep_commitment_change_orders.received_from` | `` | 100 | 1.0 |
| `procore_ep_commitment_change_orders.reviewed_by` | `` | 100 | 1.0 |
| `procore_ep_meetings.company_id` | `` | 97 | 1.0 |
| `procore_ep_meetings.distributed_by` | `` | 97 | 1.0 |
| `procore_ep_budget_change_history.company_id` | `` | 95 | 1.0 |
| `procore_ep_daily_log_notes.company_id` | `` | 92 | 1.0 |
| `procore_ep_daily_log_notes.location` | `` | 92 | 1.0 |
| `procore_ep_inspections.closed_by` | `` | 74 | 1.0 |
| `procore_ep_inspections.company_id` | `` | 74 | 1.0 |
| `procore_ep_inspections.location` | `` | 74 | 1.0 |
| `procore_ep_inspections.point_of_contact` | `` | 74 | 1.0 |
| `procore_ep_inspections.responsible_contractor` | `` | 74 | 1.0 |
| `procore_ep_inspections.specification_section` | `` | 74 | 1.0 |
| `procore_ep_inspections.trade` | `` | 74 | 1.0 |
| `procore_ep_commitment_line_items.company_id` | `` | 63 | 1.0 |
| `procore_ep_prime_change_orders.change_order_change_reason` | `` | 63 | 1.0 |
| `procore_ep_prime_change_orders.company_id` | `` | 63 | 1.0 |
| `procore_ep_prime_change_orders.designated_reviewer` | `` | 63 | 1.0 |
| `procore_ep_prime_change_orders.received_from` | `` | 63 | 1.0 |
| `procore_ep_daily_log_deliveries.company_id` | `` | 59 | 1.0 |
| `procore_ep_commitment_compliance_insurance_documents.company_id` | `` | 58 | 1.0 |
| `procore_ep_rfqs_change_event_change_event_line_items__0a3e8d.company_id` | `` | 57 | 1.0 |
| `procore_ep_rfqs_change_event_change_event_line_items.company_id` | `` | 52 | 1.0 |
| `procore_ep_prime_contract_line_items.company_id` | `` | 47 | 1.0 |
| `procore_ep_budget_views.company_id` | `` | 35 | 1.0 |
| `procore_ep_punch_items_assignees.company_id` | `` | 32 | 1.0 |
| `procore_ep_punch_items_assignments.company_id` | `` | 32 | 1.0 |
| `procore_ep_rfqs_change_event_attachments.company_id` | `` | 31 | 1.0 |
| `procore_ep_purchase_order_line_items_cost_code_line_i_779dbd.company_id` | `` | 24 | 1.0 |
| `procore_ep_subcontractor_invoice_change_order_items.company_id` | `` | 24 | 1.0 |
| `procore_ep_punch_items.company_id` | `` | 23 | 1.0 |
| `procore_ep_punch_items_ball_in_court.company_id` | `` | 23 | 1.0 |
| `procore_ep_billing_periods.company_id` | `` | 20 | 1.0 |
| `procore_ep_daily_log_deliveries_attachments.company_id` | `` | 18 | 1.0 |
| `procore_ep_commitment_attachments.company_id` | `` | 16 | 1.0 |
| `procore_ep_daily_log_inspections_attachments.company_id` | `` | 14 | 1.0 |
| `procore_ep_projects.company_id` | `` | 14 | 1.0 |
| `procore_ep_projects.project_stage` | `` | 14 | 1.0 |
| `procore_ep_purchase_order_line_items.company_id` | `` | 12 | 1.0 |
| `procore_ep_rfqs_attachments.company_id` | `` | 11 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163287_value.company_id` | `` | 10 | 1.0 |
| `procore_ep_purchase_order_contracts.assignee` | `` | 10 | 1.0 |
| `procore_ep_purchase_order_contracts.company_id` | `` | 10 | 1.0 |
| `procore_ep_purchase_order_contracts.custom_fields_custom_field_214072_value` | `` | 10 | 1.0 |
| `procore_ep_purchase_order_contracts.custom_fields_custom_field_214078_value` | `` | 10 | 1.0 |
| `procore_ep_purchase_order_contracts.custom_fields_custom_field_214087_value` | `` | 10 | 1.0 |
| `procore_ep_inspections_signature_requests.company_id` | `` | 8 | 1.0 |
| `procore_ep_inspections_signature_requests.signature` | `` | 8 | 1.0 |
| `procore_ep_commitment_compliance.company_id` | `` | 7 | 1.0 |
| `procore_ep_observations_assignees.company_id` | `` | 7 | 1.0 |
| `procore_ep_observations_assignees.vendor` | `` | 7 | 1.0 |
| `procore_ep_rfqs.company_id` | `` | 7 | 1.0 |
| `procore_ep_prime_contracts.company_id` | `` | 6 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163290_value.company_id` | `` | 6 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163293_value.company_id` | `` | 4 | 1.0 |
| `procore_ep_daily_log_visitor.company_id` | `` | 2 | 1.0 |
| `procore_ep_prime_change_order_line_items.company_id` | `` | 2 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163296_value.company_id` | `` | 2 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163299_value.company_id` | `` | 2 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163302_value.company_id` | `` | 2 | 1.0 |
| `procore_ep_projects_custom_fields_custom_field_163305_value.company_id` | `` | 2 | 1.0 |
| `procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65.company_id` | `` | 1 | 1.0 |

## Remaining High-Priority Candidates

| Field | Endpoint | Root Cause | Rows | Next Step |
| --- | --- | --- | ---: | --- |
| `procore_ep_punch_items.closed_at` | `punch-items` | `registry_path_present_but_projection_not_writing` | 23 | Investigate projection extraction/write path for this mapped field. |
| `procore_ep_punch_items.closed_by` | `punch-items` | `registry_path_present_but_projection_not_writing` | 23 | Investigate projection extraction/write path for this mapped field. |
| `procore_ep_budget_detail_row_cells.company_id` | `` | `schema_column_not_in_projection_registry` | 225131 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_budget_detail_row_cells.currency_iso_code` | `` | `schema_column_not_in_projection_registry` | 225131 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_inspection_items_response_set_responses.company_id` | `` | `schema_column_not_in_projection_registry` | 10068 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_submittals_approvers.company_id` | `` | `schema_column_not_in_projection_registry` | 7260 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_submittals_approvers_attachments.company_id` | `` | `schema_column_not_in_projection_registry` | 6566 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis_assignees.company_id` | `` | `schema_column_not_in_projection_registry` | 3371 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_inspection_items.company_id` | `` | `schema_column_not_in_projection_registry` | 3363 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_inspection_items.item_response` | `` | `schema_column_not_in_projection_registry` | 3363 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_inspection_items.response` | `` | `schema_column_not_in_projection_registry` | 3363 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_inspection_items.response_set` | `` | `schema_column_not_in_projection_registry` | 3363 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_daily_log_dcrs.company_id` | `` | `schema_column_not_in_projection_registry` | 2623 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_budget_detail_rows.actual_cost` | `` | `schema_column_not_in_projection_registry` | 2496 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_budget_detail_rows.company_id` | `` | `schema_column_not_in_projection_registry` | 2496 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_budget_detail_rows.cost_type` | `` | `schema_column_not_in_projection_registry` | 2496 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_budget_detail_rows.cost_type_id` | `` | `schema_column_not_in_projection_registry` | 2496 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_budget_detail_rows.line_item_type_id` | `` | `schema_column_not_in_projection_registry` | 2496 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis.ball_in_court` | `` | `schema_column_not_in_projection_registry` | 1960 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis.company_id` | `` | `schema_column_not_in_projection_registry` | 1960 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis.cost_code` | `` | `schema_column_not_in_projection_registry` | 1960 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis.location` | `` | `schema_column_not_in_projection_registry` | 1960 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis.sub_job` | `` | `schema_column_not_in_projection_registry` | 1960 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_rfis_questions.company_id` | `` | `schema_column_not_in_projection_registry` | 1960 | Review migration/read-model origin and add or document projection mapping only after approval. |
| `procore_ep_submittals.company_id` | `` | `schema_column_not_in_projection_registry` | 1760 | Review migration/read-model origin and add or document projection mapping only after approval. |

## Intentionally Deferred Fields

| Field | Classification | Next Action | Rationale |
| --- | --- | --- | --- |
| `procore_ep_budget_detail_rows.actual_cost` | `read_model_convenience_or_dead_column` | `no_action_dead_column_candidate` | Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection. |
| `procore_ep_budget_detail_rows.cost_type` | `read_model_convenience_or_dead_column` | `no_action_dead_column_candidate` | Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection. |
| `procore_ep_budget_detail_rows.cost_type_id` | `read_model_convenience_or_dead_column` | `no_action_dead_column_candidate` | Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection. |
| `procore_ep_budget_detail_rows.line_item_type_id` | `read_model_convenience_or_dead_column` | `no_action_dead_column_candidate` | Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection. |
| `procore_ep_budget_detail_row_cells.currency_iso_code` | `expected_optional` | `no_action_expected_optional` | Candidate row-level source paths are present only as null or empty values. |

## Budget Detail Confirmation

- Budget Detail refresh/reconciliation remains unchanged.
- Budget Detail row convenience fields remain deferred based on Batch 2 triage evidence.
- `procore_ep_budget_detail_row_cells.currency_iso_code` remains expected optional based on current evidence.

## Guardrails

- Schema changes applied by this audit delta: `no`
- Registry changes applied by this audit delta: `no`
- Projection code changes applied by this audit delta: `no`
- Live calls made: `no`
- Scheduler called: `no`
- SourceRefreshOrchestrator called: `no`
- Budget Detail refresh/reconciliation called: `no`
- Writeback performed: `no`
- Raw payload values emitted: `no`
