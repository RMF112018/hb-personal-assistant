# 05 — Legacy replay precedence and CLI honesty

## Objective

Keep legacy replay for historical bootstrap, but ensure it cannot degrade full raw payload data and that CLI receipts are honest.

## Required behavior

`hb-assistant procore analytics reprocess` must:

- prefer full raw rows when they exist;
- use legacy redacted replay only when full raw rows do not exist;
- report full raw rows inspected/written;
- report legacy rows inspected/written;
- report skipped due to higher quality;
- report source-quality distribution.

## CLI compatibility

Do not break existing operator commands. Add flags only if necessary. Sensible default should be:

- prefer full raw;
- fallback to redacted legacy only when no full payload exists.

## Tests

Prove this sequence:

1. legacy replay first creates degraded rows;
2. live full payload later upgrades rows;
3. legacy replay after full payload is no-op/skipped;
4. receipts classify skipped/downgrade prevention.

## Evidence

Write `docs/evidence/procore_full_raw_payload_ingestion/06-idempotency-and-precedence.md` with operation sequence, row counts, source-quality distribution, and downgrade prevention proof.
