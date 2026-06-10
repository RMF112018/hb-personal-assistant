# 07 — Tests, Fixtures, and Regression Protection

## Goal

Add tests that prevent regression to shallow generic projections.

## Minimum tests

1. Change-event fixture:
   - full payload with nested `change_items`, `budget_code.segment_items`, `cost_impact`, `budget_impact`, `vendor`, `commitment`, `contract`, attachments, markup items, custom fields.
   - Assert primary + child/detail rows are written.
   - Assert every fixture field path is mapped.

2. Generic field-inventory fixture:
   - payload with nested arrays/objects.
   - assert inventory finds every path.

3. Completeness gate:
   - introducing a new unmapped business field in fixture fails the audit.

4. Source-quality no-downgrade:
   - legacy projection cannot overwrite endpoint-specific full projection.

5. Idempotency:
   - repeated replay does not duplicate child rows.

6. No raw leak:
   - CLI receipts and evidence do not contain raw bodies.

7. Broad endpoint smoke:
   - test at least one representative payload per endpoint family.

## Existing tests

Keep PR #18 tests passing:
- full raw ingestion,
- structured analytics foundation,
- live sync chain tests.

Do not weaken or delete tests to make new tests pass.
