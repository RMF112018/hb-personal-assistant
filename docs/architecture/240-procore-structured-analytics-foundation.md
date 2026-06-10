# Procore Structured Analytics Foundation

## Summary

This run adds a local Procore structured analytics foundation. The storage design is not owned by
the daily brief or local model pipeline. Daily brief usefulness is a downstream validation target.

The acceptance gate is structured endpoint-family storage, not JSON capture alone.

## Storage Layers

1. **Capture/control:** `procore_endpoint_contracts`, `procore_endpoint_capture_runs`,
   `procore_endpoint_capture_pages`, and `procore_endpoint_capture_errors`.
2. **Governed raw landing:** `procore_endpoint_raw_payloads`, used for local replay, current/history
   selection, payload hashes, source refs, scrub status, retention, and source quality.
3. **Structured bronze:** endpoint-family `procore_raw_*` tables that preserve typed/queryable
   business fields close to endpoint shape.
4. **Future marts:** conformed `procore_analytics_*` facts/dimensions can be built later from the
   raw landing plus `procore_raw_*` tables without re-querying Procore.
5. **Gold/read models:** ranked signals, daily brief candidates, local model context, CLI/status, and
   operator reports consume redacted/source-linked projections only.

## Structured Table Coverage

V46 adds structured endpoint-family tables for RFIs/responses, submittals/packages/responses,
observations, punch items, meetings/details/topics, daily logs, inspections/sections/items,
schedules/activities, contracts/line items/change orders, budgets, invoices/payment applications,
attachments, and project/company/person/cost-code/location/status/date dimensions.

All structured rows carry stable source identity, endpoint/family identity, project/record/parent
identity, payload hash, raw payload link, current/history fields, source/capture timestamps,
business status/date/owner/cost fields where available, source quality, retention, scrub status, and
no-writeback/no-raw-emission guards.

## Backfill And Reprocessing

`hb-assistant procore analytics reprocess` backfills from existing local `procore_live_records`
without live Procore calls. Bootstrap rows sourced from `canonical_json_redacted` are labelled
`source_quality=redacted_legacy_projection`; they are a partial historical bootstrap, not complete
true raw endpoint capture.

New live capture integrations should populate `procore_endpoint_raw_payloads` and the matching
`procore_raw_*` structured table at the canonical live-sync boundary.

## Financial Amount Extraction

The bronze `amount` column is populated by endpoint-family-aware monetary extraction, not a single
generic key probe. `AMOUNT_FIELDS_BY_ENDPOINT` (in `procore/structured_analytics.py`) maps each
financial `endpoint_id` to an ordered list of source field paths; `_path_value` resolves both flat
keys and dotted paths (e.g. `summary.current_payment_due`). The original generic key list
(`amount`, `total`, `total_amount`, `contract_amount`, `revised_budget`, `original_budget_amount`,
`current_budget_amount`) remains the universal fallback, so endpoints whose payloads already expose
a plain `amount` (line items, budget rows) are unchanged.

Documented precedence:

- **Invoice items** (`subcontractor-invoice-*-items` → `procore_raw_invoice_items`):
  `work_completed_this_period` → `total_completed_and_stored_to_date` →
  `subcontractor_claimed_amount` → `scheduled_value`. The headline represents amount billed this
  period; SOV/cumulative values stay available in source for other questions.
- **Invoices** (`subcontractor-invoices` → `procore_raw_invoices`): `total_claimed_amount` →
  `summary.current_payment_due` → `summary.contract_sum_to_date` →
  `summary.total_completed_and_stored_to_date`.
- **Change orders** (`prime-/commitment-change-orders` → `procore_raw_change_orders`): `grand_total`
  only. `schedule_impact_amount` is deliberately excluded — it is a schedule day-count, not currency.
- **Payment applications**: mapped but currently source-absent (no `payment-applications` endpoint
  emits rows); amounts will populate automatically when source rows arrive.

The amount stays `TEXT` (V46 unchanged); typed aggregation is a downstream silver/mart concern.
Source-field provenance is exposed by `_amount_with_source` for diagnostics/tests but is not
persisted. `structured_coverage` reports `non_null_amount_rows` and `amount_coverage_pct` per
endpoint so financial coverage gaps are visible without inspecting payloads.

## Operator Surfaces

New local-only CLI surfaces:

- `hb-assistant procore analytics contract --json`
- `hb-assistant procore analytics coverage --json`
- `hb-assistant procore analytics coverage --markdown`
- `hb-assistant procore analytics reprocess --dry-run --family rfis`
- `hb-assistant procore analytics structured-counts --project-key <key> --json`
- `hb-assistant procore analytics ranking-diagnostics --brief-date YYYY-MM-DD --json`
- `hb-assistant procore analytics no-raw-leak-scan --path <path> --json`

`reprocess --apply` requires `--db` so production cannot be accidentally mutated.

## Daily Brief Relationship

Daily brief/local-model projections must consume ranked, source-linked structured projections.
Aggregate Procore sludge and closed-record noise belong in analytics diagnostics, not top-priority
brief sections. Raw Procore payloads must not appear in daily brief, browser, Obsidian, status JSON,
test snapshots, or repo evidence.
