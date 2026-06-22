# Procore Change Events Null Field Audit

- DB path: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Generated UTC: `2026-06-21T09:30:13.102127+00:00`
- Majority-null threshold: `50.0%`
- Shareable audit raw payload/body values emitted: no
- Full package raw payload samples included: yes, under `sensitive-raw-payload-samples/`
- Raw sample rule: top 3 longest non-empty `procore_endpoint_raw_payloads.payload_json` values for `change-events`.
- Non-null value examples in shareable audit: hashed fingerprints only

## Table to Endpoint Mapping

| Table | Corresponding endpoint key(s) |
|---|---|
| `procore_ep_change_events` | `change-events` |
| `procore_ep_change_events_attachments` | `change-events` |
| `procore_ep_change_events_change_items` | `change-events` |
| `procore_ep_change_events_change_items_budget_code_seg_2dff22` | `change-events` |
| `procore_ep_change_events_markup_items` | `change-events` |
| `procore_ep_change_events_markup_items_wbs_code_segment_items` | `change-events` |

## Row Counts

| Table | Rows | Exists |
|---|---:|---|
| `procore_ep_change_events` | 1059 | True |
| `procore_ep_change_events_attachments` | 2352 | True |
| `procore_ep_change_events_change_items` | 2829 | True |
| `procore_ep_change_events_change_items_budget_code_seg_2dff22` | 8487 | True |
| `procore_ep_change_events_markup_items` | 2154 | True |
| `procore_ep_change_events_markup_items_wbs_code_segment_items` | 6462 | True |

## Majority-Null Fields

| Table | Column | Missing | Nonblank | Missing % | Distinct nonblank |
|---|---|---:|---:|---:|---:|
| `procore_ep_change_events` | `currency_configuration_currency_iso_code` | 1059 | 0 | 100.0 | 0 |
| `procore_ep_change_events` | `deleted_at` | 1059 | 0 | 100.0 | 0 |
| `procore_ep_change_events` | `external_data` | 1059 | 0 | 100.0 | 0 |
| `procore_ep_change_events` | `parent_record_id` | 1059 | 0 | 100.0 | 0 |
| `procore_ep_change_events` | `parent_record_id_hash` | 1059 | 0 | 100.0 | 0 |
| `procore_ep_change_events` | `source` | 1059 | 0 | 100.0 | 0 |
| `procore_ep_change_events` | `event_origin` | 1054 | 5 | 99.527856 | 5 |
| `procore_ep_change_events` | `event_origin_display_name` | 915 | 144 | 86.402266 | 132 |
| `procore_ep_change_events` | `event_origin_origin_id` | 915 | 144 | 86.402266 | 132 |
| `procore_ep_change_events_attachments` | `parent_item_id` | 2352 | 0 | 100.0 | 0 |
| `procore_ep_change_events_attachments` | `payload_sidecar_json` | 2352 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_change` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_base_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_currency_exchange_rate` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_non_commitment_amount` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_base_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_currency_exchange_rate` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `deleted_at` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `parent_item_id` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_base_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_currency_exchange_rate` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 | 0 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_amount` | 2820 | 9 | 99.681866 | 9 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_budget_modification_id` | 2820 | 9 | 99.681866 | 9 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_notes` | 2820 | 9 | 99.681866 | 9 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_from_id` | 2820 | 9 | 99.681866 | 3 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_from_name` | 2820 | 9 | 99.681866 | 3 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_to_id` | 2820 | 9 | 99.681866 | 6 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_to_name` | 2820 | 9 | 99.681866 | 6 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_latest_quote_amount` | 2657 | 172 | 93.920113 | 100 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_latest_quote_amount_project_currency` | 2657 | 172 | 93.920113 | 100 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_contract_id` | 2539 | 290 | 89.749028 | 41 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_days_in_stage` | 2539 | 290 | 89.749028 | 77 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_id` | 2539 | 290 | 89.749028 | 290 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_in_status_since` | 2539 | 290 | 89.749028 | 265 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_number` | 2539 | 290 | 89.749028 | 28 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_status` | 2539 | 290 | 89.749028 | 5 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_title` | 2539 | 290 | 89.749028 | 93 |
| `procore_ep_change_events_change_items` | `cost_impact_estimate_unit_of_measure` | 2083 | 746 | 73.630258 | 8 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_uom_id` | 2008 | 821 | 70.979145 | 8 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_uom_name` | 2008 | 821 | 70.979145 | 8 |
| `procore_ep_change_events_change_items` | `latest_cost_values_uom_id` | 2007 | 822 | 70.943796 | 8 |
| `procore_ep_change_events_change_items` | `latest_cost_values_uom_name` | 2007 | 822 | 70.943796 | 8 |
| `procore_ep_change_events_markup_items` | `parent_item_id` | 2154 | 0 | 100.0 | 0 |

## All-Null Fields

| Table | Column | Rows |
|---|---|---:|
| `procore_ep_change_events` | `currency_configuration_currency_iso_code` | 1059 |
| `procore_ep_change_events` | `deleted_at` | 1059 |
| `procore_ep_change_events` | `external_data` | 1059 |
| `procore_ep_change_events` | `parent_record_id` | 1059 |
| `procore_ep_change_events` | `parent_record_id_hash` | 1059 |
| `procore_ep_change_events` | `source` | 1059 |
| `procore_ep_change_events_attachments` | `parent_item_id` | 2352 |
| `procore_ep_change_events_attachments` | `payload_sidecar_json` | 2352 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_change` | 2829 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_base_currency_iso_code` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_currency_exchange_rate` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_currency_iso_code` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_non_commitment_amount` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_base_currency_iso_code` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_currency_exchange_rate` | 2829 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_currency_iso_code` | 2829 |
| `procore_ep_change_events_change_items` | `currency_configuration_currency_iso_code` | 2829 |
| `procore_ep_change_events_change_items` | `deleted_at` | 2829 |
| `procore_ep_change_events_change_items` | `parent_item_id` | 2829 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_base_currency_iso_code` | 2829 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_currency_exchange_rate` | 2829 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_currency_iso_code` | 2829 |
| `procore_ep_change_events_markup_items` | `parent_item_id` | 2154 |

## All Fields With Any Null/Blank Values

| Table | Column | Missing | Nonblank | Missing % |
|---|---|---:|---:|---:|
| `procore_ep_change_events` | `currency_configuration_currency_iso_code` | 1059 | 0 | 100.0 |
| `procore_ep_change_events` | `deleted_at` | 1059 | 0 | 100.0 |
| `procore_ep_change_events` | `external_data` | 1059 | 0 | 100.0 |
| `procore_ep_change_events` | `parent_record_id` | 1059 | 0 | 100.0 |
| `procore_ep_change_events` | `parent_record_id_hash` | 1059 | 0 | 100.0 |
| `procore_ep_change_events` | `source` | 1059 | 0 | 100.0 |
| `procore_ep_change_events` | `event_origin` | 1054 | 5 | 99.527856 |
| `procore_ep_change_events` | `event_origin_display_name` | 915 | 144 | 86.402266 |
| `procore_ep_change_events` | `event_origin_origin_id` | 915 | 144 | 86.402266 |
| `procore_ep_change_events` | `description` | 136 | 923 | 12.842304 |
| `procore_ep_change_events` | `source_of_revenue_rom` | 9 | 1050 | 0.849858 |
| `procore_ep_change_events` | `prime_contract_for_estimates_id` | 4 | 1055 | 0.377715 |
| `procore_ep_change_events` | `prime_contract_for_estimates_number` | 4 | 1055 | 0.377715 |
| `procore_ep_change_events` | `prime_contract_for_estimates_title` | 4 | 1055 | 0.377715 |
| `procore_ep_change_events_attachments` | `parent_item_id` | 2352 | 0 | 100.0 |
| `procore_ep_change_events_attachments` | `payload_sidecar_json` | 2352 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_change` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_base_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_currency_exchange_rate` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_non_commitment_amount` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_base_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_currency_exchange_rate` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `deleted_at` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `parent_item_id` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_base_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_currency_exchange_rate` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_currency_configuration_currency_iso_code` | 2829 | 0 | 100.0 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_amount` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_budget_modification_id` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_notes` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_from_id` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_from_name` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_to_id` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `budget_impact_budget_modification_transfer_to_name` | 2820 | 9 | 99.681866 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_latest_quote_amount` | 2657 | 172 | 93.920113 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_latest_quote_amount_project_currency` | 2657 | 172 | 93.920113 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_contract_id` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_days_in_stage` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_id` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_in_status_since` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_number` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_status` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_request_for_quote_title` | 2539 | 290 | 89.749028 |
| `procore_ep_change_events_change_items` | `cost_impact_estimate_unit_of_measure` | 2083 | 746 | 73.630258 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_uom_id` | 2008 | 821 | 70.979145 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_uom_name` | 2008 | 821 | 70.979145 |
| `procore_ep_change_events_change_items` | `latest_cost_values_uom_id` | 2007 | 822 | 70.943796 |
| `procore_ep_change_events_change_items` | `latest_cost_values_uom_name` | 2007 | 822 | 70.943796 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_line_item_holder_id` | 1372 | 1457 | 48.497702 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_days_in_stage` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_id` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_in_status_since` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_line_item_amount` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_line_item_amount_project_currency` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_line_item_id` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_number` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_status` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `cost_impact_commitment_title` | 1370 | 1459 | 48.427006 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_contract_id` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_days_in_stage` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_id` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_in_status_since` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_line_item_amount` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_line_item_amount_project_currency` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_line_item_id` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_number` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_status` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_package_title` | 1359 | 1470 | 48.038176 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_confirmed` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_confirmed_id` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_confirmed_number` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_confirmed_status` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_confirmed_title` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_vendor_confirmed` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_vendor_confirmed_id` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `cost_impact_vendor_confirmed_name` | 1184 | 1645 | 41.852245 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_contract_id` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_contract_number` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_contract_title` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_days_in_stage` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_id` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_in_status_since` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_line_item_amount` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_line_item_amount_project_currency` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_line_item_id` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_number` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_status` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `revenue_impact_change_order_title` | 1066 | 1763 | 37.681159 |
| `procore_ep_change_events_change_items` | `cost_impact_estimate_unit_cost` | 713 | 2116 | 25.203252 |
| `procore_ep_change_events_change_items` | `cost_impact_estimate_quantity` | 705 | 2124 | 24.920467 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_proposed_id` | 579 | 2250 | 20.466596 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_proposed_number` | 579 | 2250 | 20.466596 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_proposed_status` | 579 | 2250 | 20.466596 |
| `procore_ep_change_events_change_items` | `cost_impact_contract_proposed_title` | 579 | 2250 | 20.466596 |
| `procore_ep_change_events_change_items` | `cost_impact_vendor_proposed_id` | 457 | 2372 | 16.154118 |
| `procore_ep_change_events_change_items` | `cost_impact_vendor_proposed_name` | 457 | 2372 | 16.154118 |
| `procore_ep_change_events_change_items` | `latest_cost_values_unit_cost` | 330 | 2499 | 11.664899 |
| `procore_ep_change_events_change_items` | `latest_cost_values_unit_cost_project_currency` | 330 | 2499 | 11.664899 |
| `procore_ep_change_events_change_items` | `latest_cost_values_quantity` | 325 | 2504 | 11.488158 |
| `procore_ep_change_events_change_items` | `revenue_impact_estimate_unit_cost` | 317 | 2512 | 11.205373 |
| `procore_ep_change_events_change_items` | `revenue_impact_estimate_unit_cost_project_currency` | 317 | 2512 | 11.205373 |
| `procore_ep_change_events_change_items` | `revenue_impact_estimate_quantity` | 312 | 2517 | 11.028632 |
| `procore_ep_change_events_change_items` | `description` | 249 | 2580 | 8.801697 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_unit_cost` | 136 | 2693 | 4.807352 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_unit_cost_project_currency` | 136 | 2693 | 4.807352 |
| `procore_ep_change_events_change_items` | `latest_revenue_values_quantity` | 133 | 2696 | 4.701308 |
| `procore_ep_change_events_change_items` | `budget_code_description` | 62 | 2767 | 2.191587 |
| `procore_ep_change_events_change_items` | `budget_code_flat_code` | 62 | 2767 | 2.191587 |
| `procore_ep_change_events_markup_items` | `parent_item_id` | 2154 | 0 | 100.0 |
| `procore_ep_change_events_markup_items` | `wbs_code_description` | 70 | 2084 | 3.249768 |
| `procore_ep_change_events_markup_items` | `wbs_code_flat_code` | 70 | 2084 | 3.249768 |
