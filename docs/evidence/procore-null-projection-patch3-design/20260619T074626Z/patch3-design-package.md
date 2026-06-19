# Patch 3 Procore Null Projection Schema Policy Design Package

Generated at: `2026-06-19T07:50:18Z`

## 1. Executive recommendation

Patch 3 should be implemented later as schema policy cleanup, not projection remediation. The reviewed evidence supports separating object/container schema decisions from scalar mapping defects: whole dict/list payloads must not be projected into bare scalar columns, and standard `company_id` derivation needs a repository-wide provenance policy before any backfill or mapping.

This design package recommends future table-specific decomposition, child-table/entity representation, or additional evidence decisions for the 43 object/container fields. It also recommends deferring the 4 standard `company_id` fields until explicit derivation sources and provenance fields are approved.

No migrations, mappings, registry edits, projection changes, Budget Detail behavior changes, `company_id` derivation, refreshes, live calls, writeback, or replay were performed.

## 2. Inputs reviewed

- `docs/evidence/procore-null-projection-patch2/20260619T071034Z/post-patch2-null-projection-audit.json`
- `docs/evidence/procore-null-projection-patch2/20260619T071034Z/post-patch2-raw-payload-mapping-audit.json`
- `docs/evidence/procore-null-projection-final-schema-decision-matrix/20260619T000000Z/remaining-unresolved-schema-decision-matrix.md`

- Raw strict suspected projection defect count preserved: `123`
- High-confidence scalar mapping candidates: `0`
- Date/datetime mapping candidates: `0`
- Patch 1 scalar decomposition defects: `0`

## 3. Object/container field inventory

| Table | Column | Endpoint | Rows | Null rate | Recommendation | Existing scalar columns | Child/entity indicators |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `procore_ep_change_events` | `event_origin` | `change-events` | 1054 | 0.995256 | `reuse_existing_scalar_decomposition_columns` | `event_origin_display_name`, `event_origin_origin_id` | none found |
| `procore_ep_commitment_change_orders` | `change_order_change_reason` | `commitment-change-orders` | 100 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `change_order_change_reason_id` | none found |
| `procore_ep_commitment_change_orders` | `designated_reviewer` | `commitment-change-orders` | 100 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `designated_reviewer_id`, `designated_reviewer_name` | none found |
| `procore_ep_commitment_change_orders` | `received_from` | `commitment-change-orders` | 100 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `received_from_id`, `received_from_name` | none found |
| `procore_ep_commitment_change_orders` | `reviewed_by` | `commitment-change-orders` | 100 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `reviewed_by_id`, `reviewed_by_name` | none found |
| `procore_ep_daily_log_inspections` | `location` | `daily-log-inspections` | 114 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_daily_log_manpower` | `contact` | `daily-log-manpower` | 921 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `contact_email`, `contact_fax_number`, `contact_id`, `contact_login_information_id`, `contact_name`, `contact_vendor_name` | none found |
| `procore_ep_daily_log_manpower` | `cost_code` | `daily-log-manpower` | 921 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `cost_code_id`, `cost_code_long_name`, `cost_code_name` | none found |
| `procore_ep_daily_log_manpower` | `location` | `daily-log-manpower` | 921 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_daily_log_notes` | `location` | `daily-log-notes` | 92 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_inspection_items` | `item_response` | `inspection-items` | 3363 | 1.0 | `represent_only_in_child_table` | `item_response_item_id`, `item_response_item_type_id`, `item_response_item_type_name`, `item_response_payload_response_option_id`, `item_response_payload_response_option_name`, `item_response_responded_at`, `item_response_responder_id`, `item_response_responder_login`, `item_response_responder_name` | none found |
| `procore_ep_inspection_items` | `response` | `inspection-items` | 3363 | 1.0 | `represent_only_in_child_table` | `response_id`, `response_name`, `response_set_created_at`, `response_set_id`, `response_set_name`, `response_set_updated_at` | `procore_ep_inspection_items_response_set_responses` |
| `procore_ep_inspection_items` | `response_set` | `inspection-items` | 3363 | 1.0 | `represent_only_in_child_table` | `response_set_created_at`, `response_set_id`, `response_set_name`, `response_set_updated_at` | `procore_ep_inspection_items_response_set_responses` |
| `procore_ep_inspections` | `closed_by` | `inspections` | 74 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `closed_by_company_name`, `closed_by_id`, `closed_by_login`, `closed_by_name` | none found |
| `procore_ep_inspections` | `location` | `inspections` | 74 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `location_code`, `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_inspections` | `point_of_contact` | `inspections` | 74 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `point_of_contact_company_name`, `point_of_contact_id`, `point_of_contact_login`, `point_of_contact_name` | none found |
| `procore_ep_inspections` | `responsible_contractor` | `inspections` | 74 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `responsible_contractor_id`, `responsible_contractor_name` | none found |
| `procore_ep_inspections` | `specification_section` | `inspections` | 74 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `specification_section_id` | none found |
| `procore_ep_inspections` | `trade` | `inspections` | 74 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `trade_id`, `trade_name`, `trade_updated_at` | none found |
| `procore_ep_inspections_signature_requests` | `signature` | `inspections` | 8 | 1.0 | `represent_only_in_entity_dimension` | `signature_attachment_id`, `signature_attachment_name`, `signature_captured_at`, `signature_captured_by_id`, `signature_captured_by_login`, `signature_captured_by_name`, `signature_id` | none found |
| `procore_ep_meetings` | `distributed_by` | `meetings` | 97 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `distributed_by_id`, `distributed_by_login`, `distributed_by_name` | none found |
| `procore_ep_observations` | `assignee` | `observations` | 215 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `assignee_id`, `assignee_name`, `assignee_vendor_id`, `assignee_vendor_name` | `procore_ep_observations_assignees` |
| `procore_ep_observations` | `assignee_vendor` | `observations` | 215 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `assignee_vendor_id`, `assignee_vendor_name` | none found |
| `procore_ep_observations` | `location` | `observations` | 215 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_observations` | `origin` | `observations` | 215 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `origin_payload_checklist_item_id`, `origin_payload_checklist_list_id` | none found |
| `procore_ep_observations` | `specification_section` | `observations` | 215 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `specification_section_current_revision_id`, `specification_section_id`, `specification_section_number`, `specification_section_viewable_document_id` | none found |
| `procore_ep_observations` | `trade` | `observations` | 215 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `trade_id`, `trade_name`, `trade_updated_at` | none found |
| `procore_ep_observations_assignees` | `vendor` | `observations` | 7 | 1.0 | `represent_only_in_entity_dimension` | `vendor_id`, `vendor_name` | none found |
| `procore_ep_prime_change_orders` | `change_order_change_reason` | `prime-change-orders` | 63 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `change_order_change_reason_id` | none found |
| `procore_ep_prime_change_orders` | `designated_reviewer` | `prime-change-orders` | 63 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `designated_reviewer_id`, `designated_reviewer_name` | none found |
| `procore_ep_prime_change_orders` | `received_from` | `prime-change-orders` | 63 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `received_from_id`, `received_from_name` | none found |
| `procore_ep_projects` | `project_stage` | `projects` | 14 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `project_stage_id`, `project_stage_name` | none found |
| `procore_ep_purchase_order_contracts` | `assignee` | `purchase-order-contracts` | 10 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `assignee_id` | none found |
| `procore_ep_purchase_order_contracts` | `custom_fields_custom_field_214072_value` | `purchase-order-contracts` | 10 | 1.0 | `needs_additional_source_sample` | `custom_fields_custom_field_214072_value_id` | none found |
| `procore_ep_purchase_order_contracts` | `custom_fields_custom_field_214078_value` | `purchase-order-contracts` | 10 | 1.0 | `needs_additional_source_sample` | `custom_fields_custom_field_214078_value_company_name`, `custom_fields_custom_field_214078_value_id` | none found |
| `procore_ep_purchase_order_contracts` | `custom_fields_custom_field_214087_value` | `purchase-order-contracts` | 10 | 1.0 | `needs_additional_source_sample` | `custom_fields_custom_field_214087_value_id` | none found |
| `procore_ep_rfis` | `ball_in_court` | `rfis` | 1967 | 0.972547 | `reuse_existing_scalar_decomposition_columns` | `ball_in_court_id`, `ball_in_court_login`, `ball_in_court_name` | `procore_ep_rfis_ball_in_courts` |
| `procore_ep_rfis` | `cost_code` | `rfis` | 1967 | 0.984748 | `reuse_existing_scalar_decomposition_columns` | `cost_code_id`, `cost_code_name` | none found |
| `procore_ep_rfis` | `location` | `rfis` | 1967 | 0.961362 | `reuse_existing_scalar_decomposition_columns` | `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_rfis` | `sub_job` | `rfis` | 1967 | 0.967972 | `reuse_existing_scalar_decomposition_columns` | `sub_job_code`, `sub_job_id`, `sub_job_name` | none found |
| `procore_ep_submittals` | `location` | `submittals` | 1760 | 0.981818 | `reuse_existing_scalar_decomposition_columns` | `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at` | none found |
| `procore_ep_submittals` | `submittal_package` | `submittals` | 1760 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `submittal_package_created_by_id`, `submittal_package_created_by_login`, `submittal_package_created_by_name`, `submittal_package_id`, `submittal_package_number`, `submittal_package_specification_section_id`, `submittal_package_updated_at` | none found |
| `procore_ep_submittals` | `submittal_workflow_template` | `submittals` | 1760 | 1.0 | `reuse_existing_scalar_decomposition_columns` | `submittal_workflow_template_applied_at`, `submittal_workflow_template_id`, `submittal_workflow_template_name` | none found |

## 4. Recommended object/container decisions by table

### `procore_ep_change_events`
- `event_origin`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_commitment_change_orders`
- `change_order_change_reason`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `designated_reviewer`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `received_from`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `reviewed_by`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_daily_log_inspections`
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_daily_log_manpower`
- `contact`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `cost_code`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_daily_log_notes`
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_inspection_items`
- `item_response`: `represent_only_in_child_table`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `response`: `represent_only_in_child_table`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `response_set`: `represent_only_in_child_table`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_inspections`
- `closed_by`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `point_of_contact`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `responsible_contractor`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `specification_section`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `trade`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_inspections_signature_requests`
- `signature`: `represent_only_in_entity_dimension`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_meetings`
- `distributed_by`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_observations`
- `assignee`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `assignee_vendor`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `origin`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `specification_section`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `trade`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_observations_assignees`
- `vendor`: `represent_only_in_entity_dimension`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_prime_change_orders`
- `change_order_change_reason`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `designated_reviewer`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `received_from`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_projects`
- `project_stage`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_purchase_order_contracts`
- `assignee`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `custom_fields_custom_field_214072_value`: `needs_additional_source_sample`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `custom_fields_custom_field_214078_value`: `needs_additional_source_sample`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `custom_fields_custom_field_214087_value`: `needs_additional_source_sample`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_rfis`
- `ball_in_court`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `cost_code`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `sub_job`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.

### `procore_ep_submittals`
- `location`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `submittal_package`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.
- `submittal_workflow_template`: `reuse_existing_scalar_decomposition_columns`. Evidence class: `object_container_requires_decomposition_or_deprecation`; raw root cause: `schema_column_not_in_projection_registry`.


## 5. Decomposition candidates

### `add_scalar_decomposition_columns`
- None.

### `reuse_existing_scalar_decomposition_columns`
- `procore_ep_change_events.event_origin`: `event_origin_display_name`, `event_origin_origin_id`
- `procore_ep_commitment_change_orders.change_order_change_reason`: `change_order_change_reason_id`
- `procore_ep_commitment_change_orders.designated_reviewer`: `designated_reviewer_id`, `designated_reviewer_name`
- `procore_ep_commitment_change_orders.received_from`: `received_from_id`, `received_from_name`
- `procore_ep_commitment_change_orders.reviewed_by`: `reviewed_by_id`, `reviewed_by_name`
- `procore_ep_daily_log_inspections.location`: `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_daily_log_manpower.contact`: `contact_email`, `contact_fax_number`, `contact_id`, `contact_login_information_id`, `contact_name`, `contact_vendor_name`
- `procore_ep_daily_log_manpower.cost_code`: `cost_code_id`, `cost_code_long_name`, `cost_code_name`
- `procore_ep_daily_log_manpower.location`: `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_daily_log_notes.location`: `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_inspections.closed_by`: `closed_by_company_name`, `closed_by_id`, `closed_by_login`, `closed_by_name`
- `procore_ep_inspections.location`: `location_code`, `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_inspections.point_of_contact`: `point_of_contact_company_name`, `point_of_contact_id`, `point_of_contact_login`, `point_of_contact_name`
- `procore_ep_inspections.responsible_contractor`: `responsible_contractor_id`, `responsible_contractor_name`
- `procore_ep_inspections.specification_section`: `specification_section_id`
- `procore_ep_inspections.trade`: `trade_id`, `trade_name`, `trade_updated_at`
- `procore_ep_meetings.distributed_by`: `distributed_by_id`, `distributed_by_login`, `distributed_by_name`
- `procore_ep_observations.assignee`: `assignee_id`, `assignee_name`, `assignee_vendor_id`, `assignee_vendor_name`
- `procore_ep_observations.assignee_vendor`: `assignee_vendor_id`, `assignee_vendor_name`
- `procore_ep_observations.location`: `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_observations.origin`: `origin_payload_checklist_item_id`, `origin_payload_checklist_list_id`
- `procore_ep_observations.specification_section`: `specification_section_current_revision_id`, `specification_section_id`, `specification_section_number`, `specification_section_viewable_document_id`
- `procore_ep_observations.trade`: `trade_id`, `trade_name`, `trade_updated_at`
- `procore_ep_prime_change_orders.change_order_change_reason`: `change_order_change_reason_id`
- `procore_ep_prime_change_orders.designated_reviewer`: `designated_reviewer_id`, `designated_reviewer_name`
- `procore_ep_prime_change_orders.received_from`: `received_from_id`, `received_from_name`
- `procore_ep_projects.project_stage`: `project_stage_id`, `project_stage_name`
- `procore_ep_purchase_order_contracts.assignee`: `assignee_id`
- `procore_ep_rfis.ball_in_court`: `ball_in_court_id`, `ball_in_court_login`, `ball_in_court_name`
- `procore_ep_rfis.cost_code`: `cost_code_id`, `cost_code_name`
- `procore_ep_rfis.location`: `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_rfis.sub_job`: `sub_job_code`, `sub_job_id`, `sub_job_name`
- `procore_ep_submittals.location`: `location_created_at`, `location_id`, `location_name`, `location_node_name`, `location_parent_id`, `location_updated_at`
- `procore_ep_submittals.submittal_package`: `submittal_package_created_by_id`, `submittal_package_created_by_login`, `submittal_package_created_by_name`, `submittal_package_id`, `submittal_package_number`, `submittal_package_specification_section_id`, `submittal_package_updated_at`
- `procore_ep_submittals.submittal_workflow_template`: `submittal_workflow_template_applied_at`, `submittal_workflow_template_id`, `submittal_workflow_template_name`

## 6. Deprecation candidates

- None assigned in this design package. Ambiguous custom-field containers are marked for additional source evidence before deprecation.

## 7. Child-table/entity-only candidates

### `represent_only_in_child_table`
- `procore_ep_inspection_items.item_response`
- `procore_ep_inspection_items.response`
- `procore_ep_inspection_items.response_set`

### `represent_only_in_entity_dimension`
- `procore_ep_inspections_signature_requests.signature`
- `procore_ep_observations_assignees.vendor`

## 8. Fields needing additional evidence

- `procore_ep_purchase_order_contracts.custom_fields_custom_field_214072_value`: keep unresolved until reviewed against a body-free custom-field source inventory.
- `procore_ep_purchase_order_contracts.custom_fields_custom_field_214078_value`: keep unresolved until reviewed against a body-free custom-field source inventory.
- `procore_ep_purchase_order_contracts.custom_fields_custom_field_214087_value`: keep unresolved until reviewed against a body-free custom-field source inventory.

## 9. `company_id` policy recommendation

Standard `company_id` may only be derived from explicit request context, the configured project registry, or documented company-scoped endpoint context. Nested company, vendor, or business-party IDs must remain in generated nested columns or entity/reference dimensions and must not be promoted into standard `company_id` by field-name similarity alone.

Any future derived standard `company_id` implementation must include provenance fields such as `company_id_source`, `company_id_source_kind`, and `company_id_source_ref`, unless repo truth identifies equivalent existing provenance columns. It must also include rollback/backfill rules and copied-DB proof before production apply.

## 10. Tables eligible / not eligible for `company_id` derivation

Potentially eligible after approval: primary project-scoped endpoint tables where the request context or project registry deterministically supplies company ID and where provenance columns are available or added.

Not eligible in the current branch: child/reference/vendor/business-party tables and the four deferred fields below, because current evidence does not prove a repository-wide convention or approved provenance path.

- `procore_ep_projects.company_id` (`projects`): `company_id_policy_deferred`
- `procore_ep_purchase_order_line_items.company_id` (`purchase-order-line-items`): `company_id_policy_deferred`
- `procore_ep_rfqs.company_id` (`rfqs`): `company_id_policy_deferred`
- `procore_ep_rfqs_change_event_change_event_line_items.company_id` (`rfqs`): `company_id_policy_deferred`

## 11. Proposed future migration strategy

1. Approve a table-by-table schema RFC for object/container fields, separating scalar decomposition, child-table/entity representation, and deprecation.
2. Add nullable scalar/provenance columns only after copied-DB source proof identifies stable source keys and target semantics.
3. Backfill only through endpoint-limited copied-DB projection replay before any production apply.
4. Deprecate bare container columns through an explicit migration/deprecation plan with rollback notes; do not silently delete columns.

## 12. Proposed future tests

- Registry/schema audit test proving no whole dict/list mapping into bare scalar columns.
- Projection tests for each approved scalar decomposition path, including object IDs, names, logins, and dates where applicable.
- Company ID derivation tests proving approved source kind, source ref, and rollback-safe null behavior when context is absent.
- No-raw evidence tests proving inventories contain counts/path names only.

## 13. Proposed future copied-DB proof commands

```bash
sqlite3 "$PROD_DB" ".backup '/tmp/procore-schema-policy-proof/hb-personal-assistant.sqlite'"
sqlite3 /tmp/procore-schema-policy-proof/hb-personal-assistant.sqlite "PRAGMA integrity_check; PRAGMA quick_check;"
hb-assistant procore analytics projection-schema-audit --db /tmp/procore-schema-policy-proof/hb-personal-assistant.sqlite --json
hb-assistant procore analytics projection-reprocess --db /tmp/procore-schema-policy-proof/hb-personal-assistant.sqlite --endpoint <approved-endpoint> --apply --json
```

## 14. No-raw / no-live guardrails

- This package was generated from existing body-free evidence files only.
- No raw payload bodies, example payload values, business text, personal identifiers, notes, comments, descriptions, signed URLs, or credentials are included.
- No live Procore calls, scheduler calls, `SourceRefreshOrchestrator` runs, all-project refreshes, all-endpoint refreshes, writeback, migrations, projection replay, or Budget Detail refresh/reconciliation were used.

## 15. Stop conditions

- Stop if a proposed object/container mapping would store a whole dict/list into a bare scalar column.
- Stop if `company_id` derivation lacks explicit source context and provenance.
- Stop if copied-DB proof fails to populate any approved scalar decomposition field.
- Stop if no-raw scan detects payload values or sensitive content in evidence.

## 16. Recommended Patch 3 implementation sequence

1. Implement approved scalar decomposition for high-value operational tables with existing or newly approved scalar destination columns.
2. Move child/entity-only containers into existing child tables or explicit dimensions; avoid duplicating whole objects in parent tables.
3. Review custom-field containers with a body-free custom-field metadata inventory before deprecation or decomposition.
4. Separately approve and implement repository-wide `company_id` derivation with provenance and rollback/backfill proof.

## 17. Open questions, if any

- Which object/reference dimensions should become first-class shared dimensions versus endpoint-local scalar columns?
- Should custom-field container columns be deprecated, decomposed based on custom-field definitions, or represented in a generic custom-field value table?
- Which existing provenance columns, if any, are equivalent to `company_id_source`, `company_id_source_kind`, and `company_id_source_ref`?

## Closeout

Patch 3 is design/evidence only. No implementation changes were made.
