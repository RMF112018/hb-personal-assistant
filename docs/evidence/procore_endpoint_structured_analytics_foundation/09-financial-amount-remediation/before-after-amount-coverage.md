# Before / after amount-coverage matrix

Generated from a **timestamped `/tmp` copy** of the production DB (read-only; copy only).
"Before" = freshly migrated copy (structured tables empty). "After" = idempotent
`backfill_from_live_records(apply=True)` (run twice). Verdict applies the acceptance rule:
*any table with source rows containing mapped monetary fields but 0% amount coverage is a
**BLOCKER***; a table may only remain 0% when it has no source rows or the source rows lack
monetary fields.

| structured_table | rows | non_null_amount | amount_coverage_pct | source_rows | sampled_source_money_fields | before% | verdict |
|---|---:|---:|---:|---:|---|---:|---|
| procore_raw_invoice_items | 13136 | 13136 | 100.0 | 13136 | work_completed_this_period, total_completed_and_stored_to_date, subcontractor_claimed_amount, scheduled_value | 0.0 | PASS |
| procore_raw_invoices | 220 | 220 | 100.0 | 220 | total_claimed_amount, summary.current_payment_due, summary.contract_sum_to_date, summary.total_completed_and_stored_to_date | 0.0 | PASS |
| procore_raw_change_orders | 164 | 164 | 100.0 | 164 | grand_total | 0.0 | PASS |
| procore_raw_change_order_line_items | 274 | 274 | 100.0 | 274 | amount | 0.0 | PASS (non-regressed) |
| procore_raw_contract_line_items | 393 | 393 | 100.0 | 393 | amount | 0.0 | PASS (non-regressed) |
| procore_raw_budget_rows | 1182 | 1182 | 100.0 | 1182 | original_budget_amount | 0.0 | PASS (non-regressed) |
| procore_raw_payment_applications | 0 | 0 | 0.0 | 0 | — | 0.0 | SOURCE-ABSENT (no source rows) |

**Blockers: none.**

- The three previously-0% financial families (`invoice_items` 13,136 rows, `invoices`,
  `change_orders`) now populate `amount` at 100%.
- Generic-fallback tables (`*_line_items`, `budget_rows`) reach 100% and are **not regressed**
  (unit test `test_amount_generic_fallback_preserved_for_existing_tables` guards the mapping).
- `procore_raw_change_orders` `amount` = `grand_total` (e.g. `491383.15`); the co-present
  `schedule_impact_amount` day-count is correctly **not** used.
- `procore_raw_payment_applications`: no `payment-applications` endpoint exists in the source
  (0 source rows) → classified **source-absent**, not extraction-failed.

> "before%" is 0.0 for every table because the matrix re-runs on a freshly migrated copy where
> structured tables start empty; the decisive comparison is the previously-reported 0% on the
> financial families vs. 100% after this remediation, and the no-blocker verdict.
