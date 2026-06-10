# 01 — Payload Field Inventory Engine

## Goal

Build or extend a deterministic local inventory engine that extracts field-path coverage from full raw Procore payloads without emitting values.

## Required behavior

For each `endpoint_key` in `procore_endpoint_raw_payloads` where `raw_procore_payload_persisted=1`:

- inventory top-level keys,
- inventory nested object paths,
- inventory nested array paths,
- count occurrences,
- count non-null / null / empty rates,
- detect scalar/object/array type variations,
- count array cardinalities,
- classify fields into preliminary categories.

The inventory must not emit raw values. It may emit field names, JSON paths, types, counts, percentages, and hash prefixes.

## Deliverables

- Implement a reusable inventory module under `src/hb_assistant/procore/`.
- Add a CLI command or extend analytics CLI:
  - `projection-inventory`
  - JSON and markdown/table output.
- Add tests using synthetic fixture payloads with nested arrays/objects.
- Add templates or generated reports under evidence.

## Completion gate

The inventory engine must prove it can find the change-event fields that seeded this package: `change_items[]`, `attachments[]`, `markup_items[]`, `custom_fields`, `company_id`, `project_id`, `change_type`, `change_reason`, `scope`, `source_of_revenue_rom`.
