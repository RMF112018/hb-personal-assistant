# 06 — Backfill and CLI Surfaces

## Goal

Implement replay/backfill from `procore_endpoint_raw_payloads.payload_json` into the new endpoint-specific projection tables.

## Required behavior

- No live Procore calls during projection replay.
- Idempotent.
- Bounded by endpoint/project/limit filters.
- Applies source-quality precedence.
- Supports dry-run and apply modes.
- Emits no raw payload bodies.

## CLI requirements

Add or extend commands for:

```bash
hb-assistant procore analytics projection-inventory --db "$DB" --json
hb-assistant procore analytics projection-audit --db "$DB" --json
hb-assistant procore analytics projection-reprocess --db "$DB" --apply --json
hb-assistant procore analytics projection-coverage --db "$DB" --json
```

Names may vary if repo conventions require, but command functionality must exist.

## Receipts

Receipts must include:
- endpoints inspected,
- payload rows inspected,
- primary rows written,
- child rows written,
- unmapped fields by endpoint,
- skipped/held endpoints,
- source-quality breakdown,
- external_writeback_performed = 0.

Receipts must not include:
- raw payload body,
- field values from payload bodies,
- URLs,
- secrets.
