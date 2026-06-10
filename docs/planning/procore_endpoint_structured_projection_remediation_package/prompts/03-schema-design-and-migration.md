# 03 — Schema Design and Migration

## Goal

Design and implement additive schema changes for endpoint-specific structured projection tables and nested child/detail tables.

## Requirements

- Do not drop or destructively alter existing tables.
- Preserve `procore_raw_*` compatibility tables.
- Add a migration if schema changes are required.
- Every new table must include:
  - stable primary key,
  - endpoint_key where relevant,
  - project_key,
  - project_id and/or hashes where relevant,
  - company_id and/or hashes where relevant,
  - record_id / parent_record_id as relevant,
  - raw_payload_id,
  - payload_hash,
  - source_quality,
  - payload_seen_first_utc,
  - payload_seen_last_utc,
  - is_current,
  - created_utc,
  - updated_utc,
  - external_writeback_performed default 0 / check 0.

## Required table patterns

Create endpoint-specific primary and child/detail tables as derived from the projection matrix.

For change events, minimum expected tables:

- `procore_change_events`
- `procore_change_event_items`
- `procore_change_event_item_budget_segments`
- `procore_change_event_attachments`
- `procore_change_event_markup_items`
- `procore_change_event_custom_fields`
- `procore_change_event_production_quantities`

Equivalent endpoint-specific table families must be produced for all endpoints with nested content.

## Evidence

Write:
- schema migration summary,
- table list,
- column list,
- FK/index summary,
- compatibility notes.
