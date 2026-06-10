# 05 — Structured null-rate matrix (full vs redacted)

Same logical `prime-change-orders` record projected two ways: from the full live payload
vs from a redacted legacy projection that omits the financial/owner fields.

| table | endpoint | source_quality | rows | critical_fields_checked | before_null_pct | after_null_pct | verdict |
|---|---|---|---:|---|---:|---:|---|
| procore_raw_change_orders | prime-change-orders | redacted_legacy_projection | 1 | amount, owner_name | 100% | 100% | NULL (degraded) |
| procore_raw_change_orders | prime-change-orders | live_full_payload | 1 | amount, owner_name | 100% | 0% | POPULATED |
| procore_raw_invoice_items | subcontractor-invoice-contract-detail-items | live_full_payload | 1 | amount | — | 0% | POPULATED (14000.00) |
| procore_raw_invoices | subcontractor-invoices | live_full_payload | 1 | amount | — | 0% | POPULATED (3103000.00) |

`before_null_pct` = redacted-projection null rate for the critical field;
`after_null_pct` = full-payload null rate. Full payloads drive the critical business
fields (amount, owner_name, cost_code, dates) to 0% null where the redacted projection
leaves them 100% null.

## Placeholder handling

`test_placeholder_strings_do_not_populate_scalars`: a full payload with
`owner="[redacted]"`, `amount="null"`, `cost_code=""`, `status={}`, `assignee="[scrubbed]"`
yields all-NULL structured scalars, while the stored `payload_json` still contains the
literal `[redacted]`/`[scrubbed]` strings (not mutated).

## Financial non-regression

`grand_total` (change orders, excludes schedule day-count), `work_completed_this_period`
(invoice items), `total_claimed_amount` (invoices) all extract correctly from full
payloads; the existing financial-amount foundation tests pass unchanged.

(Counts and percentages only — no payload bodies or private values.)
