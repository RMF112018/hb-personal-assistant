# 09 — Financial amount-field remediation

## Why

The independent audit classified the branch **PARTIAL / PASS WITH CONDITIONS** for one
reason: the bronze structured tables existed and backfilled safely, but the financial
`amount` column was mostly NULL on the largest financial families. Root cause: the single
generic `_amount()` probe in `src/hb_assistant/procore/structured_analytics.py` recognised
only plain monetary keys (`amount`, `total`, …) that do **not** appear in Procore invoice,
invoice-item, or change-order payloads.

## What changed (code)

`src/hb_assistant/procore/structured_analytics.py` only:

1. `_path_value(payload, path)` — flat-or-dotted resolver (e.g. `summary.current_payment_due`).
2. `AMOUNT_FIELDS_BY_ENDPOINT` — endpoint-family-aware monetary field registry, keyed by the
   same `endpoint_id` as `STRUCTURED_TABLE_BY_ENDPOINT`.
3. `_amount_with_source(payload, endpoint_id)` — endpoint-aware precedence, then the original
   generic key list as a universal fallback; returns `(amount, source_field)` (source field is
   for diagnostics/tests only — **not persisted**).
4. `_amount()` now delegates to it; call site passes `endpoint_id`.
5. `structured_coverage()` gains additive keys `non_null_amount_rows` and `amount_coverage_pct`
   per endpoint row (no flag/command renames).

**No schema change.** V46 is preserved; `amount` remains `TEXT`. No new DB column was added —
`amount_source_field` is proven in tests/evidence, not stored.

## Extraction fields & precedence (documented)

| structured table | source endpoint(s) | precedence (first wins) |
|---|---|---|
| `procore_raw_invoice_items` | `subcontractor-invoice-contract-detail-items`, `-contract-items`, `-change-order-items` | `work_completed_this_period` → `total_completed_and_stored_to_date` → `subcontractor_claimed_amount` → `scheduled_value` |
| `procore_raw_invoices` | `subcontractor-invoices` | `total_claimed_amount` → `summary.current_payment_due` → `summary.contract_sum_to_date` → `summary.total_completed_and_stored_to_date` |
| `procore_raw_change_orders` | `prime-change-orders`, `commitment-change-orders` | `grand_total` **only** |
| `procore_raw_payment_applications` | `payment-applications` | `total_claimed_amount` → `summary.current_payment_due` → `amount` *(source-absent today)* |
| line items / budget rows | (unchanged) | generic fallback (`amount` / `original_budget_amount`) |

### Decisions

- **Invoice items lead with `work_completed_this_period`** so the bronze `amount` represents
  the amount billed this period. `scheduled_value` (the SOV contract value) and
  `total_completed_and_stored_to_date` (cumulative) answer different questions and are read
  from source SOV fields when needed; they remain in the fallback chain.
- **`schedule_impact_amount` is deliberately excluded** from `change_orders.amount`. Sampled
  values are schedule **day-counts** (e.g. `"5"`, `"0"`), not currency; mapping them into a
  dollar column would contaminate cost analytics. `grand_total` is the only CO dollar source.

## Files in this bundle

- `before-after-amount-coverage.md` — the population matrix (the decisive proof).
- `sampled-field-summary.md` — money-like field names per endpoint (names only, no bodies).
- `db-copy-backfill-proof.md` — migration head, counts, prod sha256 before==after, idempotency.
- `no-live-no-writeback.md` — local-only / no-external-call proof.
- `no-leak-scan.md` — leak-scan proof over changed code + this bundle.
- `validation-results.md` — targeted / branch-owned / broad results with baseline classification.
