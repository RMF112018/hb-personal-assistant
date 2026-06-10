# 02 — Endpoint Projection Matrix

## Goal

Create a complete endpoint-by-endpoint projection matrix that maps every observed Procore payload field path to a destination.

## Required matrix columns

At minimum:

- endpoint_key
- endpoint_family
- json_path
- observed_type
- cardinality
- occurrence_count
- non_null_count
- empty_count
- business_category
- destination_kind
- destination_table
- destination_column
- child_table_parent_key
- extraction_strategy
- exclusion_reason
- status

## Destination kinds

Allowed destination kinds:

- `primary_column`
- `child_table_column`
- `dimension_table_column`
- `bridge_table_column`
- `lossless_sidecar_json`
- `excluded_non_business`
- `excluded_transport_secret`

`excluded_*` requires a reason. Business fields may not be excluded merely because they are inconvenient.

## Completion gate

For every endpoint with full raw payloads:
- no `status = unmapped` for primary fields,
- no `status = unmapped` for nested business fields,
- no observed nested array without a table or sidecar.

## Evidence

Write:
- `01-payload-field-inventory.json` or `.csv` under evidence (field names/counts only),
- `02-endpoint-projection-matrix.csv`,
- `02-endpoint-projection-matrix-summary.md`.
