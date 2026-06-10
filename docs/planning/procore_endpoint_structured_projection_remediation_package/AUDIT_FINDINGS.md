# Seed Finding: Change Events Prove Structured Projection Is Too Shallow

This package is seeded by the production evidence gathered after PR #18.

## Confirmed facts from the operator session

- Full raw payload ingestion works.
- `procore_endpoint_raw_payloads` contains `live_full_payload` rows.
- `procore_raw_change_events` has mostly full-source rows:
  - `live_full_payload`: 194 rows
  - `redacted_legacy_projection`: 4 rows
- Yet many useful structured columns remain empty in `procore_raw_change_events`.

## Observed empty columns in `procore_raw_change_events`

Across 198 rows:

- `company_id`: empty
- `company_id_hash`: empty
- `assignee_name`: empty
- `responsible_party_name`: empty
- `due_at_utc`: empty
- `start_at_utc`: empty
- `finish_at_utc`: empty
- `cost_code`: empty
- `cost_type`: empty
- `amount`: empty
- `currency`: empty
- `quantity`: empty
- `unit_of_measure`: empty

## Fields present in change-event full raw payloads but not projected usefully

Observed in payload field inventories:

- `attachments`
- `change_items`
- `change_reason`
- `change_type`
- `comments_enabled`
- `company_id`
- `created_at`
- `created_by`
- `currency_configuration`
- `custom_fields`
- `deletable`
- `deleted_at`
- `description`
- `event_origin`
- `external_data`
- `has_edited_markups`
- `id`
- `in_recycle_bin`
- `markup_items`
- `notes`
- `number`
- `prime_contract_for_estimates`
- `production_quantities`
- `project_id`
- `scope`
- `source`
- `source_of_revenue_rom`
- `status`
- `title`
- `updated_at`

## Nested `change_items[]` fields observed

The nested change-event payload contains business-critical fields such as:

- `budget_code`
- `flat_code`
- `segment_items`
- `cost_impact`
- `budget_impact`
- `commitment`
- `contract`
- `vendor`
- `line_item`
- `amount`
- `amount_project_currency`
- `quantity`
- `unit_cost`
- `unit_of_measure`
- `calculation_strategy`
- `status`
- `title`
- `number`

## Required inference

The database is now a raw source of truth, but not yet a useful analytical/read-model database. Remediation must build endpoint-specific structured projections and nested child tables for all endpoints, not merely improve the generic `procore_raw_*` family tables.
