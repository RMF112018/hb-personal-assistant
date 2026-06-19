# Shareable Redacted Raw Payload Samples for Procore Missing Mapping Cleanup

## Summary

- Generated UTC: `2026-06-19T05:15:41.504695+00:00`
- Target fields included: `200`
- Endpoints loaded: `billing-periods, budget-change-history, budget-modifications, budget-views, change-events, commitment-attachments, commitment-change-orders, commitment-compliance, commitment-contracts, commitment-line-items, daily-log-dcrs, daily-log-deliveries, daily-log-inspections, daily-log-manpower, daily-log-notes, daily-log-visitor, daily-log-weather, inspection-items, inspection-sections, inspections, meetings, observations, prime-change-order-line-items, prime-change-orders, prime-contract-line-items, prime-contracts, projects, punch-items, purchase-order-contracts, purchase-order-line-items, rfis, rfqs, subcontractor-invoice-change-order-items, subcontractor-invoice-contract-detail-items, subcontractor-invoices, submittals`
- Raw payload bodies emitted: `false`
- Raw scalar values emitted: `false`
- Redacted structural samples included: `true`

## Field Path Evidence

### `procore_ep_billing_periods.company_id`

- Inferred endpoint: `billing-periods`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `20`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `20`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 20 | 0 | 0 | 20 | 0 |
| `$.company_id` | 20 | 0 | 0 | 20 | 0 |
| `$.project.company.id` | 20 | 0 | 0 | 20 | 0 |
| `$.project.company_id` | 20 | 0 | 0 | 20 | 0 |
| `$.company` | 20 | 0 | 0 | 20 | 0 |

Root keys from first matching payload:

```text
created_at, due_date, end_date, id, position, project_id, start_date, status, updated_at
```

### `procore_ep_budget_change_history.company_id`

- Inferred endpoint: `budget-change-history`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `95`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 100 | 0 | 0 | 100 | 0 |
| `$.company_id` | 100 | 0 | 0 | 100 | 0 |
| `$.project.company.id` | 100 | 0 | 0 | 100 | 0 |
| `$.project.company_id` | 100 | 0 | 0 | 100 | 0 |
| `$.company` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
budget_code, column, created_at, created_by, description, new_value, old_value, type
```

### `procore_ep_budget_detail_columns.company_id`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `276`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company_id` | 0 | 0 | 0 | 0 | 0 |
| `$.company.id` | 0 | 0 | 0 | 0 | 0 |
| `$.project.company_id` | 0 | 0 | 0 | 0 | 0 |
| `$.project.company.id` | 0 | 0 | 0 | 0 | 0 |
| `$.company` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_columns.visible`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `276`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.visible` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_row_cells.company_id`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `225131`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company_id` | 0 | 0 | 0 | 0 | 0 |
| `$.company.id` | 0 | 0 | 0 | 0 | 0 |
| `$.project.company_id` | 0 | 0 | 0 | 0 | 0 |
| `$.project.company.id` | 0 | 0 | 0 | 0 | 0 |
| `$.company` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_row_cells.currency_iso_code`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `225131`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.currency_iso_code` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_rows.company_id`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2496`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company_id` | 0 | 0 | 0 | 0 | 0 |
| `$.company.id` | 0 | 0 | 0 | 0 | 0 |
| `$.project.company_id` | 0 | 0 | 0 | 0 | 0 |
| `$.project.company.id` | 0 | 0 | 0 | 0 | 0 |
| `$.company` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_rows.cost_type_id`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2496`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_type_id` | 0 | 0 | 0 | 0 | 0 |
| `$.cost_type.id` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_rows.cost_type`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2496`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_type` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_rows.line_item_type_id`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2496`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.line_item_type_id` | 0 | 0 | 0 | 0 | 0 |
| `$.line_item_type.id` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_detail_rows.actual_cost`

- Inferred endpoint: `None`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2496`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `0`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.actual_cost` | 0 | 0 | 0 | 0 | 0 |

### `procore_ep_budget_modifications.company_id`

- Inferred endpoint: `budget-modifications`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `148`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `148`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 148 | 0 | 0 | 148 | 0 |
| `$.company_id` | 148 | 0 | 0 | 148 | 0 |
| `$.project.company.id` | 148 | 0 | 0 | 148 | 0 |
| `$.project.company_id` | 148 | 0 | 0 | 148 | 0 |
| `$.company` | 148 | 0 | 0 | 148 | 0 |

Root keys from first matching payload:

```text
created_at, from_budget_line_item_id, id, notes, origin_data, origin_id, to_budget_line_item_id, transfer_amount, updated_at
```

### `procore_ep_budget_views.company_id`

- Inferred endpoint: `budget-views`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `35`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `35`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 35 | 0 | 0 | 35 | 0 |
| `$.company_id` | 35 | 0 | 0 | 35 | 0 |
| `$.project.company.id` | 35 | 0 | 0 | 35 | 0 |
| `$.project.company_id` | 35 | 0 | 0 | 35 | 0 |
| `$.company` | 35 | 0 | 0 | 35 | 0 |

Root keys from first matching payload:

```text
created_at, created_by, description, id, links, name, role, updated_at
```

### `procore_ep_change_events.event_origin`

- Inferred endpoint: `change-events`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1054`
- DB non-null rows: `5`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.event_origin` | 250 | 250 | 9 | 0 | 5 |
| `$.event_origin.id` | 250 | 0 | 0 | 250 | 0 |
| `$.event_origin.name` | 250 | 0 | 0 | 250 | 0 |
| `$.event_origin.login` | 250 | 0 | 0 | 250 | 0 |
| `$.event_origin.code` | 250 | 0 | 0 | 250 | 0 |
| `$.event_origin.number` | 250 | 0 | 0 | 250 | 0 |
| `$.event_origin.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_commitment_attachments.company_id`

- Inferred endpoint: `commitment-attachments`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `16`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `16`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 16 | 0 | 0 | 16 | 0 |
| `$.company_id` | 16 | 0 | 0 | 16 | 0 |
| `$.project.company.id` | 16 | 0 | 0 | 16 | 0 |
| `$.project.company_id` | 16 | 0 | 0 | 16 | 0 |
| `$.company` | 16 | 0 | 0 | 16 | 0 |

Root keys from first matching payload:

```text
content_type, id, name, url, uuid
```

### `procore_ep_commitment_change_orders.company_id`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 100 | 0 | 0 | 100 | 0 |
| `$.company_id` | 100 | 0 | 0 | 100 | 0 |
| `$.project.company.id` | 100 | 0 | 0 | 100 | 0 |
| `$.project.company_id` | 100 | 0 | 0 | 100 | 0 |
| `$.company` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.change_order_change_reason`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_order_change_reason` | 100 | 100 | 98 | 0 | 5 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.designated_reviewer`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.designated_reviewer` | 100 | 100 | 68 | 0 | 5 |
| `$.designated_reviewer.id` | 100 | 68 | 68 | 32 | 5 |
| `$.designated_reviewer.name` | 100 | 68 | 68 | 32 | 5 |
| `$.designated_reviewer.login` | 100 | 0 | 0 | 100 | 0 |
| `$.designated_reviewer.code` | 100 | 0 | 0 | 100 | 0 |
| `$.designated_reviewer.number` | 100 | 0 | 0 | 100 | 0 |
| `$.designated_reviewer.title` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.received_from`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.received_from` | 100 | 100 | 21 | 0 | 5 |
| `$.received_from.id` | 100 | 21 | 21 | 79 | 5 |
| `$.received_from.name` | 100 | 21 | 21 | 79 | 5 |
| `$.received_from.login` | 100 | 0 | 0 | 100 | 0 |
| `$.received_from.code` | 100 | 0 | 0 | 100 | 0 |
| `$.received_from.number` | 100 | 0 | 0 | 100 | 0 |
| `$.received_from.title` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.reviewed_by`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.reviewed_by` | 100 | 100 | 1 | 0 | 5 |
| `$.reviewed_by.id` | 100 | 1 | 1 | 99 | 1 |
| `$.reviewed_by.name` | 100 | 1 | 1 | 99 | 1 |
| `$.reviewed_by.login` | 100 | 0 | 0 | 100 | 0 |
| `$.reviewed_by.code` | 100 | 0 | 0 | 100 | 0 |
| `$.reviewed_by.number` | 100 | 0 | 0 | 100 | 0 |
| `$.reviewed_by.title` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_compliance.company_id`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance_insurance_documents.company_id`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `58`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.insurance_documents[].company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.insurance_documents[].company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.insurance_documents[].project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance_insurance_documents__52b7bf.company_id`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `105`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.insurance_documents[].attachments[].company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.insurance_documents[].attachments[].company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.insurance_documents[].attachments[].project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_contracts.company_id`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_line_items.company_id`

- Inferred endpoint: `commitment-line-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 63 | 0 | 0 | 63 | 0 |
| `$.company_id` | 63 | 0 | 0 | 63 | 0 |
| `$.project.company.id` | 63 | 0 | 0 | 63 | 0 |
| `$.project.company_id` | 63 | 0 | 0 | 63 | 0 |
| `$.company` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
amount, description, funding_rule_id, id, position, prime_line_item_id, tax_code_id, wbs_code, wbs_code_id
```

### `procore_ep_daily_log_dcrs.company_id`

- Inferred endpoint: `daily-log-dcrs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2628`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
apprentice_hours, attachments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, first_year_hours, foreman_hours, id, journeyman_hours, local_city_hours, local_county_hours, location, minority_hours, notes, number_of_apprentice_workers, number_of_foreman_workers, number_of_journeyman_workers, number_of_other_workers, other_hours, permissions, position, related_items, status, trade, updated_at, vendor, veteran_hours, women_hours
```

### `procore_ep_daily_log_dcrs_attachments.company_id`

- Inferred endpoint: `daily-log-dcrs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `793`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.attachments[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.attachments[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
apprentice_hours, attachments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, first_year_hours, foreman_hours, id, journeyman_hours, local_city_hours, local_county_hours, location, minority_hours, notes, number_of_apprentice_workers, number_of_foreman_workers, number_of_journeyman_workers, number_of_other_workers, other_hours, permissions, position, related_items, status, trade, updated_at, vendor, veteran_hours, women_hours
```

### `procore_ep_daily_log_deliveries.company_id`

- Inferred endpoint: `daily-log-deliveries`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `59`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `59`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 59 | 0 | 0 | 59 | 0 |
| `$.company_id` | 59 | 0 | 0 | 59 | 0 |
| `$.project.company.id` | 59 | 0 | 0 | 59 | 0 |
| `$.project.company_id` | 59 | 0 | 0 | 59 | 0 |
| `$.company` | 59 | 0 | 0 | 59 | 0 |

Root keys from first matching payload:

```text
attachments, comments, contents, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, delivery_from, id, location, permissions, position, related_items, status, time_hour, time_minute, tracking_number, updated_at, vendor
```

### `procore_ep_daily_log_deliveries_attachments.company_id`

- Inferred endpoint: `daily-log-deliveries`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `18`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `59`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 59 | 0 | 0 | 59 | 0 |
| `$.attachments[].company_id` | 59 | 0 | 0 | 59 | 0 |
| `$.attachments[].project.company_id` | 59 | 0 | 0 | 59 | 0 |
| `$.company.id` | 59 | 0 | 0 | 59 | 0 |
| `$.company_id` | 59 | 0 | 0 | 59 | 0 |
| `$.project.company.id` | 59 | 0 | 0 | 59 | 0 |
| `$.project.company_id` | 59 | 0 | 0 | 59 | 0 |
| `$.company` | 59 | 0 | 0 | 59 | 0 |

Root keys from first matching payload:

```text
attachments, comments, contents, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, delivery_from, id, location, permissions, position, related_items, status, time_hour, time_minute, tracking_number, updated_at, vendor
```

### `procore_ep_daily_log_inspections.company_id`

- Inferred endpoint: `daily-log-inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `114`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `114`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 114 | 0 | 0 | 114 | 0 |
| `$.company_id` | 114 | 0 | 0 | 114 | 0 |
| `$.project.company.id` | 114 | 0 | 0 | 114 | 0 |
| `$.project.company_id` | 114 | 0 | 0 | 114 | 0 |
| `$.company` | 114 | 0 | 0 | 114 | 0 |

Root keys from first matching payload:

```text
area, attachments, comments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, end_hour, end_minute, id, inspecting_entity, inspection_type, inspector_name, location, permissions, position, related_items, start_hour, start_minute, status, updated_at, vendor
```

### `procore_ep_daily_log_inspections.location`

- Inferred endpoint: `daily-log-inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `114`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `114`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 114 | 114 | 60 | 0 | 5 |
| `$.location.id` | 114 | 60 | 60 | 54 | 5 |
| `$.location.name` | 114 | 60 | 60 | 54 | 5 |
| `$.location.login` | 114 | 0 | 0 | 114 | 0 |
| `$.location.code` | 114 | 0 | 0 | 114 | 0 |
| `$.location.number` | 114 | 0 | 0 | 114 | 0 |
| `$.location.title` | 114 | 0 | 0 | 114 | 0 |

Root keys from first matching payload:

```text
area, attachments, comments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, end_hour, end_minute, id, inspecting_entity, inspection_type, inspector_name, location, permissions, position, related_items, start_hour, start_minute, status, updated_at, vendor
```

### `procore_ep_daily_log_inspections_attachments.company_id`

- Inferred endpoint: `daily-log-inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `14`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `114`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 114 | 0 | 0 | 114 | 0 |
| `$.attachments[].company_id` | 114 | 0 | 0 | 114 | 0 |
| `$.attachments[].project.company_id` | 114 | 0 | 0 | 114 | 0 |
| `$.company.id` | 114 | 0 | 0 | 114 | 0 |
| `$.company_id` | 114 | 0 | 0 | 114 | 0 |
| `$.project.company.id` | 114 | 0 | 0 | 114 | 0 |
| `$.project.company_id` | 114 | 0 | 0 | 114 | 0 |
| `$.company` | 114 | 0 | 0 | 114 | 0 |

Root keys from first matching payload:

```text
area, attachments, comments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, end_hour, end_minute, id, inspecting_entity, inspection_type, inspector_name, location, permissions, position, related_items, start_hour, start_minute, status, updated_at, vendor
```

### `procore_ep_daily_log_manpower.company_id`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.contact`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.contact` | 250 | 250 | 250 | 0 | 5 |
| `$.contact.id` | 250 | 250 | 250 | 0 | 5 |
| `$.contact.name` | 250 | 250 | 250 | 0 | 5 |
| `$.contact.login` | 250 | 0 | 0 | 250 | 0 |
| `$.contact.code` | 250 | 0 | 0 | 250 | 0 |
| `$.contact.number` | 250 | 0 | 0 | 250 | 0 |
| `$.contact.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.cost_code`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_code` | 250 | 250 | 0 | 0 | 5 |
| `$.cost_code.id` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.name` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.login` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.code` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.number` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.location`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 250 | 250 | 192 | 0 | 5 |
| `$.location.id` | 250 | 192 | 192 | 58 | 5 |
| `$.location.name` | 250 | 192 | 192 | 58 | 5 |
| `$.location.login` | 250 | 0 | 0 | 250 | 0 |
| `$.location.code` | 250 | 0 | 0 | 250 | 0 |
| `$.location.number` | 250 | 0 | 0 | 250 | 0 |
| `$.location.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower_attachments.company_id`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `781`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.attachments[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.attachments[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_notes.company_id`

- Inferred endpoint: `daily-log-notes`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `92`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `92`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 92 | 0 | 0 | 92 | 0 |
| `$.company_id` | 92 | 0 | 0 | 92 | 0 |
| `$.project.company.id` | 92 | 0 | 0 | 92 | 0 |
| `$.project.company_id` | 92 | 0 | 0 | 92 | 0 |
| `$.company` | 92 | 0 | 0 | 92 | 0 |

Root keys from first matching payload:

```text
attachments, comment, created_at, created_by, created_by_collaborator, custom_fields, daily_log_header_id, date, datetime, deleted_at, id, is_issue_day, location, permissions, position, related_items, status, updated_at, vendor
```

### `procore_ep_daily_log_notes.location`

- Inferred endpoint: `daily-log-notes`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `92`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `92`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 92 | 92 | 26 | 0 | 5 |
| `$.location.id` | 92 | 26 | 26 | 66 | 5 |
| `$.location.name` | 92 | 26 | 26 | 66 | 5 |
| `$.location.login` | 92 | 0 | 0 | 92 | 0 |
| `$.location.code` | 92 | 0 | 0 | 92 | 0 |
| `$.location.number` | 92 | 0 | 0 | 92 | 0 |
| `$.location.title` | 92 | 0 | 0 | 92 | 0 |

Root keys from first matching payload:

```text
attachments, comment, created_at, created_by, created_by_collaborator, custom_fields, daily_log_header_id, date, datetime, deleted_at, id, is_issue_day, location, permissions, position, related_items, status, updated_at, vendor
```

### `procore_ep_daily_log_notes_attachments.company_id`

- Inferred endpoint: `daily-log-notes`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1188`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `92`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 92 | 0 | 0 | 92 | 0 |
| `$.attachments[].company_id` | 92 | 0 | 0 | 92 | 0 |
| `$.attachments[].project.company_id` | 92 | 0 | 0 | 92 | 0 |
| `$.company.id` | 92 | 0 | 0 | 92 | 0 |
| `$.company_id` | 92 | 0 | 0 | 92 | 0 |
| `$.project.company.id` | 92 | 0 | 0 | 92 | 0 |
| `$.project.company_id` | 92 | 0 | 0 | 92 | 0 |
| `$.company` | 92 | 0 | 0 | 92 | 0 |

Root keys from first matching payload:

```text
attachments, comment, created_at, created_by, created_by_collaborator, custom_fields, daily_log_header_id, date, datetime, deleted_at, id, is_issue_day, location, permissions, position, related_items, status, updated_at, vendor
```

### `procore_ep_daily_log_visitor.company_id`

- Inferred endpoint: `daily-log-visitor`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `2`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 2 | 0 | 0 | 2 | 0 |
| `$.company_id` | 2 | 0 | 0 | 2 | 0 |
| `$.project.company.id` | 2 | 0 | 0 | 2 | 0 |
| `$.project.company_id` | 2 | 0 | 0 | 2 | 0 |
| `$.company` | 2 | 0 | 0 | 2 | 0 |

Root keys from first matching payload:

```text
attachments, begin_hour, begin_minute, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, details, end_hour, end_minute, id, location, permissions, position, related_items, status, subject, updated_at, vendor
```

### `procore_ep_daily_log_weather.company_id`

- Inferred endpoint: `daily-log-weather`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `130`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `130`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 130 | 0 | 0 | 130 | 0 |
| `$.company_id` | 130 | 0 | 0 | 130 | 0 |
| `$.project.company.id` | 130 | 0 | 0 | 130 | 0 |
| `$.project.company_id` | 130 | 0 | 0 | 130 | 0 |
| `$.company` | 130 | 0 | 0 | 130 | 0 |

Root keys from first matching payload:

```text
attachments, average, calamity, comments, created_at, created_by, created_by_collaborator, custom_fields, daily_log_segment, daily_log_segment_id, date, datetime, deleted_at, ground, id, is_weather_delay, location, permissions, position, precipitation, sky, status, temperature, time, time_hour, time_minute, updated_at, vendor, wind
```

### `procore_ep_inspection_items.company_id`

- Inferred endpoint: `inspection-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `3363`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
company_template_item_details, details, display_conditions, evidence_configuration, id, item_reference_ids, item_response, list_id, name, number, parent_item_id, position, relative_position, responded_with, response, response_set, section_id, signature_request_ids, status, template_item_id, type, updated_at
```

### `procore_ep_inspection_items.item_response`

- Inferred endpoint: `inspection-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `3363`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.item_response` | 250 | 250 | 185 | 0 | 5 |

Root keys from first matching payload:

```text
company_template_item_details, details, display_conditions, evidence_configuration, id, item_reference_ids, item_response, list_id, name, number, parent_item_id, position, relative_position, responded_with, response, response_set, section_id, signature_request_ids, status, template_item_id, type, updated_at
```

### `procore_ep_inspection_items.response`

- Inferred endpoint: `inspection-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `3363`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.response` | 250 | 250 | 185 | 0 | 5 |

Root keys from first matching payload:

```text
company_template_item_details, details, display_conditions, evidence_configuration, id, item_reference_ids, item_response, list_id, name, number, parent_item_id, position, relative_position, responded_with, response, response_set, section_id, signature_request_ids, status, template_item_id, type, updated_at
```

### `procore_ep_inspection_items.response_set`

- Inferred endpoint: `inspection-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `3363`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.response_set` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
company_template_item_details, details, display_conditions, evidence_configuration, id, item_reference_ids, item_response, list_id, name, number, parent_item_id, position, relative_position, responded_with, response, response_set, section_id, signature_request_ids, status, template_item_id, type, updated_at
```

### `procore_ep_inspection_items_response_set_responses.company_id`

- Inferred endpoint: `inspection-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10068`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.response_set.responses[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.response_set.responses[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.response_set.responses[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
company_template_item_details, details, display_conditions, evidence_configuration, id, item_reference_ids, item_response, list_id, name, number, parent_item_id, position, relative_position, responded_with, response, response_set, section_id, signature_request_ids, status, template_item_id, type, updated_at
```

### `procore_ep_inspection_sections.company_id`

- Inferred endpoint: `inspection-sections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `139`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `139`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 139 | 0 | 0 | 139 | 0 |
| `$.company_id` | 139 | 0 | 0 | 139 | 0 |
| `$.project.company.id` | 139 | 0 | 0 | 139 | 0 |
| `$.project.company_id` | 139 | 0 | 0 | 139 | 0 |
| `$.company` | 139 | 0 | 0 | 139 | 0 |

Root keys from first matching payload:

```text
id, name, position, template_section_id, updated_at
```

### `procore_ep_inspections.company_id`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.company` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections.closed_by`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_by` | 74 | 74 | 11 | 0 | 5 |
| `$.closed_by.id` | 74 | 11 | 11 | 63 | 5 |
| `$.closed_by.name` | 74 | 11 | 11 | 63 | 5 |
| `$.closed_by.login` | 74 | 11 | 11 | 63 | 5 |
| `$.closed_by.code` | 74 | 0 | 0 | 74 | 0 |
| `$.closed_by.number` | 74 | 0 | 0 | 74 | 0 |
| `$.closed_by.title` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections.location`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 74 | 74 | 60 | 0 | 5 |
| `$.location.id` | 74 | 60 | 60 | 14 | 5 |
| `$.location.name` | 74 | 60 | 60 | 14 | 5 |
| `$.location.login` | 74 | 0 | 0 | 74 | 0 |
| `$.location.code` | 74 | 60 | 0 | 14 | 5 |
| `$.location.number` | 74 | 0 | 0 | 74 | 0 |
| `$.location.title` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections.point_of_contact`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.point_of_contact` | 74 | 74 | 7 | 0 | 5 |
| `$.point_of_contact.id` | 74 | 7 | 7 | 67 | 5 |
| `$.point_of_contact.name` | 74 | 7 | 7 | 67 | 5 |
| `$.point_of_contact.login` | 74 | 7 | 7 | 67 | 5 |
| `$.point_of_contact.code` | 74 | 0 | 0 | 74 | 0 |
| `$.point_of_contact.number` | 74 | 0 | 0 | 74 | 0 |
| `$.point_of_contact.title` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections.responsible_contractor`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.responsible_contractor` | 74 | 74 | 9 | 0 | 5 |
| `$.responsible_contractor.id` | 74 | 9 | 9 | 65 | 5 |
| `$.responsible_contractor.name` | 74 | 9 | 9 | 65 | 5 |
| `$.responsible_contractor.login` | 74 | 0 | 0 | 74 | 0 |
| `$.responsible_contractor.code` | 74 | 0 | 0 | 74 | 0 |
| `$.responsible_contractor.number` | 74 | 0 | 0 | 74 | 0 |
| `$.responsible_contractor.title` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections.specification_section`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.specification_section` | 74 | 74 | 2 | 0 | 5 |
| `$.specification_section.id` | 74 | 2 | 2 | 72 | 2 |
| `$.specification_section.name` | 74 | 0 | 0 | 74 | 0 |
| `$.specification_section.login` | 74 | 0 | 0 | 74 | 0 |
| `$.specification_section.code` | 74 | 0 | 0 | 74 | 0 |
| `$.specification_section.number` | 74 | 0 | 0 | 74 | 0 |
| `$.specification_section.title` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections.trade`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `74`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.trade` | 74 | 74 | 10 | 0 | 5 |
| `$.trade.id` | 74 | 10 | 10 | 64 | 5 |
| `$.trade.name` | 74 | 10 | 10 | 64 | 5 |
| `$.trade.login` | 74 | 0 | 0 | 74 | 0 |
| `$.trade.code` | 74 | 0 | 0 | 74 | 0 |
| `$.trade.number` | 74 | 0 | 0 | 74 | 0 |
| `$.trade.title` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections_attachments.company_id`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `363`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.attachments[].company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.attachments[].project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.company` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections_distribution_members.company_id`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `213`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.distribution_members[].company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.distribution_members[].company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.distribution_members[].project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.company` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections_inspectors.company_id`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `101`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.inspectors[].company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.inspectors[].company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.inspectors[].project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.company` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections_signature_requests.company_id`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `8`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.signature_requests[].company.id` | 74 | 0 | 0 | 74 | 0 |
| `$.signature_requests[].company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.signature_requests[].project.company_id` | 74 | 0 | 0 | 74 | 0 |
| `$.company` | 74 | 0 | 0 | 74 | 0 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_inspections_signature_requests.signature`

- Inferred endpoint: `inspections`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `8`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `74`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.signature` | 74 | 0 | 0 | 74 | 0 |
| `$.signature_requests[].signature` | 74 | 8 | 4 | 66 | 5 |

Root keys from first matching payload:

```text
asset_ids, attachments, closed_at, closed_by, closed_observations_count, conforming_item_count, created_at, created_by, current_drawing_revision_ids, custom_fields, default_response_phrasing, deficient_item_count, deleted, description, distribution_members, drawing_ids, due_at, equipment, equipment_id, id, identifier, inspected_item_count, inspection_date, inspection_type, inspectors, item_count, list_template_id, list_template_name, location, managed_equipment_id, name, neutral_item_count, not_applicable_item_count, number, observations_count, overdue, point_of_contact, private, reinspected_by_id, reinspected_from_id, respondable_item_count, responsible_contractor, schedule, signature_requests, specification_section, status, template_id, trade, updated_at
```

### `procore_ep_meetings.company_id`

- Inferred endpoint: `meetings`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `97`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `97`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 97 | 0 | 0 | 97 | 0 |
| `$.company_id` | 97 | 0 | 0 | 97 | 0 |
| `$.project.company.id` | 97 | 0 | 0 | 97 | 0 |
| `$.project.company_id` | 97 | 0 | 0 | 97 | 0 |
| `$.company` | 97 | 0 | 0 | 97 | 0 |

Root keys from first matching payload:

```text
created_at, created_by_id, description, distributed_at, distributed_by, ends_at, id, is_private, last_distributed_event, location, meeting_template_id, meeting_topics_count, mode, occurred, parent_id, position, starts_at, title, updated_at
```

### `procore_ep_meetings.distributed_by`

- Inferred endpoint: `meetings`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `97`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `97`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.distributed_by` | 97 | 97 | 81 | 0 | 5 |
| `$.distributed_by.id` | 97 | 81 | 81 | 16 | 5 |
| `$.distributed_by.name` | 97 | 81 | 81 | 16 | 5 |
| `$.distributed_by.login` | 97 | 81 | 81 | 16 | 5 |
| `$.distributed_by.code` | 97 | 0 | 0 | 97 | 0 |
| `$.distributed_by.number` | 97 | 0 | 0 | 97 | 0 |
| `$.distributed_by.title` | 97 | 0 | 0 | 97 | 0 |

Root keys from first matching payload:

```text
created_at, created_by_id, description, distributed_at, distributed_by, ends_at, id, is_private, last_distributed_event, location, meeting_template_id, meeting_topics_count, mode, occurred, parent_id, position, starts_at, title, updated_at
```

### `procore_ep_observations.company_id`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 215 | 0 | 0 | 215 | 0 |
| `$.company_id` | 215 | 0 | 0 | 215 | 0 |
| `$.project.company.id` | 215 | 0 | 0 | 215 | 0 |
| `$.project.company_id` | 215 | 0 | 0 | 215 | 0 |
| `$.company` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations.assignee`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignee` | 215 | 215 | 209 | 0 | 5 |
| `$.assignee.id` | 215 | 209 | 209 | 6 | 5 |
| `$.assignee.name` | 215 | 209 | 209 | 6 | 5 |
| `$.assignee.login` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee.code` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee.number` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations.assignee_vendor`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignee.vendor` | 215 | 209 | 207 | 6 | 5 |
| `$.assignee_vendor` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee_vendor.id` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee_vendor.name` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee_vendor.login` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee_vendor.code` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee_vendor.number` | 215 | 0 | 0 | 215 | 0 |
| `$.assignee_vendor.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations.location`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 215 | 215 | 145 | 0 | 5 |
| `$.location.id` | 215 | 145 | 145 | 70 | 5 |
| `$.location.name` | 215 | 145 | 145 | 70 | 5 |
| `$.location.login` | 215 | 0 | 0 | 215 | 0 |
| `$.location.code` | 215 | 0 | 0 | 215 | 0 |
| `$.location.number` | 215 | 0 | 0 | 215 | 0 |
| `$.location.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations.origin`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.origin` | 215 | 215 | 1 | 0 | 5 |
| `$.origin.id` | 215 | 0 | 0 | 215 | 0 |
| `$.origin.name` | 215 | 0 | 0 | 215 | 0 |
| `$.origin.login` | 215 | 0 | 0 | 215 | 0 |
| `$.origin.code` | 215 | 0 | 0 | 215 | 0 |
| `$.origin.number` | 215 | 0 | 0 | 215 | 0 |
| `$.origin.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations.specification_section`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.specification_section` | 215 | 215 | 9 | 0 | 5 |
| `$.specification_section.id` | 215 | 9 | 9 | 206 | 5 |
| `$.specification_section.name` | 215 | 0 | 0 | 215 | 0 |
| `$.specification_section.login` | 215 | 0 | 0 | 215 | 0 |
| `$.specification_section.code` | 215 | 0 | 0 | 215 | 0 |
| `$.specification_section.number` | 215 | 9 | 9 | 206 | 5 |
| `$.specification_section.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations.trade`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `215`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.trade` | 215 | 215 | 161 | 0 | 5 |
| `$.trade.id` | 215 | 161 | 161 | 54 | 5 |
| `$.trade.name` | 215 | 161 | 161 | 54 | 5 |
| `$.trade.login` | 215 | 0 | 0 | 215 | 0 |
| `$.trade.code` | 215 | 0 | 0 | 215 | 0 |
| `$.trade.number` | 215 | 0 | 0 | 215 | 0 |
| `$.trade.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations_assignees.company_id`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignees[].company.id` | 215 | 0 | 0 | 215 | 0 |
| `$.assignees[].company_id` | 215 | 0 | 0 | 215 | 0 |
| `$.assignees[].project.company_id` | 215 | 0 | 0 | 215 | 0 |
| `$.company.id` | 215 | 0 | 0 | 215 | 0 |
| `$.company_id` | 215 | 0 | 0 | 215 | 0 |
| `$.project.company.id` | 215 | 0 | 0 | 215 | 0 |
| `$.project.company_id` | 215 | 0 | 0 | 215 | 0 |
| `$.company` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_observations_assignees.vendor`

- Inferred endpoint: `observations`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `215`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignee.vendor` | 215 | 209 | 207 | 6 | 5 |
| `$.assignees[].vendor` | 215 | 7 | 5 | 208 | 5 |
| `$.vendor` | 215 | 0 | 0 | 215 | 0 |
| `$.vendor.id` | 215 | 0 | 0 | 215 | 0 |
| `$.vendor.name` | 215 | 0 | 0 | 215 | 0 |
| `$.vendor.login` | 215 | 0 | 0 | 215 | 0 |
| `$.vendor.code` | 215 | 0 | 0 | 215 | 0 |
| `$.vendor.number` | 215 | 0 | 0 | 215 | 0 |
| `$.vendor.title` | 215 | 0 | 0 | 215 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, category, closed_at, created_at, created_by, custom_fields, date_notified, deleted_at, description, description_rich_text, due_date, id, location, name, number, origin, permissions, personal, priority, specification_section, status, trade, type, updated_at
```

### `procore_ep_prime_change_order_line_items.company_id`

- Inferred endpoint: `prime-change-order-line-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `2`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 2 | 0 | 0 | 2 | 0 |
| `$.company_id` | 2 | 0 | 0 | 2 | 0 |
| `$.project.company.id` | 2 | 0 | 0 | 2 | 0 |
| `$.project.company_id` | 2 | 0 | 0 | 2 | 0 |
| `$.company` | 2 | 0 | 0 | 2 | 0 |

Root keys from first matching payload:

```text
amount, description, extended_type, funding_rule_id, id, position, prime_line_item_id, quantity, tax_code_id, unit_cost, wbs_code, wbs_code_id
```

### `procore_ep_prime_change_orders.company_id`

- Inferred endpoint: `prime-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 63 | 0 | 0 | 63 | 0 |
| `$.company_id` | 63 | 0 | 0 | 63 | 0 |
| `$.project.company.id` | 63 | 0 | 0 | 63 | 0 |
| `$.project.company_id` | 63 | 0 | 0 | 63 | 0 |
| `$.company` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revised_substantial_completion_date, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_prime_change_orders.change_order_change_reason`

- Inferred endpoint: `prime-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_order_change_reason` | 63 | 63 | 60 | 0 | 5 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revised_substantial_completion_date, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_prime_change_orders.designated_reviewer`

- Inferred endpoint: `prime-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.designated_reviewer` | 63 | 63 | 19 | 0 | 5 |
| `$.designated_reviewer.id` | 63 | 19 | 19 | 44 | 5 |
| `$.designated_reviewer.name` | 63 | 19 | 19 | 44 | 5 |
| `$.designated_reviewer.login` | 63 | 0 | 0 | 63 | 0 |
| `$.designated_reviewer.code` | 63 | 0 | 0 | 63 | 0 |
| `$.designated_reviewer.number` | 63 | 0 | 0 | 63 | 0 |
| `$.designated_reviewer.title` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revised_substantial_completion_date, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_prime_change_orders.received_from`

- Inferred endpoint: `prime-change-orders`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.received_from` | 63 | 63 | 36 | 0 | 5 |
| `$.received_from.id` | 63 | 36 | 36 | 27 | 5 |
| `$.received_from.name` | 63 | 36 | 36 | 27 | 5 |
| `$.received_from.login` | 63 | 0 | 0 | 63 | 0 |
| `$.received_from.code` | 63 | 0 | 0 | 63 | 0 |
| `$.received_from.number` | 63 | 0 | 0 | 63 | 0 |
| `$.received_from.title` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revised_substantial_completion_date, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_prime_contract_line_items.company_id`

- Inferred endpoint: `prime-contract-line-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `47`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `47`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 47 | 0 | 0 | 47 | 0 |
| `$.company_id` | 47 | 0 | 0 | 47 | 0 |
| `$.project.company.id` | 47 | 0 | 0 | 47 | 0 |
| `$.project.company_id` | 47 | 0 | 0 | 47 | 0 |
| `$.company` | 47 | 0 | 0 | 47 | 0 |

Root keys from first matching payload:

```text
amount, description, funding_rule_id, id, line_item_group_id, position, tax_code_id, wbs_code, wbs_code_id
```

### `procore_ep_prime_contracts.company_id`

- Inferred endpoint: `prime-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `6`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `15`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 15 | 0 | 0 | 15 | 0 |
| `$.company_id` | 15 | 0 | 0 | 15 | 0 |
| `$.project.company.id` | 15 | 0 | 0 | 15 | 0 |
| `$.project.company_id` | 15 | 0 | 0 | 15 | 0 |
| `$.company` | 15 | 0 | 0 | 15 | 0 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, approval_letter_date, approved_change_orders, architect, attachments, contract_date, contract_estimated_completion_date, contract_start_date, contract_termination_date, contractor, created_at, created_by, currency_configuration, custom_fields, deleted_at, description, draft_change_orders_amount, exclusions, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, inclusions, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, original_substantial_completion_date, outstanding_balance, owner_invoices_amount, pending_change_orders_amount, pending_revised_contract_amount, percentage_paid, private, retainage_percent, returned_date, revised_contract_amount, show_line_items_to_non_admins, signed_contract_received_date, status, substantial_completion_date, title, total_payments, updated_at, vendor
```

### `procore_ep_projects.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `14`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects.project_stage`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `14`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.project_stage` | 14 | 14 | 12 | 0 | 5 |
| `$.project_stage.id` | 14 | 12 | 12 | 2 | 5 |
| `$.project_stage.name` | 14 | 12 | 12 | 2 | 5 |
| `$.project_stage.login` | 14 | 0 | 0 | 14 | 0 |
| `$.project_stage.code` | 14 | 0 | 0 | 14 | 0 |
| `$.project_stage.number` | 14 | 0 | 0 | 14 | 0 |
| `$.project_stage.title` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163287_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163287.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163287.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163287.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163290_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `6`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163290.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163290.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163290.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163293_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `4`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163293.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163293.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163293.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163296_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163296.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163296.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163296.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163299_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163299.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163299.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163299.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163302_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163302.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163302.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163302.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_projects_custom_fields_custom_field_163305_value.company_id`

- Inferred endpoint: `projects`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `2`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `14`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 14 | 14 | 14 | 0 | 5 |
| `$.company.id` | 14 | 14 | 14 | 0 | 5 |
| `$.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163305.value[].company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163305.value[].company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.custom_fields.custom_field_163305.value[].project.company_id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company.id` | 14 | 0 | 0 | 14 | 0 |
| `$.project.company_id` | 14 | 0 | 0 | 14 | 0 |

Root keys from first matching payload:

```text
accounting_project_number, active, address, city, company, completion_date, country_code, county, created_at, created_by, custom_fields, delivery_method, designated_market_area, display_name, estimated_value, id, is_demo, latitude, longitude, name, origin_code, origin_data, origin_id, owners_project_id, parent_job, parent_job_id, phone, photo_id, project_bid_type_id, project_number, project_owner_type_id, project_region_id, project_sector_id, project_stage, project_template, projected_finish_date, sector, stage, start_date, state_code, store_number, time_zone, total_value, updated_at, work_scope, zip
```

### `procore_ep_punch_items.company_id`

- Inferred endpoint: `punch-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `36`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `36`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company` | 36 | 0 | 0 | 36 | 0 |

Root keys from first matching payload:

```text
assignees, assignments, ball_in_court, closed_at, closed_by, cost_code, cost_impact, cost_impact_amount, created_at, created_by, custom_fields, deleted_at, description, due_date, due_tomorrow, final_approver, flagged_by, has_attachments, has_resolved_responses, has_unresolved_responses, id, location, manager_notified_at, name, overdue, position, priority, private, punch_item_manager, punch_item_type, reference, schedule_impact, schedule_impact_days, schedule_risk, schedule_risk_reason, should_display_risk_flag, status, trade, updated_at, workflow_status
```

### `procore_ep_punch_items_assignees.company_id`

- Inferred endpoint: `punch-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `48`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `36`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignees[].company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.assignees[].company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.assignees[].project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company` | 36 | 0 | 0 | 36 | 0 |

Root keys from first matching payload:

```text
assignees, assignments, ball_in_court, closed_at, closed_by, cost_code, cost_impact, cost_impact_amount, created_at, created_by, custom_fields, deleted_at, description, due_date, due_tomorrow, final_approver, flagged_by, has_attachments, has_resolved_responses, has_unresolved_responses, id, location, manager_notified_at, name, overdue, position, priority, private, punch_item_manager, punch_item_type, reference, schedule_impact, schedule_impact_days, schedule_risk, schedule_risk_reason, should_display_risk_flag, status, trade, updated_at, workflow_status
```

### `procore_ep_punch_items_assignments.company_id`

- Inferred endpoint: `punch-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `48`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `36`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignments[].company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.assignments[].company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.assignments[].project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company` | 36 | 0 | 0 | 36 | 0 |

Root keys from first matching payload:

```text
assignees, assignments, ball_in_court, closed_at, closed_by, cost_code, cost_impact, cost_impact_amount, created_at, created_by, custom_fields, deleted_at, description, due_date, due_tomorrow, final_approver, flagged_by, has_attachments, has_resolved_responses, has_unresolved_responses, id, location, manager_notified_at, name, overdue, position, priority, private, punch_item_manager, punch_item_type, reference, schedule_impact, schedule_impact_days, schedule_risk, schedule_risk_reason, should_display_risk_flag, status, trade, updated_at, workflow_status
```

### `procore_ep_punch_items_ball_in_court.company_id`

- Inferred endpoint: `punch-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `23`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `36`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.ball_in_court[].company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.ball_in_court[].company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.ball_in_court[].project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company.id` | 36 | 0 | 0 | 36 | 0 |
| `$.project.company_id` | 36 | 0 | 0 | 36 | 0 |
| `$.company` | 36 | 0 | 0 | 36 | 0 |

Root keys from first matching payload:

```text
assignees, assignments, ball_in_court, closed_at, closed_by, cost_code, cost_impact, cost_impact_amount, created_at, created_by, custom_fields, deleted_at, description, due_date, due_tomorrow, final_approver, flagged_by, has_attachments, has_resolved_responses, has_unresolved_responses, id, location, manager_notified_at, name, overdue, position, priority, private, punch_item_manager, punch_item_type, reference, schedule_impact, schedule_impact_days, schedule_risk, schedule_risk_reason, should_display_risk_flag, status, trade, updated_at, workflow_status
```

### `procore_ep_purchase_order_contracts.company_id`

- Inferred endpoint: `purchase-order-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `10`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 10 | 0 | 0 | 10 | 0 |
| `$.company_id` | 10 | 0 | 0 | 10 | 0 |
| `$.project.company.id` | 10 | 0 | 0 | 10 | 0 |
| `$.project.company_id` | 10 | 0 | 0 | 10 | 0 |
| `$.company` | 10 | 0 | 0 | 10 | 0 |

Root keys from first matching payload:

```text
accounting_method, allow_change_orders_ssov, approval_letter_date, approved_change_orders, assignee, bill_to_address, billing_schedule_of_values_status, contract_date, created_at, created_by_id, currency_configuration, custom_fields, deleted_at, delivery_date, description, draft_change_orders_amount, enable_ssov, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, payment_terms, pending_change_orders, pending_revised_contract, percentage_paid, private, project, remaining_balance_outstanding, requisitions_are_enabled, retainage_percent, returned_date, revised_contract, ship_to_address, ship_via, show_line_items_to_non_admins, signed_contract_received_date, status, title, total_draw_requests_amount, total_payments, total_requisitions_amount, updated_at, vendor
```

### `procore_ep_purchase_order_contracts.assignee`

- Inferred endpoint: `purchase-order-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `10`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignee` | 10 | 10 | 5 | 0 | 5 |
| `$.assignee.id` | 10 | 5 | 5 | 5 | 5 |
| `$.assignee.name` | 10 | 0 | 0 | 10 | 0 |
| `$.assignee.login` | 10 | 0 | 0 | 10 | 0 |
| `$.assignee.code` | 10 | 0 | 0 | 10 | 0 |
| `$.assignee.number` | 10 | 0 | 0 | 10 | 0 |
| `$.assignee.title` | 10 | 0 | 0 | 10 | 0 |

Root keys from first matching payload:

```text
accounting_method, allow_change_orders_ssov, approval_letter_date, approved_change_orders, assignee, bill_to_address, billing_schedule_of_values_status, contract_date, created_at, created_by_id, currency_configuration, custom_fields, deleted_at, delivery_date, description, draft_change_orders_amount, enable_ssov, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, payment_terms, pending_change_orders, pending_revised_contract, percentage_paid, private, project, remaining_balance_outstanding, requisitions_are_enabled, retainage_percent, returned_date, revised_contract, ship_to_address, ship_via, show_line_items_to_non_admins, signed_contract_received_date, status, title, total_draw_requests_amount, total_payments, total_requisitions_amount, updated_at, vendor
```

### `procore_ep_purchase_order_contracts.custom_fields_custom_field_214072_value`

- Inferred endpoint: `purchase-order-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `10`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.custom_fields.custom_field_214072.value` | 10 | 10 | 8 | 0 | 5 |
| `$.custom_fields_custom_field_214072_value` | 10 | 0 | 0 | 10 | 0 |

Root keys from first matching payload:

```text
accounting_method, allow_change_orders_ssov, approval_letter_date, approved_change_orders, assignee, bill_to_address, billing_schedule_of_values_status, contract_date, created_at, created_by_id, currency_configuration, custom_fields, deleted_at, delivery_date, description, draft_change_orders_amount, enable_ssov, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, payment_terms, pending_change_orders, pending_revised_contract, percentage_paid, private, project, remaining_balance_outstanding, requisitions_are_enabled, retainage_percent, returned_date, revised_contract, ship_to_address, ship_via, show_line_items_to_non_admins, signed_contract_received_date, status, title, total_draw_requests_amount, total_payments, total_requisitions_amount, updated_at, vendor
```

### `procore_ep_purchase_order_contracts.custom_fields_custom_field_214078_value`

- Inferred endpoint: `purchase-order-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `10`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.custom_fields.custom_field_214078.value` | 10 | 10 | 8 | 0 | 5 |
| `$.custom_fields_custom_field_214078_value` | 10 | 0 | 0 | 10 | 0 |

Root keys from first matching payload:

```text
accounting_method, allow_change_orders_ssov, approval_letter_date, approved_change_orders, assignee, bill_to_address, billing_schedule_of_values_status, contract_date, created_at, created_by_id, currency_configuration, custom_fields, deleted_at, delivery_date, description, draft_change_orders_amount, enable_ssov, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, payment_terms, pending_change_orders, pending_revised_contract, percentage_paid, private, project, remaining_balance_outstanding, requisitions_are_enabled, retainage_percent, returned_date, revised_contract, ship_to_address, ship_via, show_line_items_to_non_admins, signed_contract_received_date, status, title, total_draw_requests_amount, total_payments, total_requisitions_amount, updated_at, vendor
```

### `procore_ep_purchase_order_contracts.custom_fields_custom_field_214087_value`

- Inferred endpoint: `purchase-order-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `10`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `10`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.custom_fields.custom_field_214087.value` | 10 | 10 | 8 | 0 | 5 |
| `$.custom_fields_custom_field_214087_value` | 10 | 0 | 0 | 10 | 0 |

Root keys from first matching payload:

```text
accounting_method, allow_change_orders_ssov, approval_letter_date, approved_change_orders, assignee, bill_to_address, billing_schedule_of_values_status, contract_date, created_at, created_by_id, currency_configuration, custom_fields, deleted_at, delivery_date, description, draft_change_orders_amount, enable_ssov, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, payment_terms, pending_change_orders, pending_revised_contract, percentage_paid, private, project, remaining_balance_outstanding, requisitions_are_enabled, retainage_percent, returned_date, revised_contract, ship_to_address, ship_via, show_line_items_to_non_admins, signed_contract_received_date, status, title, total_draw_requests_amount, total_payments, total_requisitions_amount, updated_at, vendor
```

### `procore_ep_purchase_order_contracts_custom_fields_cus_a0fe65.company_id`

- Inferred endpoint: `purchase-order-contracts`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `10`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 10 | 0 | 0 | 10 | 0 |
| `$.company_id` | 10 | 0 | 0 | 10 | 0 |
| `$.custom_fields.custom_field_214094.value[].company.id` | 10 | 0 | 0 | 10 | 0 |
| `$.custom_fields.custom_field_214094.value[].company_id` | 10 | 0 | 0 | 10 | 0 |
| `$.custom_fields.custom_field_214094.value[].project.company_id` | 10 | 0 | 0 | 10 | 0 |
| `$.project.company.id` | 10 | 0 | 0 | 10 | 0 |
| `$.project.company_id` | 10 | 0 | 0 | 10 | 0 |
| `$.company` | 10 | 0 | 0 | 10 | 0 |

Root keys from first matching payload:

```text
accounting_method, allow_change_orders_ssov, approval_letter_date, approved_change_orders, assignee, bill_to_address, billing_schedule_of_values_status, contract_date, created_at, created_by_id, currency_configuration, custom_fields, deleted_at, delivery_date, description, draft_change_orders_amount, enable_ssov, executed, execution_date, grand_total, has_change_order_packages, has_potential_change_orders, id, issued_on_date, letter_of_intent_date, number, origin_code, origin_data, origin_id, payment_terms, pending_change_orders, pending_revised_contract, percentage_paid, private, project, remaining_balance_outstanding, requisitions_are_enabled, retainage_percent, returned_date, revised_contract, ship_to_address, ship_via, show_line_items_to_non_admins, signed_contract_received_date, status, title, total_draw_requests_amount, total_payments, total_requisitions_amount, updated_at, vendor
```

### `procore_ep_purchase_order_line_items.company_id`

- Inferred endpoint: `purchase-order-line-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `12`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `12`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 12 | 12 | 12 | 0 | 5 |
| `$.company.id` | 12 | 12 | 12 | 0 | 5 |
| `$.company_id` | 12 | 0 | 0 | 12 | 0 |
| `$.project.company.id` | 12 | 0 | 0 | 12 | 0 |
| `$.project.company_id` | 12 | 0 | 0 | 12 | 0 |

Root keys from first matching payload:

```text
amount, company, cost_code, created_at, currency_configuration, description, extended_amount, extended_type, holder, id, line_item_type, origin_id, position, project, quantity, total_amount, unit_cost, updated_at, wbs_code
```

### `procore_ep_purchase_order_line_items_cost_code_line_i_779dbd.company_id`

- Inferred endpoint: `purchase-order-line-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `24`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `12`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company` | 12 | 12 | 12 | 0 | 5 |
| `$.company.id` | 12 | 12 | 12 | 0 | 5 |
| `$.company_id` | 12 | 0 | 0 | 12 | 0 |
| `$.cost_code.line_item_types[].company.id` | 12 | 0 | 0 | 12 | 0 |
| `$.cost_code.line_item_types[].company_id` | 12 | 0 | 0 | 12 | 0 |
| `$.cost_code.line_item_types[].project.company_id` | 12 | 0 | 0 | 12 | 0 |
| `$.project.company.id` | 12 | 0 | 0 | 12 | 0 |
| `$.project.company_id` | 12 | 0 | 0 | 12 | 0 |

Root keys from first matching payload:

```text
amount, company, cost_code, created_at, currency_configuration, description, extended_amount, extended_type, holder, id, line_item_type, origin_id, position, project, quantity, total_amount, unit_cost, updated_at, wbs_code
```

### `procore_ep_rfis.company_id`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1967`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis.ball_in_court`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1967`
- DB non-null rows: `54`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.ball_in_court` | 250 | 250 | 19 | 0 | 5 |
| `$.ball_in_court.id` | 250 | 19 | 19 | 231 | 5 |
| `$.ball_in_court.name` | 250 | 19 | 19 | 231 | 5 |
| `$.ball_in_court.login` | 250 | 19 | 19 | 231 | 5 |
| `$.ball_in_court.code` | 250 | 0 | 0 | 250 | 0 |
| `$.ball_in_court.number` | 250 | 0 | 0 | 250 | 0 |
| `$.ball_in_court.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis.cost_code`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1967`
- DB non-null rows: `30`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_code` | 250 | 250 | 6 | 0 | 5 |
| `$.cost_code.id` | 250 | 6 | 6 | 244 | 5 |
| `$.cost_code.name` | 250 | 6 | 6 | 244 | 5 |
| `$.cost_code.login` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.code` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.number` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis.location`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1967`
- DB non-null rows: `76`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 250 | 250 | 29 | 0 | 5 |
| `$.location.id` | 250 | 29 | 29 | 221 | 5 |
| `$.location.name` | 250 | 29 | 29 | 221 | 5 |
| `$.location.login` | 250 | 0 | 0 | 250 | 0 |
| `$.location.code` | 250 | 0 | 0 | 250 | 0 |
| `$.location.number` | 250 | 0 | 0 | 250 | 0 |
| `$.location.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis.sub_job`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1967`
- DB non-null rows: `63`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.sub_job` | 250 | 250 | 14 | 0 | 5 |
| `$.sub_job.id` | 250 | 14 | 14 | 236 | 5 |
| `$.sub_job.name` | 250 | 14 | 14 | 236 | 5 |
| `$.sub_job.login` | 250 | 0 | 0 | 250 | 0 |
| `$.sub_job.code` | 250 | 14 | 14 | 236 | 5 |
| `$.sub_job.number` | 250 | 0 | 0 | 250 | 0 |
| `$.sub_job.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis_assignees.company_id`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `3390`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignees[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.assignees[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.assignees[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis_ball_in_courts.company_id`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `148`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.ball_in_courts[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.ball_in_courts[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.ball_in_courts[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfis_questions.company_id`

- Inferred endpoint: `rfis`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1967`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.questions[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.questions[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.questions[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
assignee, assignees, ball_in_court, ball_in_courts, connect_export_origin, cost_code, cost_impact, created_at, created_by, current_revision, custom_fields, due_date, full_number, has_revisions, id, initiated_at, link, location, location_id, number, prefix, priority, private, project_stage, proposed_solution, questions, received_from, reference, responsible_contractor, revision, rfi_manager, schedule_impact, source_rfi_header_id, specification_section_id, status, sub_job, subject, time_resolved, translated_status, updated_at
```

### `procore_ep_rfqs.company_id`

- Inferred endpoint: `rfqs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_event.change_event_line_items[].cost_type.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.change_event.change_order_change_reason.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
assigned, attachments, change_event, change_event_line_item_id, commitment_change_order_packages, commitment_contract_id, commitment_potential_change_orders, created_at, created_by, currency_configuration, description, due_date, estimated_status, id, number, position, private, prostore_file_ids, quotes, responses, status, title, updated_at
```

### `procore_ep_rfqs_attachments.company_id`

- Inferred endpoint: `rfqs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `11`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.attachments[].company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.attachments[].project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].cost_type.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.change_event.change_order_change_reason.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
assigned, attachments, change_event, change_event_line_item_id, commitment_change_order_packages, commitment_contract_id, commitment_potential_change_orders, created_at, created_by, currency_configuration, description, due_date, estimated_status, id, number, position, private, prostore_file_ids, quotes, responses, status, title, updated_at
```

### `procore_ep_rfqs_change_event_attachments.company_id`

- Inferred endpoint: `rfqs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `31`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_event.attachments[].company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.attachments[].company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.attachments[].project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].cost_type.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.change_event.change_order_change_reason.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
assigned, attachments, change_event, change_event_line_item_id, commitment_change_order_packages, commitment_contract_id, commitment_potential_change_orders, created_at, created_by, currency_configuration, description, due_date, estimated_status, id, number, position, private, prostore_file_ids, quotes, responses, status, title, updated_at
```

### `procore_ep_rfqs_change_event_change_event_line_items.company_id`

- Inferred endpoint: `rfqs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `52`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_event.change_event_line_items[].company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].cost_type.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.change_event.change_event_line_items[].project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_order_change_reason.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
assigned, attachments, change_event, change_event_line_item_id, commitment_change_order_packages, commitment_contract_id, commitment_potential_change_orders, created_at, created_by, currency_configuration, description, due_date, estimated_status, id, number, position, private, prostore_file_ids, quotes, responses, status, title, updated_at
```

### `procore_ep_rfqs_change_event_change_event_line_items__0a3e8d.company_id`

- Inferred endpoint: `rfqs`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `57`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_event.change_event_line_items[].cost_code.line_item_types[].company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].cost_code.line_item_types[].company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].cost_code.line_item_types[].project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.change_event.change_event_line_items[].cost_type.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.change_event.change_order_change_reason.company_id` | 7 | 7 | 7 | 0 | 5 |
| `$.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company.id` | 7 | 0 | 0 | 7 | 0 |
| `$.project.company_id` | 7 | 0 | 0 | 7 | 0 |
| `$.company` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
assigned, attachments, change_event, change_event_line_item_id, commitment_change_order_packages, commitment_contract_id, commitment_potential_change_orders, created_at, created_by, currency_configuration, description, due_date, estimated_status, id, number, position, private, prostore_file_ids, quotes, responses, status, title, updated_at
```

### `procore_ep_subcontractor_invoice_change_order_items.company_id`

- Inferred endpoint: `subcontractor-invoice-change-order-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `24`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `24`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 24 | 0 | 0 | 24 | 0 |
| `$.company_id` | 24 | 0 | 0 | 24 | 0 |
| `$.project.company.id` | 24 | 0 | 0 | 24 | 0 |
| `$.project.company_id` | 24 | 0 | 0 | 24 | 0 |
| `$.company` | 24 | 0 | 0 | 24 | 0 |

Root keys from first matching payload:

```text
change_order_package_id, comment, commitment_line_item_id, commitment_line_item_origin_id, cost_code_id, currency_configuration, description_of_work, id, item_type, line_item_id, materials_moved, materials_retainage_retained_moved, position, scheduled_quantity, scheduled_unit_price, scheduled_value, ssr_manual_override, status, subcontractor_claimed_amount, total_completed_and_stored_to_date, total_completed_and_stored_to_date_percent, wbs_code, work_completed_from_previous_application, work_completed_from_previous_application_quantity, work_completed_retainage_from_previous_application, work_completed_retainage_percent_this_period, work_completed_retainage_released_this_period, work_completed_retainage_retained_this_period, work_completed_this_period, work_completed_this_period_quantity
```

### `procore_ep_subcontractor_invoice_contract_detail_items.company_id`

- Inferred endpoint: `subcontractor-invoice-contract-detail-items`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `152`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `152`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 152 | 0 | 0 | 152 | 0 |
| `$.company_id` | 152 | 0 | 0 | 152 | 0 |
| `$.project.company.id` | 152 | 0 | 0 | 152 | 0 |
| `$.project.company_id` | 152 | 0 | 0 | 152 | 0 |
| `$.company` | 152 | 0 | 0 | 152 | 0 |

Root keys from first matching payload:

```text
comment, cost_code_id, currency_configuration, description_of_work, detail_line_item_id, id, item_type, materials_moved, materials_presently_stored, materials_retainage_retained_moved, materials_stored_retainage_currently_retained, materials_stored_retainage_percent_this_period, materials_stored_retainage_released_this_period, position, scheduled_value, ssr_manual_override, status, subcontractor_claimed_amount, total_completed_and_stored_to_date, total_completed_and_stored_to_date_percent, wbs_code, work_completed_from_previous_application, work_completed_retainage_from_previous_application, work_completed_retainage_percent_this_period, work_completed_retainage_released_this_period, work_completed_retainage_retained_this_period, work_completed_this_period
```

### `procore_ep_subcontractor_invoices.company_id`

- Inferred endpoint: `subcontractor-invoices`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `981`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, billing_date, comment, commitment_id, commitment_type, contract_invoicing_method, contract_name, created_at, created_by, currency_configuration, custom_fields, deletable, electronic_signature_id, erp_status, final, id, invoice_number, invoice_type, move_materials_to_previous_work_completed, number, origin_data, origin_id, payment_date, payment_summary, percent_complete, period_id, previous_requisition_id, project_id, requisition_end, requisition_start, status, submitted_at, summary, total_claimed_amount, updated_at, vendor_id, vendor_name
```

### `procore_ep_subcontractor_invoices_attachments.company_id`

- Inferred endpoint: `subcontractor-invoices`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `981`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.attachments[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.attachments[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.attachments[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, billing_date, comment, commitment_id, commitment_type, contract_invoicing_method, contract_name, created_at, created_by, currency_configuration, custom_fields, deletable, electronic_signature_id, erp_status, final, id, invoice_number, invoice_type, move_materials_to_previous_work_completed, number, origin_data, origin_id, payment_date, payment_summary, percent_complete, period_id, previous_requisition_id, project_id, requisition_end, requisition_start, status, submitted_at, summary, total_claimed_amount, updated_at, vendor_id, vendor_name
```

### `procore_ep_submittals.company_id`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1760`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_submittals.location`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1760`
- DB non-null rows: `32`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 250 | 250 | 26 | 0 | 5 |
| `$.location.id` | 250 | 26 | 26 | 224 | 5 |
| `$.location.name` | 250 | 26 | 26 | 224 | 5 |
| `$.location.login` | 250 | 0 | 0 | 250 | 0 |
| `$.location.code` | 250 | 0 | 0 | 250 | 0 |
| `$.location.number` | 250 | 0 | 0 | 250 | 0 |
| `$.location.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_submittals.submittal_package`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1760`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.submittal_package` | 250 | 250 | 33 | 0 | 5 |
| `$.submittal_package.id` | 250 | 33 | 33 | 217 | 5 |
| `$.submittal_package.name` | 250 | 0 | 0 | 250 | 0 |
| `$.submittal_package.login` | 250 | 0 | 0 | 250 | 0 |
| `$.submittal_package.code` | 250 | 0 | 0 | 250 | 0 |
| `$.submittal_package.number` | 250 | 33 | 33 | 217 | 5 |
| `$.submittal_package.title` | 250 | 33 | 33 | 217 | 5 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_submittals.submittal_workflow_template`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `1760`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.submittal_workflow_template` | 250 | 250 | 15 | 0 | 5 |
| `$.submittal_workflow_template.id` | 250 | 15 | 15 | 235 | 5 |
| `$.submittal_workflow_template.name` | 250 | 15 | 15 | 235 | 5 |
| `$.submittal_workflow_template.login` | 250 | 0 | 0 | 250 | 0 |
| `$.submittal_workflow_template.code` | 250 | 0 | 0 | 250 | 0 |
| `$.submittal_workflow_template.number` | 250 | 0 | 0 | 250 | 0 |
| `$.submittal_workflow_template.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_submittals_approvers.company_id`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `7260`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.approvers[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.approvers[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.approvers[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_submittals_approvers_attachments.company_id`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `6571`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.approvers[].attachments[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.approvers[].attachments[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.approvers[].attachments[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_submittals_ball_in_court.company_id`

- Inferred endpoint: `submittals`
- Strict root cause: `schema_column_not_in_projection_registry`
- DB rows: `181`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.ball_in_court[].company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.ball_in_court[].company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.ball_in_court[].project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company.id` | 250 | 0 | 0 | 250 | 0 |
| `$.project.company_id` | 250 | 0 | 0 | 250 | 0 |
| `$.company` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
approvers, attachments_count, ball_in_court, buffer_time, closed_at, created_at, created_by, current_revision, custom_fields, distributed_at, due_date, for_record_only, formatted_number, id, is_rejected, issue_date, location, number, open_date, operation_item_errors, private, received_date, received_from, rejected_submittal_log_approver_id, required_on_site_date, responsible_contractor, revision, scheduled_task, specification_section, status, sub_job, submit_by, submittal_manager, submittal_package, submittal_workflow_template, submittal_workflow_template_applied_at, title, type, updated_at
```

### `procore_ep_budget_modifications.origin_data`

- Inferred endpoint: `budget-modifications`
- Strict root cause: `None`
- DB rows: `148`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `148`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.origin_data` | 148 | 148 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
created_at, from_budget_line_item_id, id, notes, origin_data, origin_id, to_budget_line_item_id, transfer_amount, updated_at
```

### `procore_ep_budget_modifications.origin_id`

- Inferred endpoint: `budget-modifications`
- Strict root cause: `None`
- DB rows: `148`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `148`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.origin_id` | 148 | 148 | 0 | 0 | 5 |
| `$.origin.id` | 148 | 0 | 0 | 148 | 0 |

Root keys from first matching payload:

```text
created_at, from_budget_line_item_id, id, notes, origin_data, origin_id, to_budget_line_item_id, transfer_amount, updated_at
```

### `procore_ep_change_events.currency_configuration_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `1054`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.currency_configuration.currency_iso_code` | 250 | 250 | 0 | 0 | 5 |
| `$.currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events.deleted_at`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `1054`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].deleted_at` | 250 | 248 | 0 | 2 | 5 |
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted_at` | 250 | 250 | 0 | 0 | 5 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events.external_data`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `1054`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.external_data` | 250 | 250 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events.source`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `1054`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.source` | 250 | 250 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_change`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_change` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_change` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_base_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_commitment_currency_configuration_base_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_commitment_currency_configuration_base_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_currency_exchange_rate`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_commitment_currency_configuration_currency_exchange_rate` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_commitment_currency_configuration_currency_exchange_rate` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_commitment_currency_configuration_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_commitment_currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_commitment_currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_contract_confirmed`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_contract_confirmed` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_contract_confirmed` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_non_commitment_amount`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_non_commitment_amount` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_non_commitment_amount` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_base_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_request_for_quote_currency_configuration_base_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_request_for_quote_currency_configuration_base_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_currency_exchange_rate`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_request_for_quote_currency_configuration_currency_exchange_rate` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_request_for_quote_currency_configuration_currency_exchange_rate` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_request_for_quote_currency_configuration_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_request_for_quote_currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_request_for_quote_currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.cost_impact_vendor_confirmed`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].cost_impact_vendor_confirmed` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_impact_vendor_confirmed` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.currency_configuration_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.currency_configuration.currency_iso_code` | 250 | 250 | 0 | 0 | 5 |
| `$.currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.deleted_at`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].deleted_at` | 250 | 248 | 0 | 2 | 5 |
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted_at` | 250 | 250 | 0 | 0 | 5 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_base_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].revenue_impact_change_order_currency_configuration_base_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.revenue_impact_change_order_currency_configuration_base_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_currency_exchange_rate`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].revenue_impact_change_order_currency_configuration_currency_exchange_rate` | 250 | 0 | 0 | 250 | 0 |
| `$.revenue_impact_change_order_currency_configuration_currency_exchange_rate` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.revenue_impact_change_order_currency_configuration_currency_iso_code`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.change_items[].revenue_impact_change_order_currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |
| `$.revenue_impact_change_order_currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_amount`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_amount` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_amount` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_budget_modification_id`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_budget_modification_id` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_budget_modification_id` | 250 | 0 | 0 | 250 | 0 |
| `$.budget_impact_budget_modification_budget_modification.id` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_notes`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_notes` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_notes` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_transfer_from_id`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_transfer_from_id` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_transfer_from_id` | 250 | 0 | 0 | 250 | 0 |
| `$.budget_impact_budget_modification_transfer_from.id` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_transfer_from_name`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_transfer_from_name` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_transfer_from_name` | 250 | 0 | 0 | 250 | 0 |
| `$.budget_impact_budget_modification_transfer_from.name` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_transfer_to_id`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_transfer_to_id` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_transfer_to_id` | 250 | 0 | 0 | 250 | 0 |
| `$.budget_impact_budget_modification_transfer_to.id` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_change_events_change_items.budget_impact_budget_modification_transfer_to_name`

- Inferred endpoint: `change-events`
- Strict root cause: `None`
- DB rows: `2816`
- DB non-null rows: `8`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.budget_impact_budget_modification_transfer_to_name` | 250 | 0 | 0 | 250 | 0 |
| `$.change_items[].budget_impact_budget_modification_transfer_to_name` | 250 | 0 | 0 | 250 | 0 |
| `$.budget_impact_budget_modification_transfer_to.name` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, change_items, change_reason, change_type, comments_enabled, company_id, created_at, created_by, currency_configuration, custom_fields, deletable, deleted_at, description, event_origin, external_data, has_edited_markups, id, in_recycle_bin, markup_items, notes, number, prime_contract_for_estimates, production_quantities, project_id, scope, source, source_of_revenue_rom, status, title, updated_at
```

### `procore_ep_commitment_change_orders.batch_id`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.batch_id` | 100 | 100 | 0 | 0 | 5 |
| `$.batch.id` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.currency_configuration_currency_iso_code`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.currency_configuration.currency_iso_code` | 100 | 100 | 0 | 0 | 5 |
| `$.currency_configuration_currency_iso_code` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.invoiced_date`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 100 | 0 | 0 | 100 | 0 |
| `$.closed_date` | 100 | 0 | 0 | 100 | 0 |
| `$.closed_on` | 100 | 0 | 0 | 100 | 0 |
| `$.created_at` | 100 | 100 | 100 | 0 | 5 |
| `$.date` | 100 | 0 | 0 | 100 | 0 |
| `$.datetime` | 100 | 0 | 0 | 100 | 0 |
| `$.due_date` | 100 | 100 | 31 | 0 | 5 |
| `$.invoiced.closed_at` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.closed_date` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.closed_on` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.created_at` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.date` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.datetime` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.due_date` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced.updated_at` | 100 | 0 | 0 | 100 | 0 |
| `$.invoiced_date` | 100 | 100 | 0 | 0 | 5 |
| `$.updated_at` | 100 | 100 | 100 | 0 | 5 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.paid_date`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 100 | 0 | 0 | 100 | 0 |
| `$.closed_date` | 100 | 0 | 0 | 100 | 0 |
| `$.closed_on` | 100 | 0 | 0 | 100 | 0 |
| `$.created_at` | 100 | 100 | 100 | 0 | 5 |
| `$.date` | 100 | 0 | 0 | 100 | 0 |
| `$.datetime` | 100 | 0 | 0 | 100 | 0 |
| `$.due_date` | 100 | 100 | 31 | 0 | 5 |
| `$.paid.closed_at` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.closed_date` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.closed_on` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.created_at` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.date` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.datetime` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.due_date` | 100 | 0 | 0 | 100 | 0 |
| `$.paid.updated_at` | 100 | 0 | 0 | 100 | 0 |
| `$.paid_date` | 100 | 100 | 0 | 0 | 5 |
| `$.updated_at` | 100 | 100 | 100 | 0 | 5 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.review_notes`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `1`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.review_notes` | 100 | 1 | 1 | 99 | 1 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.reviewed_by_id`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `1`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.reviewed_by` | 100 | 100 | 1 | 0 | 5 |
| `$.reviewed_by.id` | 100 | 1 | 1 | 99 | 1 |
| `$.reviewed_by_id` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.reviewed_by_name`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `1`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.reviewed_by` | 100 | 100 | 1 | 0 | 5 |
| `$.reviewed_by.name` | 100 | 1 | 1 | 99 | 1 |
| `$.reviewed_by_name` | 100 | 0 | 0 | 100 | 0 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_change_orders.signed_change_order_received_date`

- Inferred endpoint: `commitment-change-orders`
- Strict root cause: `None`
- DB rows: `100`
- DB non-null rows: `4`
- Endpoint payload rows loaded: `100`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 100 | 0 | 0 | 100 | 0 |
| `$.closed_date` | 100 | 0 | 0 | 100 | 0 |
| `$.closed_on` | 100 | 0 | 0 | 100 | 0 |
| `$.created_at` | 100 | 100 | 100 | 0 | 5 |
| `$.date` | 100 | 0 | 0 | 100 | 0 |
| `$.datetime` | 100 | 0 | 0 | 100 | 0 |
| `$.due_date` | 100 | 100 | 31 | 0 | 5 |
| `$.signed_change_order_received.closed_at` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.closed_date` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.closed_on` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.created_at` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.date` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.datetime` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.due_date` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received.updated_at` | 100 | 0 | 0 | 100 | 0 |
| `$.signed_change_order_received_date` | 100 | 100 | 4 | 0 | 5 |
| `$.updated_at` | 100 | 100 | 100 | 0 | 5 |

Root keys from first matching payload:

```text
batch_id, billing_schedule_of_values_status, change_order_change_reason, contract_id, created_at, created_by, currency_configuration, custom_fields, description, designated_reviewer, due_date, enable_ssov, executed, field_change, grand_total, id, invoiced_date, legacy_package_id, legacy_request_id, location_id, number, paid, paid_date, private, received_from, reference, reviewed_at, reviewed_by, revision, schedule_impact_amount, signature_required, signed_change_order_received_date, status, title, type, updated_at
```

### `procore_ep_commitment_compliance.compliance_notes`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.compliance_notes` | 7 | 7 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance.compliance_status`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.compliance_status` | 7 | 7 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance.derived_compliance_status`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.derived_compliance_status` | 7 | 7 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance.insurance_notes`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.insurance_notes` | 7 | 7 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance.insurance_status`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.insurance_status` | 7 | 7 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance.updated_at`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 7 | 0 | 0 | 7 | 0 |
| `$.closed_date` | 7 | 0 | 0 | 7 | 0 |
| `$.closed_on` | 7 | 0 | 0 | 7 | 0 |
| `$.created_at` | 7 | 0 | 0 | 7 | 0 |
| `$.date` | 7 | 0 | 0 | 7 | 0 |
| `$.datetime` | 7 | 0 | 0 | 7 | 0 |
| `$.due_date` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.closed_at` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.closed_date` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.closed_on` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.created_at` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.date` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.datetime` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.due_date` | 7 | 0 | 0 | 7 | 0 |
| `$.updated.updated_at` | 7 | 0 | 0 | 7 | 0 |
| `$.updated_at` | 7 | 7 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_compliance.updated_by_id`

- Inferred endpoint: `commitment-compliance`
- Strict root cause: `None`
- DB rows: `7`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `7`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.updated_by_id` | 7 | 7 | 0 | 0 | 5 |
| `$.updated_by.id` | 7 | 0 | 0 | 7 | 0 |

Root keys from first matching payload:

```text
compliance_documents, compliance_notes, compliance_requirements_not_created, compliance_status, derived_compliance_status, derived_insurance_status, insurance_documents, insurance_notes, insurance_requirements_not_created, insurance_status, updated_at, updated_by_id
```

### `procore_ep_commitment_contracts.actual_completion_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `1`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.actual_completion.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.date` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.actual_completion_date` | 250 | 238 | 1 | 12 | 5 |
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.approval_letter_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.approval_letter.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.date` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.approval_letter_date` | 250 | 250 | 0 | 0 | 5 |
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.assignee_id`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `9`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.assignee` | 250 | 7 | 7 | 243 | 5 |
| `$.assignee.id` | 250 | 7 | 7 | 243 | 5 |
| `$.assignee_id` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.contract_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.date` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.contract.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.contract_date` | 250 | 250 | 0 | 0 | 5 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.currency_configuration_currency_iso_code`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.currency_configuration.currency_iso_code` | 250 | 250 | 0 | 0 | 5 |
| `$.currency_configuration_currency_iso_code` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.delivery_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `7`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.date` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.delivery_date` | 250 | 12 | 6 | 238 | 5 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.execution_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.date` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.execution.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.execution_date` | 250 | 250 | 0 | 0 | 5 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.issued_on_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.date` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.issued_on_date` | 250 | 250 | 0 | 0 | 5 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.letter_of_intent_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.date` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.letter_of_intent_date` | 250 | 250 | 0 | 0 | 5 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.payment_terms`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `3`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.payment_terms` | 250 | 12 | 2 | 238 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.returned_date`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 0 | 0 | 250 | 0 |
| `$.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.date` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.returned.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.returned_date` | 250 | 250 | 0 | 0 | 5 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_contracts.ship_via`

- Inferred endpoint: `commitment-contracts`
- Strict root cause: `None`
- DB rows: `243`
- DB non-null rows: `1`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.ship_via` | 250 | 12 | 1 | 238 | 5 |

Root keys from first matching payload:

```text
accounting_method, actual_completion_date, allow_change_orders_ssov, allow_comments, allow_markups, allow_payment_applications, allow_payments, approval_letter_date, billing_schedule_of_values_status, change_order_level_of_detail, contract_date, contract_estimated_completion_date, contract_start_date, created_at, created_by, currency_configuration, description, display_materials_retainage, display_work_retainage, enable_ssov, exclusions, executed, execution_date, grand_total, id, inclusions, issued_on_date, letter_of_intent_date, number, private, retainage_percent, returned_date, show_cost_code_on_pdf, show_line_items_to_non_admins, signature_required, signed_contract_received_date, ssr_enabled, status, title, type, updated_at, vendor
```

### `procore_ep_commitment_line_items.funding_rule_id`

- Inferred endpoint: `commitment-line-items`
- Strict root cause: `None`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.funding_rule_id` | 63 | 63 | 0 | 0 | 5 |
| `$.funding_rule.id` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
amount, description, funding_rule_id, id, position, prime_line_item_id, tax_code_id, wbs_code, wbs_code_id
```

### `procore_ep_commitment_line_items.prime_line_item_id`

- Inferred endpoint: `commitment-line-items`
- Strict root cause: `None`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.prime_line_item_id` | 63 | 63 | 0 | 0 | 5 |
| `$.prime_line_item.id` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
amount, description, funding_rule_id, id, position, prime_line_item_id, tax_code_id, wbs_code, wbs_code_id
```

### `procore_ep_commitment_line_items.tax_code_id`

- Inferred endpoint: `commitment-line-items`
- Strict root cause: `None`
- DB rows: `63`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.tax_code_id` | 63 | 63 | 0 | 0 | 5 |
| `$.tax_code.id` | 63 | 0 | 0 | 63 | 0 |

Root keys from first matching payload:

```text
amount, description, funding_rule_id, id, position, prime_line_item_id, tax_code_id, wbs_code, wbs_code_id
```

### `procore_ep_commitment_line_items.uom`

- Inferred endpoint: `commitment-line-items`
- Strict root cause: `None`
- DB rows: `63`
- DB non-null rows: `3`
- Endpoint payload rows loaded: `63`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.uom` | 63 | 3 | 3 | 60 | 3 |

Root keys from first matching payload:

```text
amount, description, funding_rule_id, id, position, prime_line_item_id, tax_code_id, wbs_code, wbs_code_id
```

### `procore_ep_daily_log_dcrs.deleted_at`

- Inferred endpoint: `daily-log-dcrs`
- Strict root cause: `None`
- DB rows: `2628`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 250 | 250 | 0 | 5 |
| `$.datetime` | 250 | 250 | 250 | 0 | 5 |
| `$.deleted.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted_at` | 250 | 250 | 0 | 0 | 5 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
apprentice_hours, attachments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, first_year_hours, foreman_hours, id, journeyman_hours, local_city_hours, local_county_hours, location, minority_hours, notes, number_of_apprentice_workers, number_of_foreman_workers, number_of_journeyman_workers, number_of_other_workers, other_hours, permissions, position, related_items, status, trade, updated_at, vendor, veteran_hours, women_hours
```

### `procore_ep_daily_log_dcrs.location`

- Inferred endpoint: `daily-log-dcrs`
- Strict root cause: `None`
- DB rows: `2628`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 250 | 250 | 0 | 0 | 5 |
| `$.location.id` | 250 | 0 | 0 | 250 | 0 |
| `$.location.name` | 250 | 0 | 0 | 250 | 0 |
| `$.location.login` | 250 | 0 | 0 | 250 | 0 |
| `$.location.code` | 250 | 0 | 0 | 250 | 0 |
| `$.location.number` | 250 | 0 | 0 | 250 | 0 |
| `$.location.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
apprentice_hours, attachments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, first_year_hours, foreman_hours, id, journeyman_hours, local_city_hours, local_county_hours, location, minority_hours, notes, number_of_apprentice_workers, number_of_foreman_workers, number_of_journeyman_workers, number_of_other_workers, other_hours, permissions, position, related_items, status, trade, updated_at, vendor, veteran_hours, women_hours
```

### `procore_ep_daily_log_deliveries.deleted_at`

- Inferred endpoint: `daily-log-deliveries`
- Strict root cause: `None`
- DB rows: `59`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `59`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 59 | 0 | 0 | 59 | 0 |
| `$.closed_date` | 59 | 0 | 0 | 59 | 0 |
| `$.closed_on` | 59 | 0 | 0 | 59 | 0 |
| `$.created_at` | 59 | 59 | 59 | 0 | 5 |
| `$.date` | 59 | 59 | 59 | 0 | 5 |
| `$.datetime` | 59 | 59 | 59 | 0 | 5 |
| `$.deleted.closed_at` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.closed_date` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.closed_on` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.created_at` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.date` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.datetime` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.due_date` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted.updated_at` | 59 | 0 | 0 | 59 | 0 |
| `$.deleted_at` | 59 | 59 | 0 | 0 | 5 |
| `$.due_date` | 59 | 0 | 0 | 59 | 0 |
| `$.updated_at` | 59 | 59 | 59 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, comments, contents, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, delivery_from, id, location, permissions, position, related_items, status, time_hour, time_minute, tracking_number, updated_at, vendor
```

### `procore_ep_daily_log_deliveries.location`

- Inferred endpoint: `daily-log-deliveries`
- Strict root cause: `None`
- DB rows: `59`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `59`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.location` | 59 | 59 | 0 | 0 | 5 |
| `$.location.id` | 59 | 0 | 0 | 59 | 0 |
| `$.location.name` | 59 | 0 | 0 | 59 | 0 |
| `$.location.login` | 59 | 0 | 0 | 59 | 0 |
| `$.location.code` | 59 | 0 | 0 | 59 | 0 |
| `$.location.number` | 59 | 0 | 0 | 59 | 0 |
| `$.location.title` | 59 | 0 | 0 | 59 | 0 |

Root keys from first matching payload:

```text
attachments, comments, contents, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, delivery_from, id, location, permissions, position, related_items, status, time_hour, time_minute, tracking_number, updated_at, vendor
```

### `procore_ep_daily_log_deliveries.tracking_number`

- Inferred endpoint: `daily-log-deliveries`
- Strict root cause: `None`
- DB rows: `59`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `59`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.tracking_number` | 59 | 59 | 0 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, comments, contents, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, delivery_from, id, location, permissions, position, related_items, status, time_hour, time_minute, tracking_number, updated_at, vendor
```

### `procore_ep_daily_log_deliveries.vendor`

- Inferred endpoint: `daily-log-deliveries`
- Strict root cause: `None`
- DB rows: `59`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `59`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.vendor` | 59 | 59 | 0 | 0 | 5 |
| `$.vendor.id` | 59 | 0 | 0 | 59 | 0 |
| `$.vendor.name` | 59 | 0 | 0 | 59 | 0 |
| `$.vendor.login` | 59 | 0 | 0 | 59 | 0 |
| `$.vendor.code` | 59 | 0 | 0 | 59 | 0 |
| `$.vendor.number` | 59 | 0 | 0 | 59 | 0 |
| `$.vendor.title` | 59 | 0 | 0 | 59 | 0 |

Root keys from first matching payload:

```text
attachments, comments, contents, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, delivery_from, id, location, permissions, position, related_items, status, time_hour, time_minute, tracking_number, updated_at, vendor
```

### `procore_ep_daily_log_inspections.deleted_at`

- Inferred endpoint: `daily-log-inspections`
- Strict root cause: `None`
- DB rows: `114`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `114`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 114 | 0 | 0 | 114 | 0 |
| `$.closed_date` | 114 | 0 | 0 | 114 | 0 |
| `$.closed_on` | 114 | 0 | 0 | 114 | 0 |
| `$.created_at` | 114 | 114 | 114 | 0 | 5 |
| `$.date` | 114 | 114 | 114 | 0 | 5 |
| `$.datetime` | 114 | 114 | 114 | 0 | 5 |
| `$.deleted.closed_at` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.closed_date` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.closed_on` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.created_at` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.date` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.datetime` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.due_date` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted.updated_at` | 114 | 0 | 0 | 114 | 0 |
| `$.deleted_at` | 114 | 114 | 0 | 0 | 5 |
| `$.due_date` | 114 | 0 | 0 | 114 | 0 |
| `$.updated_at` | 114 | 114 | 114 | 0 | 5 |

Root keys from first matching payload:

```text
area, attachments, comments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, end_hour, end_minute, id, inspecting_entity, inspection_type, inspector_name, location, permissions, position, related_items, start_hour, start_minute, status, updated_at, vendor
```

### `procore_ep_daily_log_inspections.vendor`

- Inferred endpoint: `daily-log-inspections`
- Strict root cause: `None`
- DB rows: `114`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `114`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.vendor` | 114 | 114 | 0 | 0 | 5 |
| `$.vendor.id` | 114 | 0 | 0 | 114 | 0 |
| `$.vendor.name` | 114 | 0 | 0 | 114 | 0 |
| `$.vendor.login` | 114 | 0 | 0 | 114 | 0 |
| `$.vendor.code` | 114 | 0 | 0 | 114 | 0 |
| `$.vendor.number` | 114 | 0 | 0 | 114 | 0 |
| `$.vendor.title` | 114 | 0 | 0 | 114 | 0 |

Root keys from first matching payload:

```text
area, attachments, comments, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, end_hour, end_minute, id, inspecting_entity, inspection_type, inspector_name, location, permissions, position, related_items, start_hour, start_minute, status, updated_at, vendor
```

### `procore_ep_daily_log_manpower.contact_job_title`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.contact.job_title` | 250 | 250 | 0 | 0 | 5 |
| `$.contact_job_title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.contact_login_information_id`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.contact.login_information_id` | 250 | 250 | 0 | 0 | 5 |
| `$.contact_login_information_id` | 250 | 0 | 0 | 250 | 0 |
| `$.contact_login_information.id` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.contact_vendor_name`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.contact.vendor_name` | 250 | 250 | 0 | 0 | 5 |
| `$.contact_vendor_name` | 250 | 0 | 0 | 250 | 0 |
| `$.contact_vendor.name` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.cost_code_id`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `2`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_code` | 250 | 250 | 0 | 0 | 5 |
| `$.cost_code.id` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code_id` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.cost_code_long_name`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `2`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_code.long_name` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code_long_name` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code_long.name` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.cost_code_name`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `2`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.cost_code` | 250 | 250 | 0 | 0 | 5 |
| `$.cost_code.name` | 250 | 0 | 0 | 250 | 0 |
| `$.cost_code_name` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.deleted_at`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.created_at` | 250 | 250 | 250 | 0 | 5 |
| `$.date` | 250 | 250 | 250 | 0 | 5 |
| `$.datetime` | 250 | 250 | 250 | 0 | 5 |
| `$.deleted.closed_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.closed_on` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.created_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.datetime` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted.updated_at` | 250 | 0 | 0 | 250 | 0 |
| `$.deleted_at` | 250 | 250 | 0 | 0 | 5 |
| `$.due_date` | 250 | 0 | 0 | 250 | 0 |
| `$.updated_at` | 250 | 250 | 250 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_manpower.trade`

- Inferred endpoint: `daily-log-manpower`
- Strict root cause: `None`
- DB rows: `921`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `250`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.trade` | 250 | 250 | 0 | 0 | 5 |
| `$.trade.id` | 250 | 0 | 0 | 250 | 0 |
| `$.trade.name` | 250 | 0 | 0 | 250 | 0 |
| `$.trade.login` | 250 | 0 | 0 | 250 | 0 |
| `$.trade.code` | 250 | 0 | 0 | 250 | 0 |
| `$.trade.number` | 250 | 0 | 0 | 250 | 0 |
| `$.trade.title` | 250 | 0 | 0 | 250 | 0 |

Root keys from first matching payload:

```text
attachments, contact, cost_code, created_at, created_by, created_by_collaborator, custom_fields, date, datetime, deleted_at, id, location, man_hours, notes, num_hours, num_workers, permissions, position, related_items, status, trade, updated_at, vendor
```

### `procore_ep_daily_log_notes.deleted_at`

- Inferred endpoint: `daily-log-notes`
- Strict root cause: `None`
- DB rows: `92`
- DB non-null rows: `0`
- Endpoint payload rows loaded: `92`

| JSON path | inspected | present | non-empty | missing | samples included |
|---|---:|---:|---:|---:|---:|
| `$.closed_at` | 92 | 0 | 0 | 92 | 0 |
| `$.closed_date` | 92 | 0 | 0 | 92 | 0 |
| `$.closed_on` | 92 | 0 | 0 | 92 | 0 |
| `$.created_at` | 92 | 92 | 92 | 0 | 5 |
| `$.date` | 92 | 92 | 92 | 0 | 5 |
| `$.datetime` | 92 | 92 | 92 | 0 | 5 |
| `$.deleted.closed_at` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.closed_date` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.closed_on` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.created_at` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.date` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.datetime` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.due_date` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted.updated_at` | 92 | 0 | 0 | 92 | 0 |
| `$.deleted_at` | 92 | 92 | 0 | 0 | 5 |
| `$.due_date` | 92 | 0 | 0 | 92 | 0 |
| `$.updated_at` | 92 | 92 | 92 | 0 | 5 |

Root keys from first matching payload:

```text
attachments, comment, created_at, created_by, created_by_collaborator, custom_fields, daily_log_header_id, date, datetime, deleted_at, id, is_issue_day, location, permissions, position, related_items, status, updated_at, vendor
```
