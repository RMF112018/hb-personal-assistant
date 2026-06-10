# 05 Backfill, Reprocessing, And Coverage

`hb-assistant procore analytics reprocess` supports dry-run by default and explicit `--apply`.
`--apply` requires `--db`, so production cannot be mutated accidentally.

Copied-DB full backfill result:

- Inspected local Procore live records: `30,059`.
- Raw landing rows written: `30,059`.
- Structured rows written: `30,059`.
- Source quality: `redacted_legacy_projection`.
- Live Procore calls: `0`.
- External writeback: `0`.

Coverage report after backfill:

- Total live record rows: `30,059`.
- Total raw landing rows: `30,059`.
- Total structured rows: `30,059`.
- Structured acceptance gate: `true`.
- `raw_json_only_is_sufficient`: `false`.
