# 03 — Full raw fixture persistence proof

Fixture: a full `prime-change-orders` item with nested business objects (`created_by`,
`vendor`, `wbs_code`, `custom_fields`, `attachments`) plus transport secrets
(`authorization`, `access_token`, signed `download_url`).

| endpoint | raw rows | structured table | structured rows | source_quality | raw_procore_payload_persisted | verdict |
|---|---:|---|---:|---|---:|---|
| prime-change-orders | 1 | procore_raw_change_orders | 1 | live_full_payload | 1 | PASS |
| subcontractor-invoice-contract-detail-items | 1 | procore_raw_invoice_items | 1 | live_full_payload | 1 | PASS |
| subcontractor-invoices | 1 | procore_raw_invoices | 1 | live_full_payload | 1 | PASS |
| rfis | 1 | procore_raw_rfis | 1 | live_full_payload | 1 | PASS |

## Business fields preserved in `payload_json` (private DB)

`grand_total`, `created_by.name`, `vendor.name`, `wbs_code.flat_code`,
`custom_fields.custom_field_1.value`, `attachments[].name`, and the non-credential
attachment URL path (`storage.procore.com/...`). Verified by JSON round-trip equality.

## Structured scalars populated from the full payload

| column | source field | populated |
|---|---|---|
| amount | grand_total (not schedule_impact_amount) | yes |
| owner_name | created_by.name | yes |
| cost_code | wbs_code.flat_code | yes |
| record_number | number | yes |
| due_at_utc | due_date | yes |

## Transport secrets NOT stored

`access_token`, `refresh_token`, `client_secret`, `api_key`, `password`, `Bearer …`,
`X-Amz-Signature`, and signed-URL `token=`/`sig=` params are absent from `payload_json`.
Raw row flags: `contains_signed_url=0`, `contains_secret_like_value=0`. Narrow post-scrub
assertion `_has_transport_secret(payload_json)` returns `False`.

(Counts, field names and classifications only — no payload bodies.)
