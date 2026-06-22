# Procore Listed Tables Null Field Audit

- DB path: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Generated UTC: `2026-06-21T09:23:39.158595+00:00`
- Majority-null threshold: `50.0%`
- Shareable audit raw payload/body values emitted: no
- Full package raw payload samples included: yes, under `sensitive-raw-payload-samples/`
- Raw sample rule: top 3 longest non-empty `procore_endpoint_raw_payloads.payload_json` values per corresponding endpoint.
- Non-null value examples in shareable audit: hashed fingerprints only

## Table to Endpoint Mapping

| Table | Corresponding endpoint key(s) |
|---|---|
| `procore_ep_budget_detail_rows` | `budget-detail-rows` |
| `procore_ep_budget_detail_row_cells` | `budget-detail-rows` |
| `procore_ep_budget_detail_columns` | `budget-detail-columns` |
| `procore_ep_budget_change_history` | `budget-change-history` |
| `procore_ep_billing_periods` | `billing-periods` |
| `procore_ep_budget_modifications` | `budget-modifications` |

## Row Counts

| Table | Rows | Exists |
|---|---:|---|
| `procore_ep_budget_detail_rows` | 3044 | True |
| `procore_ep_budget_detail_row_cells` | 273951 | True |
| `procore_ep_budget_detail_columns` | 399 | True |
| `procore_ep_budget_change_history` | 420 | True |
| `procore_ep_billing_periods` | 66 | True |
| `procore_ep_budget_modifications` | 805 | True |

## Majority-Null Fields

| Table | Column | Missing | Nonblank | Missing % | Distinct nonblank |
|---|---|---:|---:|---:|---:|
| `procore_ep_billing_periods` | `parent_record_id` | 66 | 0 | 100.0 | 0 |
| `procore_ep_billing_periods` | `parent_record_id_hash` | 66 | 0 | 100.0 | 0 |
| `procore_ep_billing_periods` | `payload_sidecar_json` | 66 | 0 | 100.0 | 0 |
| `procore_ep_budget_change_history` | `parent_record_id` | 420 | 0 | 100.0 | 0 |
| `procore_ep_budget_change_history` | `parent_record_id_hash` | 420 | 0 | 100.0 | 0 |
| `procore_ep_budget_change_history` | `payload_sidecar_json` | 420 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_columns` | `visible` | 399 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_row_cells` | `currency_iso_code` | 273951 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_row_cells` | `column_id` | 258385 | 15566 | 94.317962 | 25 |
| `procore_ep_budget_detail_row_cells` | `column_key` | 258385 | 15566 | 94.317962 | 12 |
| `procore_ep_budget_detail_rows` | `actual_cost` | 3044 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_rows` | `cost_type` | 3044 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_rows` | `cost_type_id` | 3044 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_rows` | `line_item_type_id` | 3044 | 0 | 100.0 | 0 |
| `procore_ep_budget_detail_rows` | `direct_costs` | 2522 | 522 | 82.851511 | 339 |
| `procore_ep_budget_detail_rows` | `erp_direct_costs` | 2088 | 956 | 68.593955 | 377 |
| `procore_ep_budget_detail_rows` | `erp_job_to_date_costs` | 2088 | 956 | 68.593955 | 480 |
| `procore_ep_budget_detail_rows` | `forecast_to_complete` | 2000 | 1044 | 65.703022 | 425 |
| `procore_ep_budget_detail_rows` | `committed_costs` | 1566 | 1478 | 51.445466 | 144 |
| `procore_ep_budget_detail_rows` | `pending_budget_changes` | 1566 | 1478 | 51.445466 | 35 |
| `procore_ep_budget_modifications` | `origin_data` | 805 | 0 | 100.0 | 0 |
| `procore_ep_budget_modifications` | `origin_id` | 805 | 0 | 100.0 | 0 |
| `procore_ep_budget_modifications` | `parent_record_id` | 805 | 0 | 100.0 | 0 |
| `procore_ep_budget_modifications` | `parent_record_id_hash` | 805 | 0 | 100.0 | 0 |
| `procore_ep_budget_modifications` | `payload_sidecar_json` | 805 | 0 | 100.0 | 0 |

## All-Null Fields

| Table | Column | Rows |
|---|---|---:|
| `procore_ep_billing_periods` | `parent_record_id` | 66 |
| `procore_ep_billing_periods` | `parent_record_id_hash` | 66 |
| `procore_ep_billing_periods` | `payload_sidecar_json` | 66 |
| `procore_ep_budget_change_history` | `parent_record_id` | 420 |
| `procore_ep_budget_change_history` | `parent_record_id_hash` | 420 |
| `procore_ep_budget_change_history` | `payload_sidecar_json` | 420 |
| `procore_ep_budget_detail_columns` | `visible` | 399 |
| `procore_ep_budget_detail_row_cells` | `currency_iso_code` | 273951 |
| `procore_ep_budget_detail_rows` | `actual_cost` | 3044 |
| `procore_ep_budget_detail_rows` | `cost_type` | 3044 |
| `procore_ep_budget_detail_rows` | `cost_type_id` | 3044 |
| `procore_ep_budget_detail_rows` | `line_item_type_id` | 3044 |
| `procore_ep_budget_modifications` | `origin_data` | 805 |
| `procore_ep_budget_modifications` | `origin_id` | 805 |
| `procore_ep_budget_modifications` | `parent_record_id` | 805 |
| `procore_ep_budget_modifications` | `parent_record_id_hash` | 805 |
| `procore_ep_budget_modifications` | `payload_sidecar_json` | 805 |

## All Fields With Any Null/Blank Values

| Table | Column | Missing | Nonblank | Missing % |
|---|---|---:|---:|---:|
| `procore_ep_billing_periods` | `parent_record_id` | 66 | 0 | 100.0 |
| `procore_ep_billing_periods` | `parent_record_id_hash` | 66 | 0 | 100.0 |
| `procore_ep_billing_periods` | `payload_sidecar_json` | 66 | 0 | 100.0 |
| `procore_ep_budget_change_history` | `parent_record_id` | 420 | 0 | 100.0 |
| `procore_ep_budget_change_history` | `parent_record_id_hash` | 420 | 0 | 100.0 |
| `procore_ep_budget_change_history` | `payload_sidecar_json` | 420 | 0 | 100.0 |
| `procore_ep_budget_detail_columns` | `visible` | 399 | 0 | 100.0 |
| `procore_ep_budget_detail_row_cells` | `currency_iso_code` | 273951 | 0 | 100.0 |
| `procore_ep_budget_detail_row_cells` | `column_id` | 258385 | 15566 | 94.317962 |
| `procore_ep_budget_detail_row_cells` | `column_key` | 258385 | 15566 | 94.317962 |
| `procore_ep_budget_detail_row_cells` | `value_decimal_text` | 117785 | 156166 | 42.994915 |
| `procore_ep_budget_detail_rows` | `actual_cost` | 3044 | 0 | 100.0 |
| `procore_ep_budget_detail_rows` | `cost_type` | 3044 | 0 | 100.0 |
| `procore_ep_budget_detail_rows` | `cost_type_id` | 3044 | 0 | 100.0 |
| `procore_ep_budget_detail_rows` | `line_item_type_id` | 3044 | 0 | 100.0 |
| `procore_ep_budget_detail_rows` | `direct_costs` | 2522 | 522 | 82.851511 |
| `procore_ep_budget_detail_rows` | `erp_direct_costs` | 2088 | 956 | 68.593955 |
| `procore_ep_budget_detail_rows` | `erp_job_to_date_costs` | 2088 | 956 | 68.593955 |
| `procore_ep_budget_detail_rows` | `forecast_to_complete` | 2000 | 1044 | 65.703022 |
| `procore_ep_budget_detail_rows` | `committed_costs` | 1566 | 1478 | 51.445466 |
| `procore_ep_budget_detail_rows` | `pending_budget_changes` | 1566 | 1478 | 51.445466 |
| `procore_ep_budget_detail_rows` | `job_to_date_costs` | 1478 | 1566 | 48.554534 |
| `procore_ep_budget_detail_rows` | `approved_change_orders` | 522 | 2522 | 17.148489 |
| `procore_ep_budget_detail_rows` | `estimated_cost_at_completion` | 522 | 2522 | 17.148489 |
| `procore_ep_budget_detail_rows` | `projected_budget` | 522 | 2522 | 17.148489 |
| `procore_ep_budget_detail_rows` | `projected_costs` | 522 | 2522 | 17.148489 |
| `procore_ep_budget_detail_rows` | `projected_over_under` | 522 | 2522 | 17.148489 |
| `procore_ep_budget_detail_rows` | `revised_budget` | 522 | 2522 | 17.148489 |
| `procore_ep_budget_modifications` | `origin_data` | 805 | 0 | 100.0 |
| `procore_ep_budget_modifications` | `origin_id` | 805 | 0 | 100.0 |
| `procore_ep_budget_modifications` | `parent_record_id` | 805 | 0 | 100.0 |
| `procore_ep_budget_modifications` | `parent_record_id_hash` | 805 | 0 | 100.0 |
| `procore_ep_budget_modifications` | `payload_sidecar_json` | 805 | 0 | 100.0 |
| `procore_ep_budget_modifications` | `notes` | 44 | 761 | 5.465839 |
