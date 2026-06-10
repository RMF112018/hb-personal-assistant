# 07 — Null/Empty-Rate Matrix

Per-endpoint field null/empty rates (field NAMES + percentages only; no values).

## billing-periods (10 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 20 | 20 | 0.0 | other |
| `$.created_at` | string | 20 | 20 | 0.0 | date |
| `$.due_date` | string | 20 | 20 | 0.0 | date |
| `$.end_date` | string | 20 | 20 | 0.0 | date |
| `$.id` | integer | 20 | 20 | 0.0 | identity |
| `$.position` | integer | 20 | 20 | 0.0 | other |
| `$.project_id` | integer | 20 | 20 | 0.0 | identity |
| `$.start_date` | string | 20 | 20 | 0.0 | date |
| `$.status` | string | 20 | 20 | 0.0 | status |
| `$.updated_at` | string | 20 | 20 | 0.0 | date |

## budget-change-history (9 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 100 | 100 | 0.0 | other |
| `$.budget_code` | string | 100 | 100 | 0.0 | identity |
| `$.column` | string | 100 | 100 | 0.0 | other |
| `$.created_at` | string | 100 | 100 | 0.0 | date |
| `$.created_by` | string | 100 | 100 | 0.0 | person |
| `$.description` | string | 100 | 100 | 0.0 | title |
| `$.new_value` | string | 100 | 100 | 0.0 | money |
| `$.old_value` | string | 100 | 100 | 0.0 | money |
| `$.type` | string | 100 | 100 | 0.0 | other |

## budget-modifications (10 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 148 | 148 | 0.0 | other |
| `$.created_at` | string | 148 | 148 | 0.0 | date |
| `$.from_budget_line_item_id` | integer | 148 | 148 | 0.0 | identity |
| `$.id` | integer | 148 | 148 | 0.0 | identity |
| `$.notes` | string | 148 | 143 | 3.4 | title |
| `$.origin_data` | null | 148 | 0 | 100.0 | other |
| `$.origin_id` | null | 148 | 0 | 100.0 | identity |
| `$.to_budget_line_item_id` | integer | 148 | 148 | 0.0 | identity |
| `$.transfer_amount` | string | 148 | 148 | 0.0 | money |
| `$.updated_at` | string | 148 | 148 | 0.0 | date |

## budget-views (14 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 6 | 6 | 0.0 | other |
| `$.created_at` | string | 6 | 6 | 0.0 | date |
| `$.created_by` | object | 6 | 6 | 0.0 | person |
| `$.description` | string | 6 | 6 | 0.0 | title |
| `$.id` | integer | 6 | 6 | 0.0 | identity |
| `$.links` | object | 6 | 6 | 0.0 | other |
| `$.name` | string | 6 | 6 | 0.0 | title |
| `$.role` | string | 6 | 6 | 0.0 | other |
| `$.updated_at` | string | 6 | 6 | 0.0 | date |

## change-events (250 paths, 11 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 201 | 201 | 0.0 | other |
| `$.attachments` | array | 201 | 165 | 17.9 | attachment |
| `$.attachments[]` | object | 237 | 237 | 0.0 | attachment |
| `$.change_items` | array | 201 | 200 | 0.5 | other |
| `$.change_items[]` | object | 316 | 316 | 0.0 | other |
| `$.change_items[].budget_code.segment_items` | array | 316 | 316 | 0.0 | cost_code |
| `$.change_items[].budget_code.segment_items[].path_codes` | array | 948 | 948 | 0.0 | cost_code |
| `$.change_items[].budget_code.segment_items[].path_ids` | array | 948 | 948 | 0.0 | cost_code |
| `$.change_items[].disabled_fields` | array | 316 | 249 | 21.2 | other |
| `$.change_reason` | object | 201 | 201 | 0.0 | title |
| `$.change_type` | object | 201 | 201 | 0.0 | other |
| `$.comments_enabled` | boolean | 201 | 201 | 0.0 | title |
| `$.company_id` | integer | 201 | 201 | 0.0 | identity |
| `$.created_at` | string | 201 | 201 | 0.0 | date |
| `$.created_by` | object | 201 | 201 | 0.0 | person |
| `$.currency_configuration` | object | 201 | 201 | 0.0 | money |
| `$.custom_fields` | object | 201 | 0 | 100.0 | custom_field |
| `$.deletable` | boolean | 201 | 201 | 0.0 | other |
| `$.deleted_at` | null | 201 | 0 | 100.0 | date |
| `$.description` | null/string | 201 | 184 | 8.5 | title |
| `$.event_origin` | null/object | 201 | 5 | 97.5 | other |
| `$.external_data` | null | 201 | 0 | 100.0 | custom_field |
| `$.has_edited_markups` | boolean | 201 | 201 | 0.0 | money |
| `$.id` | integer | 201 | 201 | 0.0 | identity |
| `$.in_recycle_bin` | boolean | 201 | 201 | 0.0 | other |
| `$.markup_items` | array | 201 | 196 | 2.5 | money |
| `$.markup_items[]` | object | 579 | 579 | 0.0 | money |
| `$.markup_items[].wbs_code.segment_items` | array | 579 | 579 | 0.0 | cost_code |
| `$.markup_items[].wbs_code.segment_items[].path_codes` | array | 1737 | 1737 | 0.0 | cost_code |
| `$.markup_items[].wbs_code.segment_items[].path_ids` | array | 1737 | 1737 | 0.0 | cost_code |
| `$.notes` | object | 201 | 0 | 100.0 | title |
| `$.number` | string | 201 | 201 | 0.0 | identity |
| `$.prime_contract_for_estimates` | object | 201 | 201 | 0.0 | other |
| `$.production_quantities` | array | 201 | 0 | 100.0 | other |
| `$.project_id` | integer | 201 | 201 | 0.0 | identity |
| `$.scope` | string | 201 | 201 | 0.0 | title |
| `$.source` | null | 201 | 0 | 100.0 | other |
| `$.source_of_revenue_rom` | string | 201 | 201 | 0.0 | other |
| `$.status` | object | 201 | 201 | 0.0 | status |
| `$.title` | string | 201 | 201 | 0.0 | title |
| `$.updated_at` | string | 201 | 201 | 0.0 | date |

## commitment-attachments (6 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 16 | 16 | 0.0 | other |
| `$.content_type` | string | 16 | 16 | 0.0 | other |
| `$.id` | string | 16 | 16 | 0.0 | identity |
| `$.name` | string | 16 | 16 | 0.0 | title |
| `$.url` | string | 16 | 16 | 0.0 | attachment |
| `$.uuid` | string | 16 | 16 | 0.0 | identity |

## commitment-change-orders (49 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 100 | 100 | 0.0 | other |
| `$.batch_id` | null | 100 | 0 | 100.0 | identity |
| `$.billing_schedule_of_values_status` | string | 100 | 100 | 0.0 | money |
| `$.change_order_change_reason` | null/object | 100 | 98 | 2.0 | title |
| `$.contract_id` | integer | 100 | 100 | 0.0 | identity |
| `$.created_at` | string | 100 | 100 | 0.0 | date |
| `$.created_by` | object | 100 | 100 | 0.0 | person |
| `$.currency_configuration` | object | 100 | 100 | 0.0 | money |
| `$.custom_fields` | object | 100 | 0 | 100.0 | custom_field |
| `$.description` | string | 100 | 100 | 0.0 | title |
| `$.designated_reviewer` | null/object | 100 | 68 | 32.0 | status |
| `$.due_date` | null/string | 100 | 31 | 69.0 | date |
| `$.enable_ssov` | boolean | 100 | 100 | 0.0 | other |
| `$.executed` | boolean | 100 | 100 | 0.0 | status |
| `$.field_change` | boolean | 100 | 100 | 0.0 | other |
| `$.grand_total` | string | 100 | 100 | 0.0 | money |
| `$.id` | integer | 100 | 100 | 0.0 | identity |
| `$.invoiced_date` | null | 100 | 0 | 100.0 | date |
| `$.legacy_package_id` | integer | 100 | 100 | 0.0 | identity |
| `$.legacy_request_id` | integer | 100 | 100 | 0.0 | identity |
| `$.location_id` | integer/null | 100 | 7 | 93.0 | identity |
| `$.number` | string | 100 | 100 | 0.0 | identity |
| `$.paid` | boolean | 100 | 100 | 0.0 | money |
| `$.paid_date` | null | 100 | 0 | 100.0 | date |
| `$.private` | boolean | 100 | 100 | 0.0 | status |
| `$.received_from` | null/object | 100 | 21 | 79.0 | other |
| `$.reference` | null/string | 100 | 24 | 76.0 | other |
| `$.review_notes` | string | 1 | 1 | 0.0 | status |
| `$.reviewed_at` | null/string | 100 | 94 | 6.0 | date |
| `$.reviewed_by` | null/object | 100 | 1 | 99.0 | status |
| `$.revision` | integer | 100 | 100 | 0.0 | other |
| `$.schedule_impact_amount` | integer/null | 100 | 27 | 73.0 | money |
| `$.signature_required` | boolean | 100 | 100 | 0.0 | other |
| `$.signed_change_order_received_date` | null/string | 100 | 4 | 96.0 | date |
| `$.status` | string | 100 | 100 | 0.0 | status |
| `$.title` | string | 100 | 100 | 0.0 | title |
| `$.type` | string | 100 | 100 | 0.0 | other |
| `$.updated_at` | string | 100 | 100 | 0.0 | date |

## commitment-compliance (28 paths, 5 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 7 | 7 | 0.0 | other |
| `$.compliance_documents` | array | 7 | 0 | 100.0 | attachment |
| `$.compliance_notes` | null | 7 | 0 | 100.0 | title |
| `$.compliance_requirements_not_created` | array | 7 | 0 | 100.0 | other |
| `$.compliance_status` | null | 7 | 0 | 100.0 | status |
| `$.derived_compliance_status` | null | 7 | 0 | 100.0 | status |
| `$.derived_insurance_status` | string | 7 | 7 | 0.0 | status |
| `$.insurance_documents` | array | 7 | 7 | 0.0 | attachment |
| `$.insurance_documents[]` | object | 58 | 58 | 0.0 | attachment |
| `$.insurance_documents[].attachments` | array | 58 | 58 | 0.0 | attachment |
| `$.insurance_notes` | null | 7 | 0 | 100.0 | title |
| `$.insurance_requirements_not_created` | array | 7 | 0 | 100.0 | other |
| `$.insurance_status` | null | 7 | 0 | 100.0 | status |
| `$.updated_at` | null | 7 | 0 | 100.0 | date |
| `$.updated_by_id` | null | 7 | 0 | 100.0 | identity |

## commitment-contracts (54 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 142 | 142 | 0.0 | other |
| `$.accounting_method` | string | 142 | 142 | 0.0 | other |
| `$.actual_completion_date` | null | 131 | 0 | 100.0 | date |
| `$.allow_change_orders_ssov` | boolean | 142 | 142 | 0.0 | other |
| `$.allow_comments` | boolean | 142 | 142 | 0.0 | title |
| `$.allow_markups` | boolean | 142 | 142 | 0.0 | money |
| `$.allow_payment_applications` | boolean | 142 | 142 | 0.0 | money |
| `$.allow_payments` | boolean | 142 | 142 | 0.0 | money |
| `$.approval_letter_date` | null | 142 | 0 | 100.0 | date |
| `$.assignee` | object | 5 | 5 | 0.0 | person |
| `$.bill_to_address` | string | 11 | 11 | 0.0 | other |
| `$.billing_schedule_of_values_status` | string | 131 | 131 | 0.0 | money |
| `$.change_order_level_of_detail` | string | 142 | 142 | 0.0 | other |
| `$.contract_date` | null | 142 | 0 | 100.0 | date |
| `$.contract_estimated_completion_date` | null/string | 131 | 4 | 96.9 | date |
| `$.contract_start_date` | null/string | 131 | 53 | 59.5 | date |
| `$.created_at` | string | 142 | 142 | 0.0 | date |
| `$.created_by` | object | 142 | 142 | 0.0 | person |
| `$.currency_configuration` | object | 142 | 142 | 0.0 | money |
| `$.delivery_date` | null/string | 11 | 5 | 54.5 | date |
| `$.description` | null/string | 142 | 130 | 8.5 | title |
| `$.display_materials_retainage` | boolean | 142 | 142 | 0.0 | money |
| `$.display_work_retainage` | boolean | 142 | 142 | 0.0 | money |
| `$.enable_ssov` | boolean | 142 | 142 | 0.0 | other |
| `$.exclusions` | null/string | 131 | 95 | 27.5 | other |
| `$.executed` | boolean | 142 | 142 | 0.0 | status |
| `$.execution_date` | null | 142 | 0 | 100.0 | date |
| `$.grand_total` | string | 142 | 142 | 0.0 | money |
| `$.id` | string | 142 | 142 | 0.0 | identity |
| `$.inclusions` | null/string | 131 | 97 | 26.0 | other |
| `$.issued_on_date` | null | 142 | 0 | 100.0 | date |
| `$.letter_of_intent_date` | null | 142 | 0 | 100.0 | date |
| `$.number` | string | 142 | 142 | 0.0 | identity |
| `$.payment_terms` | null/string | 11 | 1 | 90.9 | money |
| `$.private` | boolean | 142 | 142 | 0.0 | status |
| `$.retainage_percent` | string | 142 | 142 | 0.0 | money |
| `$.returned_date` | null | 142 | 0 | 100.0 | date |
| `$.ship_to_address` | string | 11 | 11 | 0.0 | other |
| `$.ship_via` | null | 11 | 0 | 100.0 | other |
| `$.show_cost_code_on_pdf` | boolean | 142 | 142 | 0.0 | cost_code |
| `$.show_line_items_to_non_admins` | boolean | 142 | 142 | 0.0 | other |
| `$.signature_required` | boolean | 142 | 142 | 0.0 | other |
| `$.signed_contract_received_date` | null/string | 142 | 18 | 87.3 | date |
| `$.ssr_enabled` | boolean | 142 | 142 | 0.0 | other |
| `$.status` | string | 142 | 142 | 0.0 | status |
| `$.title` | string | 142 | 141 | 0.7 | title |
| `$.type` | string | 142 | 142 | 0.0 | other |
| `$.updated_at` | string | 142 | 142 | 0.0 | date |
| `$.vendor` | object | 114 | 114 | 0.0 | company |

## commitment-line-items (17 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 63 | 63 | 0.0 | other |
| `$.amount` | string | 63 | 63 | 0.0 | money |
| `$.description` | string | 63 | 63 | 0.0 | title |
| `$.extended_type` | string | 12 | 12 | 0.0 | other |
| `$.funding_rule_id` | null | 63 | 0 | 100.0 | identity |
| `$.id` | string | 63 | 63 | 0.0 | identity |
| `$.position` | integer | 63 | 63 | 0.0 | other |
| `$.prime_line_item_id` | null | 63 | 0 | 100.0 | identity |
| `$.quantity` | string | 12 | 12 | 0.0 | quantity |
| `$.tax_code_id` | null | 63 | 0 | 100.0 | identity |
| `$.unit_cost` | string | 12 | 12 | 0.0 | money |
| `$.uom` | string | 3 | 3 | 0.0 | quantity |
| `$.wbs_code` | object | 63 | 63 | 0.0 | identity |
| `$.wbs_code_id` | string | 63 | 63 | 0.0 | identity |

## daily-log-dcrs (53 paths, 2 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 2541 | 2541 | 0.0 | other |
| `$.apprentice_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.attachments` | array | 2541 | 207 | 91.9 | attachment |
| `$.attachments[]` | object | 546 | 546 | 0.0 | attachment |
| `$.created_at` | string | 2541 | 2541 | 0.0 | date |
| `$.created_by` | object | 2541 | 2541 | 0.0 | person |
| `$.created_by_collaborator` | boolean | 2541 | 2541 | 0.0 | person |
| `$.custom_fields` | object | 2541 | 0 | 100.0 | custom_field |
| `$.date` | string | 2541 | 2541 | 0.0 | date |
| `$.datetime` | string | 2541 | 2541 | 0.0 | other |
| `$.deleted_at` | null | 2541 | 0 | 100.0 | date |
| `$.first_year_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.foreman_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.id` | integer | 2541 | 2541 | 0.0 | identity |
| `$.journeyman_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.local_city_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.local_county_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.location` | null | 2541 | 0 | 100.0 | other |
| `$.minority_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.notes` | null/string | 2541 | 2323 | 8.6 | title |
| `$.number_of_apprentice_workers` | integer | 2541 | 2541 | 0.0 | quantity |
| `$.number_of_foreman_workers` | integer | 2541 | 2541 | 0.0 | quantity |
| `$.number_of_journeyman_workers` | integer | 2541 | 2541 | 0.0 | quantity |
| `$.number_of_other_workers` | integer | 2541 | 2541 | 0.0 | quantity |
| `$.other_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.permissions` | object | 2541 | 2541 | 0.0 | other |
| `$.position` | integer | 2541 | 2541 | 0.0 | other |
| `$.related_items` | array | 2541 | 0 | 100.0 | other |
| `$.status` | string | 2541 | 2541 | 0.0 | status |
| `$.trade` | object | 2541 | 2541 | 0.0 | other |
| `$.updated_at` | string | 2541 | 2541 | 0.0 | date |
| `$.vendor` | object | 2541 | 2541 | 0.0 | company |
| `$.veteran_hours` | string | 2541 | 2541 | 0.0 | quantity |
| `$.women_hours` | string | 2541 | 2541 | 0.0 | quantity |

## daily-log-deliveries (37 paths, 2 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 59 | 59 | 0.0 | other |
| `$.attachments` | array | 59 | 10 | 83.1 | attachment |
| `$.attachments[]` | object | 18 | 18 | 0.0 | attachment |
| `$.comments` | null/string | 59 | 16 | 72.9 | title |
| `$.contents` | string | 59 | 43 | 27.1 | other |
| `$.created_at` | string | 59 | 59 | 0.0 | date |
| `$.created_by` | object | 59 | 59 | 0.0 | person |
| `$.created_by_collaborator` | boolean | 59 | 59 | 0.0 | person |
| `$.custom_fields` | object | 59 | 0 | 100.0 | custom_field |
| `$.date` | string | 59 | 59 | 0.0 | date |
| `$.datetime` | string | 59 | 59 | 0.0 | other |
| `$.deleted_at` | null | 59 | 0 | 100.0 | date |
| `$.delivery_from` | string | 59 | 58 | 1.7 | other |
| `$.id` | integer | 59 | 59 | 0.0 | identity |
| `$.location` | null | 59 | 0 | 100.0 | other |
| `$.permissions` | object | 59 | 59 | 0.0 | other |
| `$.position` | integer | 59 | 59 | 0.0 | other |
| `$.related_items` | array | 59 | 0 | 100.0 | other |
| `$.status` | string | 59 | 59 | 0.0 | status |
| `$.time_hour` | integer | 59 | 59 | 0.0 | quantity |
| `$.time_minute` | integer | 59 | 59 | 0.0 | other |
| `$.tracking_number` | null/string | 59 | 0 | 100.0 | identity |
| `$.updated_at` | string | 59 | 59 | 0.0 | date |
| `$.vendor` | null | 59 | 0 | 100.0 | company |

## daily-log-inspections (46 paths, 2 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 114 | 114 | 0.0 | other |
| `$.area` | null/string | 114 | 38 | 66.7 | other |
| `$.attachments` | array | 114 | 4 | 96.5 | attachment |
| `$.attachments[]` | object | 14 | 14 | 0.0 | attachment |
| `$.comments` | null/string | 114 | 100 | 12.3 | title |
| `$.created_at` | string | 114 | 114 | 0.0 | date |
| `$.created_by` | object | 114 | 114 | 0.0 | person |
| `$.created_by_collaborator` | boolean | 114 | 114 | 0.0 | person |
| `$.custom_fields` | object | 114 | 0 | 100.0 | custom_field |
| `$.date` | string | 114 | 114 | 0.0 | date |
| `$.datetime` | string | 114 | 114 | 0.0 | other |
| `$.deleted_at` | null | 114 | 0 | 100.0 | date |
| `$.end_hour` | integer | 114 | 114 | 0.0 | quantity |
| `$.end_minute` | integer | 114 | 114 | 0.0 | other |
| `$.id` | integer | 114 | 114 | 0.0 | identity |
| `$.inspecting_entity` | string | 114 | 78 | 31.6 | other |
| `$.inspection_type` | string | 114 | 111 | 2.6 | other |
| `$.inspector_name` | null/string | 114 | 105 | 7.9 | person |
| `$.location` | null/object | 114 | 60 | 47.4 | other |
| `$.permissions` | object | 114 | 114 | 0.0 | other |
| `$.position` | integer | 114 | 114 | 0.0 | other |
| `$.related_items` | array | 114 | 0 | 100.0 | other |
| `$.start_hour` | integer | 114 | 114 | 0.0 | quantity |
| `$.start_minute` | integer | 114 | 114 | 0.0 | other |
| `$.status` | string | 114 | 114 | 0.0 | status |
| `$.updated_at` | string | 114 | 114 | 0.0 | date |
| `$.vendor` | null | 114 | 0 | 100.0 | company |

## daily-log-manpower (60 paths, 2 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 883 | 883 | 0.0 | other |
| `$.attachments` | array | 883 | 166 | 81.2 | attachment |
| `$.attachments[]` | object | 771 | 771 | 0.0 | attachment |
| `$.contact` | null/object | 883 | 882 | 0.1 | person |
| `$.cost_code` | null/object | 883 | 2 | 99.8 | identity |
| `$.created_at` | string | 883 | 883 | 0.0 | date |
| `$.created_by` | object | 883 | 883 | 0.0 | person |
| `$.created_by_collaborator` | boolean | 883 | 883 | 0.0 | person |
| `$.custom_fields` | object | 883 | 0 | 100.0 | custom_field |
| `$.date` | string | 883 | 883 | 0.0 | date |
| `$.datetime` | string | 883 | 883 | 0.0 | other |
| `$.deleted_at` | null | 883 | 0 | 100.0 | date |
| `$.id` | integer | 883 | 883 | 0.0 | identity |
| `$.location` | null/object | 883 | 662 | 25.0 | other |
| `$.man_hours` | string | 883 | 883 | 0.0 | quantity |
| `$.notes` | null/string | 883 | 862 | 2.4 | title |
| `$.num_hours` | string | 883 | 883 | 0.0 | quantity |
| `$.num_workers` | integer | 883 | 883 | 0.0 | quantity |
| `$.permissions` | object | 883 | 883 | 0.0 | other |
| `$.position` | integer | 883 | 883 | 0.0 | other |
| `$.related_items` | array | 883 | 0 | 100.0 | other |
| `$.status` | string | 883 | 883 | 0.0 | status |
| `$.trade` | null | 883 | 0 | 100.0 | other |
| `$.updated_at` | string | 883 | 883 | 0.0 | date |
| `$.vendor` | object | 882 | 882 | 0.0 | company |

## daily-log-notes (40 paths, 2 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 92 | 92 | 0.0 | other |
| `$.attachments` | array | 92 | 52 | 43.5 | attachment |
| `$.attachments[]` | object | 1188 | 1188 | 0.0 | attachment |
| `$.comment` | null/string | 92 | 87 | 5.4 | title |
| `$.created_at` | string | 92 | 92 | 0.0 | date |
| `$.created_by` | object | 92 | 92 | 0.0 | person |
| `$.created_by_collaborator` | boolean | 92 | 92 | 0.0 | person |
| `$.custom_fields` | object | 92 | 0 | 100.0 | custom_field |
| `$.daily_log_header_id` | integer | 92 | 92 | 0.0 | identity |
| `$.date` | string | 92 | 92 | 0.0 | date |
| `$.datetime` | string | 92 | 92 | 0.0 | other |
| `$.deleted_at` | null | 92 | 0 | 100.0 | date |
| `$.id` | integer | 92 | 92 | 0.0 | identity |
| `$.is_issue_day` | boolean/null | 92 | 70 | 23.9 | other |
| `$.location` | null/object | 92 | 26 | 71.7 | other |
| `$.permissions` | object | 92 | 92 | 0.0 | other |
| `$.position` | integer | 92 | 92 | 0.0 | other |
| `$.related_items` | array | 92 | 0 | 100.0 | other |
| `$.status` | string | 92 | 92 | 0.0 | status |
| `$.updated_at` | string | 92 | 92 | 0.0 | date |
| `$.vendor` | null | 92 | 0 | 100.0 | company |

## daily-log-visitor (28 paths, 2 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 2 | 2 | 0.0 | other |
| `$.attachments` | array | 2 | 0 | 100.0 | attachment |
| `$.begin_hour` | integer | 2 | 2 | 0.0 | quantity |
| `$.begin_minute` | integer | 2 | 2 | 0.0 | other |
| `$.created_at` | string | 2 | 2 | 0.0 | date |
| `$.created_by` | object | 2 | 2 | 0.0 | person |
| `$.created_by_collaborator` | boolean | 2 | 2 | 0.0 | person |
| `$.custom_fields` | object | 2 | 0 | 100.0 | custom_field |
| `$.date` | string | 2 | 2 | 0.0 | date |
| `$.datetime` | string | 2 | 2 | 0.0 | other |
| `$.deleted_at` | null | 2 | 0 | 100.0 | date |
| `$.details` | string | 2 | 2 | 0.0 | other |
| `$.end_hour` | integer | 2 | 2 | 0.0 | quantity |
| `$.end_minute` | integer | 2 | 2 | 0.0 | other |
| `$.id` | integer | 2 | 2 | 0.0 | identity |
| `$.location` | null | 2 | 0 | 100.0 | other |
| `$.permissions` | object | 2 | 2 | 0.0 | other |
| `$.position` | integer | 2 | 2 | 0.0 | other |
| `$.related_items` | array | 2 | 0 | 100.0 | other |
| `$.status` | string | 2 | 2 | 0.0 | status |
| `$.subject` | string | 2 | 2 | 0.0 | title |
| `$.updated_at` | string | 2 | 2 | 0.0 | date |
| `$.vendor` | null | 2 | 0 | 100.0 | company |

## daily-log-weather (32 paths, 1 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 104 | 104 | 0.0 | other |
| `$.attachments` | array | 104 | 0 | 100.0 | attachment |
| `$.average` | string | 104 | 0 | 100.0 | other |
| `$.calamity` | string | 104 | 0 | 100.0 | other |
| `$.comments` | null | 104 | 0 | 100.0 | title |
| `$.created_at` | string | 104 | 104 | 0.0 | date |
| `$.created_by` | null | 104 | 0 | 100.0 | person |
| `$.created_by_collaborator` | boolean | 104 | 104 | 0.0 | person |
| `$.custom_fields` | object | 104 | 0 | 100.0 | custom_field |
| `$.daily_log_segment` | null | 104 | 0 | 100.0 | cost_code |
| `$.daily_log_segment_id` | null | 104 | 0 | 100.0 | identity |
| `$.date` | string | 104 | 104 | 0.0 | date |
| `$.datetime` | string | 104 | 104 | 0.0 | other |
| `$.deleted_at` | null | 104 | 0 | 100.0 | date |
| `$.ground` | string | 104 | 0 | 100.0 | other |
| `$.id` | integer | 104 | 104 | 0.0 | identity |
| `$.is_weather_delay` | null | 104 | 0 | 100.0 | other |
| `$.location` | null | 104 | 0 | 100.0 | other |
| `$.permissions` | object | 104 | 104 | 0.0 | other |
| `$.position` | integer | 104 | 104 | 0.0 | other |
| `$.precipitation` | string | 104 | 0 | 100.0 | other |
| `$.sky` | string | 104 | 0 | 100.0 | other |
| `$.status` | string | 104 | 104 | 0.0 | status |
| `$.temperature` | string | 104 | 0 | 100.0 | other |
| `$.time` | string | 104 | 104 | 0.0 | other |
| `$.time_hour` | integer | 104 | 104 | 0.0 | quantity |
| `$.time_minute` | integer | 104 | 104 | 0.0 | other |
| `$.updated_at` | string | 104 | 104 | 0.0 | date |
| `$.vendor` | null | 104 | 0 | 100.0 | company |
| `$.wind` | string | 104 | 0 | 100.0 | other |

## inspection-items (69 paths, 8 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 3363 | 3363 | 0.0 | other |
| `$.company_template_item_details` | null | 3363 | 0 | 100.0 | company |
| `$.details` | null/string | 3363 | 80 | 97.6 | other |
| `$.display_conditions` | array | 3363 | 0 | 100.0 | other |
| `$.evidence_configuration` | object | 3363 | 3363 | 0.0 | other |
| `$.evidence_configuration.observation.response_option_ids` | array | 3363 | 1157 | 65.6 | other |
| `$.evidence_configuration.observation.status_ids` | array | 3363 | 0 | 100.0 | status |
| `$.evidence_configuration.photo.response_option_ids` | array | 3363 | 0 | 100.0 | other |
| `$.evidence_configuration.photo.status_ids` | array | 3363 | 0 | 100.0 | status |
| `$.id` | integer | 3363 | 3363 | 0.0 | identity |
| `$.item_reference_ids` | array | 3363 | 0 | 100.0 | other |
| `$.item_response` | null/object | 3363 | 2528 | 24.8 | other |
| `$.list_id` | integer | 3363 | 3363 | 0.0 | identity |
| `$.name` | string | 3363 | 3363 | 0.0 | title |
| `$.number` | string | 3363 | 3363 | 0.0 | identity |
| `$.parent_item_id` | null | 3363 | 0 | 100.0 | identity |
| `$.position` | integer | 3363 | 3363 | 0.0 | other |
| `$.relative_position` | integer | 3363 | 3363 | 0.0 | other |
| `$.responded_with` | string | 3363 | 3363 | 0.0 | other |
| `$.response` | null/object | 3363 | 2526 | 24.9 | other |
| `$.response_set` | null/object | 3363 | 3356 | 0.2 | other |
| `$.response_set.responses` | array | 3356 | 3356 | 0.0 | other |
| `$.section_id` | integer | 3363 | 3363 | 0.0 | identity |
| `$.signature_request_ids` | array | 3363 | 0 | 100.0 | other |
| `$.status` | string | 3363 | 3363 | 0.0 | status |
| `$.template_item_id` | integer | 3363 | 3363 | 0.0 | identity |
| `$.type` | object | 3363 | 3363 | 0.0 | other |
| `$.updated_at` | string | 3363 | 3363 | 0.0 | date |

## inspection-sections (6 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 139 | 139 | 0.0 | other |
| `$.id` | integer | 139 | 139 | 0.0 | identity |
| `$.name` | string | 139 | 139 | 0.0 | title |
| `$.position` | integer | 139 | 139 | 0.0 | other |
| `$.template_section_id` | integer | 139 | 139 | 0.0 | identity |
| `$.updated_at` | string | 139 | 139 | 0.0 | date |

## inspections (126 paths, 7 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 74 | 74 | 0.0 | other |
| `$.asset_ids` | array | 74 | 0 | 100.0 | other |
| `$.attachments` | array | 74 | 42 | 43.2 | attachment |
| `$.attachments[]` | object | 363 | 363 | 0.0 | attachment |
| `$.closed_at` | null/string | 74 | 11 | 85.1 | date |
| `$.closed_by` | null/object | 74 | 11 | 85.1 | status |
| `$.closed_observations_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.conforming_item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.created_at` | string | 74 | 74 | 0.0 | date |
| `$.created_by` | object | 74 | 74 | 0.0 | person |
| `$.current_drawing_revision_ids` | array | 74 | 0 | 100.0 | other |
| `$.custom_fields` | object | 74 | 0 | 100.0 | custom_field |
| `$.default_response_phrasing` | object | 74 | 74 | 0.0 | other |
| `$.deficient_item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.deleted` | boolean | 74 | 74 | 0.0 | status |
| `$.description` | string | 74 | 68 | 8.1 | title |
| `$.distribution_members` | array | 74 | 58 | 21.6 | person |
| `$.distribution_members[]` | object | 213 | 213 | 0.0 | person |
| `$.drawing_ids` | array | 74 | 0 | 100.0 | other |
| `$.due_at` | null/string | 74 | 19 | 74.3 | date |
| `$.equipment` | null | 74 | 0 | 100.0 | other |
| `$.equipment_id` | null | 74 | 0 | 100.0 | identity |
| `$.id` | integer | 74 | 74 | 0.0 | identity |
| `$.identifier` | string | 74 | 74 | 0.0 | other |
| `$.inspected_item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.inspection_date` | string | 74 | 74 | 0.0 | date |
| `$.inspection_type` | object | 74 | 74 | 0.0 | other |
| `$.inspectors` | array | 74 | 74 | 0.0 | person |
| `$.inspectors[]` | object | 101 | 101 | 0.0 | person |
| `$.item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.list_template_id` | integer | 74 | 74 | 0.0 | identity |
| `$.list_template_name` | string | 74 | 74 | 0.0 | title |
| `$.location` | null/object | 74 | 60 | 18.9 | other |
| `$.managed_equipment_id` | null | 74 | 0 | 100.0 | identity |
| `$.name` | string | 74 | 74 | 0.0 | title |
| `$.neutral_item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.not_applicable_item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.number` | integer | 74 | 74 | 0.0 | identity |
| `$.observations_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.overdue` | boolean | 74 | 74 | 0.0 | date |
| `$.point_of_contact` | null/object | 74 | 7 | 90.5 | person |
| `$.private` | boolean | 74 | 74 | 0.0 | status |
| `$.reinspected_by_id` | null | 74 | 0 | 100.0 | identity |
| `$.reinspected_from_id` | null | 74 | 0 | 100.0 | identity |
| `$.respondable_item_count` | integer | 74 | 74 | 0.0 | quantity |
| `$.responsible_contractor` | null/object | 74 | 9 | 87.8 | person |
| `$.schedule` | null | 74 | 0 | 100.0 | other |
| `$.signature_requests` | array | 74 | 8 | 89.2 | other |
| `$.signature_requests[]` | object | 8 | 8 | 0.0 | other |
| `$.specification_section` | null/object | 74 | 2 | 97.3 | other |
| `$.status` | string | 74 | 74 | 0.0 | status |
| `$.template_id` | integer | 74 | 74 | 0.0 | identity |
| `$.trade` | null/object | 74 | 10 | 86.5 | other |
| `$.updated_at` | string | 74 | 74 | 0.0 | date |

## meetings (23 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 97 | 97 | 0.0 | other |
| `$.created_at` | string | 97 | 97 | 0.0 | date |
| `$.created_by_id` | integer | 97 | 97 | 0.0 | identity |
| `$.description` | string | 97 | 97 | 0.0 | title |
| `$.distributed_at` | null/string | 97 | 81 | 16.5 | date |
| `$.distributed_by` | null/object | 97 | 81 | 16.5 | other |
| `$.ends_at` | string | 97 | 97 | 0.0 | date |
| `$.id` | integer | 97 | 97 | 0.0 | identity |
| `$.is_private` | boolean | 97 | 97 | 0.0 | status |
| `$.last_distributed_event` | null/string | 97 | 81 | 16.5 | other |
| `$.location` | null/string | 97 | 92 | 5.2 | other |
| `$.meeting_template_id` | null | 97 | 0 | 100.0 | identity |
| `$.meeting_topics_count` | integer | 97 | 97 | 0.0 | quantity |
| `$.mode` | string | 97 | 97 | 0.0 | other |
| `$.occurred` | boolean | 97 | 97 | 0.0 | other |
| `$.parent_id` | integer/null | 97 | 81 | 16.5 | identity |
| `$.position` | integer | 97 | 97 | 0.0 | other |
| `$.starts_at` | string | 97 | 97 | 0.0 | date |
| `$.title` | string | 97 | 97 | 0.0 | title |
| `$.updated_at` | string | 97 | 97 | 0.0 | date |

## observations (79 paths, 1 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 215 | 215 | 0.0 | other |
| `$.assignee` | null/object | 215 | 209 | 2.8 | person |
| `$.assignees` | array | 215 | 7 | 96.7 | person |
| `$.assignees[]` | object | 7 | 7 | 0.0 | person |
| `$.category` | object | 215 | 215 | 0.0 | other |
| `$.closed_at` | null/string | 215 | 158 | 26.5 | date |
| `$.created_at` | string | 215 | 215 | 0.0 | date |
| `$.created_by` | object | 215 | 215 | 0.0 | person |
| `$.custom_fields` | object | 215 | 0 | 100.0 | custom_field |
| `$.date_notified` | null/string | 215 | 201 | 6.5 | other |
| `$.deleted_at` | null | 215 | 0 | 100.0 | date |
| `$.description` | string | 215 | 142 | 34.0 | title |
| `$.description_rich_text` | null/string | 215 | 142 | 34.0 | title |
| `$.due_date` | string | 215 | 215 | 0.0 | date |
| `$.id` | integer | 215 | 215 | 0.0 | identity |
| `$.location` | null/object | 215 | 145 | 32.6 | other |
| `$.name` | string | 215 | 215 | 0.0 | title |
| `$.number` | string | 215 | 215 | 0.0 | identity |
| `$.origin` | null/object | 215 | 1 | 99.5 | other |
| `$.permissions` | null | 215 | 0 | 100.0 | other |
| `$.personal` | boolean | 215 | 215 | 0.0 | other |
| `$.priority` | null/string | 215 | 13 | 94.0 | other |
| `$.specification_section` | null/object | 215 | 9 | 95.8 | other |
| `$.status` | string | 215 | 215 | 0.0 | status |
| `$.trade` | null/object | 215 | 161 | 25.1 | other |
| `$.type` | object | 215 | 215 | 0.0 | other |
| `$.updated_at` | string | 215 | 215 | 0.0 | date |

## prime-change-order-line-items (16 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 2 | 2 | 0.0 | other |
| `$.amount` | string | 2 | 2 | 0.0 | money |
| `$.description` | string | 2 | 2 | 0.0 | title |
| `$.extended_type` | string | 2 | 2 | 0.0 | other |
| `$.funding_rule_id` | null | 2 | 0 | 100.0 | identity |
| `$.id` | string | 2 | 2 | 0.0 | identity |
| `$.position` | integer | 2 | 2 | 0.0 | other |
| `$.prime_line_item_id` | string | 2 | 2 | 0.0 | identity |
| `$.quantity` | string | 2 | 2 | 0.0 | quantity |
| `$.tax_code_id` | null | 2 | 0 | 100.0 | identity |
| `$.unit_cost` | string | 2 | 2 | 0.0 | money |
| `$.wbs_code` | object | 2 | 2 | 0.0 | identity |
| `$.wbs_code_id` | string | 2 | 2 | 0.0 | identity |

## prime-change-orders (47 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 63 | 63 | 0.0 | other |
| `$.batch_id` | integer/null | 63 | 55 | 12.7 | identity |
| `$.billing_schedule_of_values_status` | string | 63 | 63 | 0.0 | money |
| `$.change_order_change_reason` | null/object | 63 | 60 | 4.8 | title |
| `$.contract_id` | integer | 63 | 63 | 0.0 | identity |
| `$.created_at` | string | 63 | 63 | 0.0 | date |
| `$.created_by` | object | 63 | 63 | 0.0 | person |
| `$.currency_configuration` | object | 63 | 63 | 0.0 | money |
| `$.custom_fields` | object | 63 | 0 | 100.0 | custom_field |
| `$.description` | string | 63 | 63 | 0.0 | title |
| `$.designated_reviewer` | null/object | 63 | 19 | 69.8 | status |
| `$.due_date` | null | 63 | 0 | 100.0 | date |
| `$.enable_ssov` | boolean | 63 | 63 | 0.0 | other |
| `$.executed` | boolean | 63 | 63 | 0.0 | status |
| `$.field_change` | boolean | 63 | 63 | 0.0 | other |
| `$.grand_total` | string | 63 | 63 | 0.0 | money |
| `$.id` | integer | 63 | 63 | 0.0 | identity |
| `$.invoiced_date` | null | 63 | 0 | 100.0 | date |
| `$.legacy_package_id` | integer/null | 63 | 55 | 12.7 | identity |
| `$.legacy_request_id` | integer | 63 | 63 | 0.0 | identity |
| `$.location_id` | integer/null | 63 | 7 | 88.9 | identity |
| `$.number` | string | 63 | 63 | 0.0 | identity |
| `$.paid` | boolean | 63 | 63 | 0.0 | money |
| `$.paid_date` | null | 63 | 0 | 100.0 | date |
| `$.private` | boolean | 63 | 63 | 0.0 | status |
| `$.received_from` | null/object | 63 | 36 | 42.9 | other |
| `$.reference` | null/string | 63 | 31 | 50.8 | other |
| `$.reviewed_at` | null/string | 63 | 48 | 23.8 | date |
| `$.reviewed_by` | null | 63 | 0 | 100.0 | status |
| `$.revised_substantial_completion_date` | null | 63 | 0 | 100.0 | date |
| `$.revision` | integer | 63 | 63 | 0.0 | other |
| `$.schedule_impact_amount` | integer/null | 63 | 32 | 49.2 | money |
| `$.signature_required` | boolean | 63 | 63 | 0.0 | other |
| `$.signed_change_order_received_date` | null | 63 | 0 | 100.0 | date |
| `$.status` | string | 63 | 63 | 0.0 | status |
| `$.title` | string | 63 | 63 | 0.0 | title |
| `$.type` | string | 63 | 63 | 0.0 | other |
| `$.updated_at` | string | 63 | 63 | 0.0 | date |

## prime-contract-line-items (13 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 47 | 47 | 0.0 | other |
| `$.amount` | string | 47 | 47 | 0.0 | money |
| `$.description` | string | 47 | 47 | 0.0 | title |
| `$.funding_rule_id` | null | 47 | 0 | 100.0 | identity |
| `$.id` | string | 47 | 47 | 0.0 | identity |
| `$.line_item_group_id` | null | 47 | 0 | 100.0 | identity |
| `$.position` | integer | 47 | 47 | 0.0 | other |
| `$.tax_code_id` | null | 47 | 0 | 100.0 | identity |
| `$.wbs_code` | object | 47 | 47 | 0.0 | identity |
| `$.wbs_code_id` | string | 47 | 47 | 0.0 | identity |

## prime-contracts (132 paths, 5 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 6 | 6 | 0.0 | other |
| `$.accounting_method` | string | 6 | 6 | 0.0 | other |
| `$.actual_completion_date` | null | 6 | 0 | 100.0 | date |
| `$.approval_letter_date` | null | 6 | 0 | 100.0 | date |
| `$.approved_change_orders` | string | 6 | 6 | 0.0 | status |
| `$.architect` | null/object | 6 | 2 | 66.7 | other |
| `$.attachments` | array | 6 | 0 | 100.0 | attachment |
| `$.contract_date` | null | 6 | 0 | 100.0 | date |
| `$.contract_estimated_completion_date` | null | 6 | 0 | 100.0 | date |
| `$.contract_start_date` | null | 6 | 0 | 100.0 | date |
| `$.contract_termination_date` | null | 6 | 0 | 100.0 | date |
| `$.contractor` | object | 6 | 6 | 0.0 | company |
| `$.contractor.attachments` | array | 3 | 0 | 100.0 | attachment |
| `$.contractor.project_ids` | array | 3 | 3 | 0.0 | other |
| `$.created_at` | string | 6 | 6 | 0.0 | date |
| `$.created_by` | object | 6 | 6 | 0.0 | person |
| `$.currency_configuration` | object | 6 | 6 | 0.0 | money |
| `$.custom_fields` | object | 6 | 0 | 100.0 | custom_field |
| `$.deleted_at` | null | 6 | 0 | 100.0 | date |
| `$.description` | string | 6 | 6 | 0.0 | title |
| `$.draft_change_orders_amount` | string | 6 | 6 | 0.0 | money |
| `$.exclusions` | null | 6 | 0 | 100.0 | other |
| `$.executed` | boolean | 6 | 6 | 0.0 | status |
| `$.execution_date` | null | 6 | 0 | 100.0 | date |
| `$.grand_total` | string | 6 | 6 | 0.0 | money |
| `$.has_change_order_packages` | boolean | 6 | 6 | 0.0 | other |
| `$.has_potential_change_orders` | boolean | 6 | 6 | 0.0 | other |
| `$.id` | integer | 6 | 6 | 0.0 | identity |
| `$.inclusions` | null | 6 | 0 | 100.0 | other |
| `$.issued_on_date` | null | 6 | 0 | 100.0 | date |
| `$.letter_of_intent_date` | null | 6 | 0 | 100.0 | date |
| `$.number` | string | 6 | 6 | 0.0 | identity |
| `$.origin_code` | null | 6 | 0 | 100.0 | identity |
| `$.origin_data` | string | 6 | 6 | 0.0 | other |
| `$.origin_id` | string | 6 | 6 | 0.0 | identity |
| `$.original_substantial_completion_date` | null | 6 | 0 | 100.0 | date |
| `$.outstanding_balance` | string | 6 | 6 | 0.0 | money |
| `$.owner_invoices_amount` | string | 6 | 6 | 0.0 | money |
| `$.pending_change_orders_amount` | string | 6 | 6 | 0.0 | money |
| `$.pending_revised_contract_amount` | string | 6 | 6 | 0.0 | money |
| `$.percentage_paid` | string | 6 | 6 | 0.0 | money |
| `$.private` | boolean | 6 | 6 | 0.0 | status |
| `$.retainage_percent` | string | 6 | 6 | 0.0 | money |
| `$.returned_date` | null | 6 | 0 | 100.0 | date |
| `$.revised_contract_amount` | string | 6 | 6 | 0.0 | money |
| `$.show_line_items_to_non_admins` | null | 6 | 0 | 100.0 | other |
| `$.signed_contract_received_date` | null | 6 | 0 | 100.0 | date |
| `$.status` | string | 6 | 6 | 0.0 | status |
| `$.substantial_completion_date` | null | 6 | 0 | 100.0 | date |
| `$.title` | string | 6 | 6 | 0.0 | title |
| `$.total_payments` | string | 6 | 6 | 0.0 | money |
| `$.updated_at` | string | 6 | 6 | 0.0 | date |
| `$.vendor` | object | 6 | 6 | 0.0 | company |
| `$.vendor.attachments` | array | 3 | 0 | 100.0 | attachment |
| `$.vendor.project_ids` | array | 3 | 3 | 0.0 | other |

## projects (145 paths, 7 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 7 | 7 | 0.0 | other |
| `$.accounting_project_number` | null/string | 7 | 1 | 85.7 | identity |
| `$.active` | boolean | 7 | 7 | 0.0 | other |
| `$.address` | null/string | 7 | 6 | 14.3 | other |
| `$.city` | string | 7 | 7 | 0.0 | other |
| `$.company` | object | 7 | 7 | 0.0 | company |
| `$.completion_date` | string | 7 | 7 | 0.0 | date |
| `$.country_code` | string | 7 | 7 | 0.0 | identity |
| `$.county` | string | 7 | 7 | 0.0 | other |
| `$.created_at` | string | 7 | 7 | 0.0 | date |
| `$.created_by` | object | 7 | 7 | 0.0 | person |
| `$.custom_fields` | object | 7 | 7 | 0.0 | custom_field |
| `$.custom_fields.custom_field_163287.value` | array | 7 | 5 | 28.6 | money |
| `$.custom_fields.custom_field_163290.value` | array | 7 | 3 | 57.1 | money |
| `$.custom_fields.custom_field_163293.value` | array | 7 | 2 | 71.4 | money |
| `$.custom_fields.custom_field_163296.value` | array | 7 | 1 | 85.7 | money |
| `$.custom_fields.custom_field_163299.value` | array | 7 | 1 | 85.7 | money |
| `$.custom_fields.custom_field_163302.value` | array | 7 | 1 | 85.7 | money |
| `$.custom_fields.custom_field_163305.value` | array | 7 | 1 | 85.7 | money |
| `$.delivery_method` | null/string | 7 | 4 | 42.9 | other |
| `$.designated_market_area` | null/string | 7 | 0 | 100.0 | other |
| `$.display_name` | string | 7 | 7 | 0.0 | title |
| `$.estimated_value` | null/string | 7 | 6 | 14.3 | money |
| `$.id` | integer | 7 | 7 | 0.0 | identity |
| `$.is_demo` | boolean | 7 | 7 | 0.0 | other |
| `$.latitude` | number | 7 | 7 | 0.0 | other |
| `$.longitude` | number | 7 | 7 | 0.0 | other |
| `$.name` | string | 7 | 7 | 0.0 | title |
| `$.origin_code` | string | 7 | 7 | 0.0 | identity |
| `$.origin_data` | null/string | 7 | 6 | 14.3 | other |
| `$.origin_id` | string | 7 | 7 | 0.0 | identity |
| `$.owners_project_id` | null | 7 | 0 | 100.0 | identity |
| `$.parent_job` | null | 7 | 0 | 100.0 | other |
| `$.parent_job_id` | null | 7 | 0 | 100.0 | identity |
| `$.phone` | null/string | 7 | 0 | 100.0 | other |
| `$.photo_id` | integer/null | 7 | 3 | 57.1 | identity |
| `$.project_bid_type_id` | integer/null | 7 | 3 | 57.1 | identity |
| `$.project_number` | string | 7 | 7 | 0.0 | identity |
| `$.project_owner_type_id` | null | 7 | 0 | 100.0 | identity |
| `$.project_region_id` | null | 7 | 0 | 100.0 | identity |
| `$.project_sector_id` | integer/null | 7 | 4 | 42.9 | identity |
| `$.project_stage` | null/object | 7 | 6 | 14.3 | status |
| `$.project_template` | object | 6 | 6 | 0.0 | other |
| `$.projected_finish_date` | string | 7 | 7 | 0.0 | date |
| `$.sector` | null/string | 7 | 4 | 42.9 | other |
| `$.stage` | string | 7 | 7 | 0.0 | status |
| `$.start_date` | string | 7 | 7 | 0.0 | date |
| `$.state_code` | string | 7 | 7 | 0.0 | identity |
| `$.store_number` | null/string | 7 | 0 | 100.0 | identity |
| `$.time_zone` | string | 7 | 7 | 0.0 | other |
| `$.total_value` | null/string | 7 | 6 | 14.3 | money |
| `$.updated_at` | string | 7 | 7 | 0.0 | date |
| `$.work_scope` | null/string | 7 | 4 | 42.9 | title |
| `$.zip` | string | 7 | 7 | 0.0 | other |

## punch-items (101 paths, 4 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 4 | 4 | 0.0 | other |
| `$.assignees` | array | 4 | 4 | 0.0 | person |
| `$.assignees[]` | object | 4 | 4 | 0.0 | person |
| `$.assignments` | array | 4 | 4 | 0.0 | other |
| `$.assignments[]` | object | 4 | 4 | 0.0 | other |
| `$.assignments[].attachments` | array | 4 | 0 | 100.0 | attachment |
| `$.ball_in_court` | array | 4 | 4 | 0.0 | person |
| `$.ball_in_court[]` | object | 4 | 4 | 0.0 | person |
| `$.closed_at` | null | 4 | 0 | 100.0 | date |
| `$.closed_by` | null | 4 | 0 | 100.0 | status |
| `$.cost_code` | null | 4 | 0 | 100.0 | identity |
| `$.cost_impact` | null/string | 4 | 0 | 100.0 | money |
| `$.cost_impact_amount` | null | 4 | 0 | 100.0 | money |
| `$.created_at` | string | 4 | 4 | 0.0 | date |
| `$.created_by` | object | 4 | 4 | 0.0 | person |
| `$.custom_fields` | object | 4 | 0 | 100.0 | custom_field |
| `$.deleted_at` | null | 4 | 0 | 100.0 | date |
| `$.description` | string | 4 | 4 | 0.0 | title |
| `$.due_date` | string | 4 | 4 | 0.0 | date |
| `$.due_tomorrow` | boolean | 4 | 4 | 0.0 | date |
| `$.final_approver` | object | 4 | 4 | 0.0 | person |
| `$.flagged_by` | null | 4 | 0 | 100.0 | other |
| `$.has_attachments` | boolean | 4 | 4 | 0.0 | attachment |
| `$.has_resolved_responses` | boolean | 4 | 4 | 0.0 | other |
| `$.has_unresolved_responses` | boolean | 4 | 4 | 0.0 | other |
| `$.id` | integer | 4 | 4 | 0.0 | identity |
| `$.location` | object | 4 | 4 | 0.0 | other |
| `$.manager_notified_at` | string | 4 | 4 | 0.0 | date |
| `$.name` | string | 4 | 4 | 0.0 | title |
| `$.overdue` | boolean | 4 | 4 | 0.0 | date |
| `$.position` | integer | 4 | 4 | 0.0 | other |
| `$.priority` | null | 4 | 0 | 100.0 | other |
| `$.private` | boolean | 4 | 4 | 0.0 | status |
| `$.punch_item_manager` | object | 4 | 4 | 0.0 | person |
| `$.punch_item_type` | null | 4 | 0 | 100.0 | other |
| `$.reference` | null/string | 4 | 0 | 100.0 | other |
| `$.schedule_impact` | null/string | 4 | 0 | 100.0 | other |
| `$.schedule_impact_days` | null | 4 | 0 | 100.0 | other |
| `$.schedule_risk` | null | 4 | 0 | 100.0 | other |
| `$.schedule_risk_reason` | null | 4 | 0 | 100.0 | title |
| `$.should_display_risk_flag` | boolean | 4 | 4 | 0.0 | other |
| `$.status` | string | 4 | 4 | 0.0 | status |
| `$.trade` | object | 4 | 4 | 0.0 | other |
| `$.updated_at` | string | 4 | 4 | 0.0 | date |
| `$.workflow_status` | string | 4 | 4 | 0.0 | status |

## purchase-order-contracts (214 paths, 4 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 10 | 10 | 0.0 | other |
| `$.accounting_method` | string | 10 | 10 | 0.0 | other |
| `$.allow_change_orders_ssov` | boolean | 10 | 10 | 0.0 | other |
| `$.approval_letter_date` | null | 10 | 0 | 100.0 | date |
| `$.approved_change_orders` | string | 10 | 10 | 0.0 | status |
| `$.assignee` | null/object | 10 | 5 | 50.0 | person |
| `$.bill_to_address` | string | 10 | 10 | 0.0 | other |
| `$.billing_schedule_of_values_status` | string | 10 | 10 | 0.0 | money |
| `$.contract_date` | null | 10 | 0 | 100.0 | date |
| `$.created_at` | string | 10 | 10 | 0.0 | date |
| `$.created_by_id` | integer | 10 | 10 | 0.0 | identity |
| `$.currency_configuration` | object | 10 | 10 | 0.0 | money |
| `$.custom_fields` | object | 10 | 10 | 0.0 | custom_field |
| `$.custom_fields.custom_field_214073.value` | array | 10 | 0 | 100.0 | money |
| `$.custom_fields.custom_field_214080.value` | array | 10 | 0 | 100.0 | money |
| `$.custom_fields.custom_field_214093.value` | array | 10 | 0 | 100.0 | money |
| `$.custom_fields.custom_field_214094.value` | array | 10 | 1 | 90.0 | money |
| `$.deleted_at` | null | 10 | 0 | 100.0 | date |
| `$.delivery_date` | null/string | 10 | 5 | 50.0 | date |
| `$.description` | null/string | 10 | 8 | 20.0 | title |
| `$.draft_change_orders_amount` | string | 10 | 10 | 0.0 | money |
| `$.enable_ssov` | boolean | 10 | 10 | 0.0 | other |
| `$.executed` | boolean | 10 | 10 | 0.0 | status |
| `$.execution_date` | null | 10 | 0 | 100.0 | date |
| `$.grand_total` | string | 10 | 10 | 0.0 | money |
| `$.has_change_order_packages` | boolean | 10 | 10 | 0.0 | other |
| `$.has_potential_change_orders` | boolean | 10 | 10 | 0.0 | other |
| `$.id` | integer | 10 | 10 | 0.0 | identity |
| `$.issued_on_date` | null | 10 | 0 | 100.0 | date |
| `$.letter_of_intent_date` | null | 10 | 0 | 100.0 | date |
| `$.number` | string | 10 | 10 | 0.0 | identity |
| `$.origin_code` | null/string | 10 | 7 | 30.0 | identity |
| `$.origin_data` | null | 10 | 0 | 100.0 | other |
| `$.origin_id` | null/string | 10 | 7 | 30.0 | identity |
| `$.payment_terms` | null/string | 10 | 1 | 90.0 | money |
| `$.pending_change_orders` | string | 10 | 10 | 0.0 | other |
| `$.pending_revised_contract` | string | 10 | 10 | 0.0 | other |
| `$.percentage_paid` | string | 10 | 10 | 0.0 | money |
| `$.private` | boolean | 10 | 10 | 0.0 | status |
| `$.project` | object | 10 | 10 | 0.0 | other |
| `$.remaining_balance_outstanding` | string | 10 | 10 | 0.0 | money |
| `$.requisitions_are_enabled` | boolean | 10 | 10 | 0.0 | other |
| `$.retainage_percent` | string | 10 | 10 | 0.0 | money |
| `$.returned_date` | null | 10 | 0 | 100.0 | date |
| `$.revised_contract` | string | 10 | 10 | 0.0 | other |
| `$.ship_to_address` | string | 10 | 10 | 0.0 | other |
| `$.ship_via` | null | 10 | 0 | 100.0 | other |
| `$.show_line_items_to_non_admins` | boolean | 10 | 10 | 0.0 | other |
| `$.signed_contract_received_date` | null/string | 10 | 1 | 90.0 | date |
| `$.status` | string | 10 | 10 | 0.0 | status |
| `$.title` | string | 10 | 10 | 0.0 | title |
| `$.total_draw_requests_amount` | string | 10 | 10 | 0.0 | money |
| `$.total_payments` | string | 10 | 10 | 0.0 | money |
| `$.total_requisitions_amount` | string | 10 | 10 | 0.0 | money |
| `$.updated_at` | string | 10 | 10 | 0.0 | date |
| `$.vendor` | object | 10 | 10 | 0.0 | company |

## purchase-order-line-items (62 paths, 1 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 12 | 12 | 0.0 | other |
| `$.amount` | string | 12 | 12 | 0.0 | money |
| `$.company` | object | 12 | 12 | 0.0 | company |
| `$.cost_code` | object | 12 | 12 | 0.0 | identity |
| `$.cost_code.line_item_types` | array | 12 | 12 | 0.0 | other |
| `$.created_at` | string | 12 | 12 | 0.0 | date |
| `$.currency_configuration` | object | 12 | 12 | 0.0 | money |
| `$.description` | string | 12 | 12 | 0.0 | title |
| `$.extended_amount` | string | 12 | 12 | 0.0 | money |
| `$.extended_type` | string | 12 | 12 | 0.0 | other |
| `$.holder` | object | 12 | 12 | 0.0 | other |
| `$.id` | integer | 12 | 12 | 0.0 | identity |
| `$.line_item_type` | object | 12 | 12 | 0.0 | other |
| `$.origin_id` | null/string | 12 | 4 | 66.7 | identity |
| `$.position` | integer | 12 | 12 | 0.0 | other |
| `$.project` | object | 12 | 12 | 0.0 | other |
| `$.quantity` | string | 12 | 12 | 0.0 | quantity |
| `$.total_amount` | string | 12 | 12 | 0.0 | money |
| `$.unit_cost` | string | 12 | 12 | 0.0 | money |
| `$.uom` | string | 3 | 3 | 0.0 | quantity |
| `$.updated_at` | string | 12 | 12 | 0.0 | date |
| `$.wbs_code` | object | 12 | 12 | 0.0 | identity |

## rfis (101 paths, 3 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 607 | 607 | 0.0 | other |
| `$.assignee` | null/object | 607 | 592 | 2.5 | person |
| `$.assignees` | array | 607 | 592 | 2.5 | person |
| `$.assignees[]` | object | 1018 | 1018 | 0.0 | person |
| `$.ball_in_court` | null/object | 607 | 55 | 90.9 | person |
| `$.ball_in_courts` | array | 607 | 55 | 90.9 | person |
| `$.ball_in_courts[]` | object | 76 | 76 | 0.0 | person |
| `$.connect_export_origin` | null | 607 | 0 | 100.0 | other |
| `$.cost_code` | null/object | 607 | 30 | 95.1 | identity |
| `$.cost_impact` | object | 607 | 607 | 0.0 | money |
| `$.created_at` | string | 607 | 607 | 0.0 | date |
| `$.created_by` | object | 607 | 607 | 0.0 | person |
| `$.current_revision` | boolean | 607 | 607 | 0.0 | other |
| `$.custom_fields` | object | 607 | 0 | 100.0 | custom_field |
| `$.due_date` | null/string | 607 | 588 | 3.1 | date |
| `$.full_number` | null/string | 607 | 588 | 3.1 | identity |
| `$.has_revisions` | boolean | 607 | 607 | 0.0 | other |
| `$.id` | integer | 607 | 607 | 0.0 | identity |
| `$.initiated_at` | null/string | 607 | 588 | 3.1 | date |
| `$.link` | string | 607 | 607 | 0.0 | other |
| `$.location` | null/object | 607 | 76 | 87.5 | other |
| `$.location_id` | integer/null | 607 | 76 | 87.5 | identity |
| `$.number` | null/string | 607 | 588 | 3.1 | identity |
| `$.prefix` | null | 607 | 0 | 100.0 | other |
| `$.priority` | object | 607 | 607 | 0.0 | other |
| `$.private` | boolean | 607 | 607 | 0.0 | status |
| `$.project_stage` | null/object | 607 | 160 | 73.6 | status |
| `$.proposed_solution` | null/string | 607 | 0 | 100.0 | other |
| `$.questions` | array | 607 | 607 | 0.0 | title |
| `$.questions[]` | object | 607 | 607 | 0.0 | title |
| `$.received_from` | null/object | 607 | 509 | 16.1 | other |
| `$.reference` | null/string | 607 | 40 | 93.4 | other |
| `$.responsible_contractor` | null/object | 607 | 516 | 15.0 | person |
| `$.revision` | string | 607 | 607 | 0.0 | other |
| `$.rfi_manager` | object | 607 | 607 | 0.0 | person |
| `$.schedule_impact` | object | 607 | 607 | 0.0 | other |
| `$.source_rfi_header_id` | integer | 607 | 607 | 0.0 | identity |
| `$.specification_section_id` | integer/null | 607 | 21 | 96.5 | identity |
| `$.status` | string | 607 | 607 | 0.0 | status |
| `$.sub_job` | null/object | 607 | 63 | 89.6 | other |
| `$.subject` | string | 607 | 607 | 0.0 | title |
| `$.time_resolved` | null/string | 607 | 552 | 9.1 | other |
| `$.translated_status` | string | 607 | 607 | 0.0 | status |
| `$.updated_at` | string | 607 | 607 | 0.0 | date |

## rfqs (256 paths, 7 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 7 | 7 | 0.0 | other |
| `$.assigned` | object | 5 | 5 | 0.0 | attachment |
| `$.attachments` | array | 7 | 6 | 14.3 | attachment |
| `$.attachments[]` | object | 11 | 11 | 0.0 | attachment |
| `$.change_event` | object | 7 | 7 | 0.0 | other |
| `$.change_event.attachments` | array | 7 | 6 | 14.3 | attachment |
| `$.change_event.change_event_line_items` | array | 7 | 7 | 0.0 | other |
| `$.change_event.change_event_line_items[].cost_code.line_item_types` | array | 52 | 52 | 0.0 | other |
| `$.change_event_line_item_id` | integer | 7 | 7 | 0.0 | identity |
| `$.commitment_change_order_packages` | object | 3 | 3 | 0.0 | other |
| `$.commitment_contract_id` | integer | 7 | 7 | 0.0 | identity |
| `$.commitment_potential_change_orders` | object | 3 | 3 | 0.0 | other |
| `$.created_at` | string | 7 | 7 | 0.0 | date |
| `$.created_by` | object | 7 | 7 | 0.0 | person |
| `$.currency_configuration` | object | 7 | 7 | 0.0 | money |
| `$.description` | string | 7 | 7 | 0.0 | title |
| `$.due_date` | string | 7 | 7 | 0.0 | date |
| `$.estimated_status` | string | 7 | 7 | 0.0 | status |
| `$.id` | integer | 7 | 7 | 0.0 | identity |
| `$.intent_to_quote` | boolean | 4 | 4 | 0.0 | other |
| `$.number` | string | 7 | 7 | 0.0 | identity |
| `$.position` | integer | 7 | 7 | 0.0 | other |
| `$.private` | boolean | 7 | 7 | 0.0 | status |
| `$.prostore_file_ids` | array | 7 | 6 | 14.3 | attachment |
| `$.prostore_file_ids[]` | integer | 11 | 11 | 0.0 | attachment |
| `$.quotes` | array | 7 | 0 | 100.0 | other |
| `$.responses` | array | 7 | 0 | 100.0 | other |
| `$.status` | string | 7 | 7 | 0.0 | status |
| `$.title` | string | 7 | 7 | 0.0 | title |
| `$.updated_at` | string | 7 | 7 | 0.0 | date |

## schedules (17 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 1 | 1 | 0.0 | other |
| `$.calendar_id` | string | 1 | 1 | 0.0 | identity |
| `$.company_id` | string | 1 | 1 | 0.0 | identity |
| `$.created_at` | string | 1 | 1 | 0.0 | date |
| `$.created_by` | string | 1 | 1 | 0.0 | person |
| `$.data_date` | string | 1 | 1 | 0.0 | date |
| `$.deleted_at` | null | 1 | 0 | 100.0 | date |
| `$.deleted_by` | null | 1 | 0 | 100.0 | person |
| `$.is_active` | boolean | 1 | 1 | 0.0 | other |
| `$.parent_schedule_id` | null | 1 | 0 | 100.0 | identity |
| `$.project_id` | string | 1 | 1 | 0.0 | identity |
| `$.schedule_id` | string | 1 | 1 | 0.0 | identity |
| `$.schedule_name` | string | 1 | 1 | 0.0 | title |
| `$.schedule_type` | string | 1 | 1 | 0.0 | other |
| `$.start_date` | string | 1 | 1 | 0.0 | date |
| `$.updated_at` | string | 1 | 1 | 0.0 | date |
| `$.updated_by` | string | 1 | 1 | 0.0 | person |

## subcontractor-invoice-change-order-items (35 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 24 | 24 | 0.0 | other |
| `$.change_order_package_id` | integer | 24 | 24 | 0.0 | identity |
| `$.comment` | null | 24 | 0 | 100.0 | title |
| `$.commitment_line_item_id` | integer | 24 | 24 | 0.0 | identity |
| `$.commitment_line_item_origin_id` | null/string | 24 | 22 | 8.3 | identity |
| `$.cost_code_id` | integer | 24 | 24 | 0.0 | identity |
| `$.currency_configuration` | object | 24 | 24 | 0.0 | money |
| `$.description_of_work` | string | 24 | 24 | 0.0 | title |
| `$.id` | integer | 24 | 24 | 0.0 | identity |
| `$.item_type` | string | 24 | 24 | 0.0 | other |
| `$.line_item_id` | integer | 24 | 24 | 0.0 | identity |
| `$.materials_moved` | string | 24 | 24 | 0.0 | other |
| `$.materials_retainage_retained_moved` | string | 24 | 24 | 0.0 | money |
| `$.position` | integer | 24 | 24 | 0.0 | other |
| `$.scheduled_quantity` | string | 24 | 24 | 0.0 | quantity |
| `$.scheduled_unit_price` | string | 24 | 24 | 0.0 | money |
| `$.scheduled_value` | string | 24 | 24 | 0.0 | money |
| `$.ssr_manual_override` | boolean | 24 | 24 | 0.0 | other |
| `$.status` | string | 24 | 24 | 0.0 | status |
| `$.subcontractor_claimed_amount` | string | 24 | 24 | 0.0 | money |
| `$.total_completed_and_stored_to_date` | string | 24 | 24 | 0.0 | date |
| `$.total_completed_and_stored_to_date_percent` | string | 24 | 24 | 0.0 | money |
| `$.wbs_code` | object | 24 | 24 | 0.0 | identity |
| `$.work_completed_from_previous_application` | string | 24 | 24 | 0.0 | other |
| `$.work_completed_from_previous_application_quantity` | string | 24 | 24 | 0.0 | quantity |
| `$.work_completed_retainage_from_previous_application` | string | 24 | 24 | 0.0 | money |
| `$.work_completed_retainage_percent_this_period` | string | 24 | 24 | 0.0 | money |
| `$.work_completed_retainage_released_this_period` | string | 24 | 24 | 0.0 | money |
| `$.work_completed_retainage_retained_this_period` | string | 24 | 24 | 0.0 | money |
| `$.work_completed_this_period` | string | 24 | 24 | 0.0 | other |
| `$.work_completed_this_period_quantity` | string | 24 | 24 | 0.0 | quantity |

## subcontractor-invoice-contract-detail-items (32 paths, 0 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 152 | 152 | 0.0 | other |
| `$.comment` | null | 152 | 0 | 100.0 | title |
| `$.cost_code_id` | integer | 152 | 152 | 0.0 | identity |
| `$.currency_configuration` | object | 152 | 152 | 0.0 | money |
| `$.description_of_work` | string | 152 | 152 | 0.0 | title |
| `$.detail_line_item_id` | integer | 152 | 152 | 0.0 | identity |
| `$.id` | integer | 152 | 152 | 0.0 | identity |
| `$.item_type` | string | 152 | 152 | 0.0 | other |
| `$.materials_moved` | string | 152 | 152 | 0.0 | other |
| `$.materials_presently_stored` | string | 152 | 152 | 0.0 | other |
| `$.materials_retainage_retained_moved` | string | 152 | 152 | 0.0 | money |
| `$.materials_stored_retainage_currently_retained` | string | 152 | 152 | 0.0 | money |
| `$.materials_stored_retainage_percent_this_period` | string | 152 | 152 | 0.0 | money |
| `$.materials_stored_retainage_released_this_period` | string | 152 | 152 | 0.0 | money |
| `$.position` | integer | 152 | 152 | 0.0 | other |
| `$.scheduled_value` | string | 152 | 152 | 0.0 | money |
| `$.ssr_manual_override` | boolean | 152 | 152 | 0.0 | other |
| `$.status` | string | 152 | 152 | 0.0 | status |
| `$.subcontractor_claimed_amount` | string | 152 | 152 | 0.0 | money |
| `$.total_completed_and_stored_to_date` | string | 152 | 152 | 0.0 | date |
| `$.total_completed_and_stored_to_date_percent` | string | 152 | 152 | 0.0 | money |
| `$.wbs_code` | object | 152 | 152 | 0.0 | identity |
| `$.work_completed_from_previous_application` | string | 152 | 152 | 0.0 | other |
| `$.work_completed_retainage_from_previous_application` | string | 152 | 152 | 0.0 | money |
| `$.work_completed_retainage_percent_this_period` | string | 152 | 152 | 0.0 | money |
| `$.work_completed_retainage_released_this_period` | string | 152 | 152 | 0.0 | money |
| `$.work_completed_retainage_retained_this_period` | string | 152 | 152 | 0.0 | money |
| `$.work_completed_this_period` | string | 152 | 152 | 0.0 | other |

## subcontractor-invoices (78 paths, 1 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 228 | 228 | 0.0 | other |
| `$.attachments` | array | 228 | 211 | 7.5 | attachment |
| `$.attachments[]` | object | 215 | 215 | 0.0 | attachment |
| `$.billing_date` | string | 228 | 228 | 0.0 | date |
| `$.comment` | null/string | 228 | 40 | 82.5 | title |
| `$.commitment_id` | integer | 228 | 228 | 0.0 | identity |
| `$.commitment_type` | string | 228 | 228 | 0.0 | other |
| `$.contract_invoicing_method` | string | 228 | 228 | 0.0 | other |
| `$.contract_name` | string | 228 | 228 | 0.0 | title |
| `$.created_at` | string | 228 | 228 | 0.0 | date |
| `$.created_by` | object | 228 | 228 | 0.0 | person |
| `$.currency_configuration` | object | 228 | 228 | 0.0 | money |
| `$.custom_fields` | object | 228 | 0 | 100.0 | custom_field |
| `$.deletable` | boolean | 228 | 228 | 0.0 | other |
| `$.electronic_signature_id` | null | 228 | 0 | 100.0 | identity |
| `$.erp_status` | string | 228 | 228 | 0.0 | status |
| `$.final` | boolean | 228 | 228 | 0.0 | other |
| `$.id` | integer | 228 | 228 | 0.0 | identity |
| `$.invoice_number` | string | 228 | 222 | 2.6 | identity |
| `$.invoice_type` | string | 228 | 228 | 0.0 | other |
| `$.move_materials_to_previous_work_completed` | boolean | 228 | 228 | 0.0 | other |
| `$.number` | integer | 228 | 228 | 0.0 | identity |
| `$.origin_data` | null | 228 | 0 | 100.0 | other |
| `$.origin_id` | null | 228 | 0 | 100.0 | identity |
| `$.payment_date` | null | 228 | 0 | 100.0 | date |
| `$.payment_summary` | object | 228 | 228 | 0.0 | money |
| `$.percent_complete` | string | 228 | 228 | 0.0 | other |
| `$.period_id` | integer | 228 | 228 | 0.0 | identity |
| `$.previous_requisition_id` | integer/null | 228 | 184 | 19.3 | identity |
| `$.project_id` | integer | 228 | 228 | 0.0 | identity |
| `$.requisition_end` | string | 228 | 228 | 0.0 | other |
| `$.requisition_start` | string | 228 | 228 | 0.0 | other |
| `$.status` | string | 228 | 228 | 0.0 | status |
| `$.submitted_at` | null/string | 228 | 88 | 61.4 | date |
| `$.summary` | object | 228 | 228 | 0.0 | money |
| `$.total_claimed_amount` | string | 228 | 228 | 0.0 | money |
| `$.updated_at` | string | 228 | 228 | 0.0 | date |
| `$.vendor_id` | integer | 228 | 228 | 0.0 | identity |
| `$.vendor_name` | string | 228 | 228 | 0.0 | company |

## submittals (144 paths, 7 arrays)

| json_path | type | occ | non-empty | null/empty % | category |
|---|---|--:|--:|--:|---|
| `$` | object | 449 | 449 | 0.0 | other |
| `$.approvers` | array | 449 | 442 | 1.6 | person |
| `$.approvers[]` | object | 1519 | 1519 | 0.0 | person |
| `$.approvers[].attachments` | array | 1519 | 1264 | 16.8 | attachment |
| `$.approvers[].submittal_associated_attachment_ids` | array | 1519 | 1264 | 16.8 | attachment |
| `$.attachments_count` | integer | 449 | 449 | 0.0 | quantity |
| `$.ball_in_court` | array | 449 | 80 | 82.2 | person |
| `$.ball_in_court[]` | object | 81 | 81 | 0.0 | person |
| `$.buffer_time` | null | 449 | 0 | 100.0 | other |
| `$.closed_at` | null/string | 449 | 359 | 20.0 | date |
| `$.created_at` | string | 449 | 449 | 0.0 | date |
| `$.created_by` | object | 449 | 449 | 0.0 | person |
| `$.current_revision` | boolean | 449 | 449 | 0.0 | other |
| `$.custom_fields` | object | 449 | 449 | 0.0 | custom_field |
| `$.distributed_at` | null/string | 449 | 40 | 91.1 | date |
| `$.due_date` | null/string | 449 | 442 | 1.6 | date |
| `$.for_record_only` | boolean | 449 | 449 | 0.0 | other |
| `$.formatted_number` | string | 449 | 449 | 0.0 | identity |
| `$.id` | integer | 449 | 449 | 0.0 | identity |
| `$.is_rejected` | boolean | 449 | 449 | 0.0 | other |
| `$.issue_date` | null/string | 449 | 399 | 11.1 | date |
| `$.location` | null/object | 449 | 65 | 85.5 | other |
| `$.number` | string | 449 | 449 | 0.0 | identity |
| `$.open_date` | null/string | 449 | 336 | 25.2 | date |
| `$.operation_item_errors` | array | 449 | 0 | 100.0 | other |
| `$.private` | boolean | 449 | 449 | 0.0 | status |
| `$.received_date` | null/string | 449 | 57 | 87.3 | date |
| `$.received_from` | null/object | 449 | 378 | 15.8 | other |
| `$.rejected_submittal_log_approver_id` | null | 449 | 0 | 100.0 | identity |
| `$.required_on_site_date` | null/string | 449 | 4 | 99.1 | date |
| `$.responsible_contractor` | null/object | 449 | 445 | 0.9 | person |
| `$.revision` | string | 449 | 449 | 0.0 | other |
| `$.scheduled_task` | null | 449 | 0 | 100.0 | other |
| `$.specification_section` | null/object | 449 | 446 | 0.7 | other |
| `$.status` | object | 449 | 449 | 0.0 | status |
| `$.sub_job` | null | 449 | 0 | 100.0 | other |
| `$.submit_by` | null/string | 449 | 24 | 94.7 | other |
| `$.submittal_manager` | object | 449 | 449 | 0.0 | person |
| `$.submittal_package` | null/object | 449 | 99 | 78.0 | other |
| `$.submittal_package.attachments` | array | 99 | 0 | 100.0 | attachment |
| `$.submittal_package.submittal_ids` | array | 99 | 99 | 0.0 | other |
| `$.submittal_workflow_template` | null/object | 449 | 65 | 85.5 | other |
| `$.submittal_workflow_template_applied_at` | null/string | 449 | 65 | 85.5 | date |
| `$.title` | string | 449 | 449 | 0.0 | title |
| `$.type` | null/object | 449 | 427 | 4.9 | other |
| `$.updated_at` | string | 449 | 449 | 0.0 | date |

