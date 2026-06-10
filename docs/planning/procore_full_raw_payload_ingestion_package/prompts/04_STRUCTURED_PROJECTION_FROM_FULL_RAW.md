# 04 — Structured projection from full raw payloads

## Objective

Make structured `procore_raw_*` projection prefer full raw payload rows and use legacy redacted replay only as degraded fallback.

## Required source order

Structured projection must prefer:

1. `procore_endpoint_raw_payloads` rows where `raw_procore_payload_persisted=1` and source quality is full/high fidelity;
2. direct live payload object during live sync;
3. `procore_live_records.canonical_json_redacted` only when no full raw payload exists.

## Refactor

Create or clarify helpers like:

- `structured_values_from_payload(...)`;
- `insert_structured_from_payload(...)`;
- `backfill_from_raw_payloads(...)`;
- `backfill_from_live_records(...)` as degraded fallback.

Exact names may vary.

## Non-regression

Maintain financial amount extraction for:

- invoice items;
- invoices;
- change orders with `grand_total` only;
- change-order line items;
- contract line items;
- budget rows.

## Coverage diagnostics

Enhance coverage if useful to include:

- rows by source quality;
- raw persisted count;
- legacy fallback count;
- per-table null rates for critical fields;
- degraded rows count.

No raw values in diagnostics.

## Evidence

Write `docs/evidence/procore_full_raw_payload_ingestion/05-structured-null-rate-matrix.md` with:

`table | endpoint | source_quality | rows | critical_fields_checked | before_null_pct | after_null_pct | verdict`
