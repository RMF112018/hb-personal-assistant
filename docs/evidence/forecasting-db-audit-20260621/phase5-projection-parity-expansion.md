# Phase 5 Projection Parity Expansion

Evidence JSON: `phase5-projection-parity-evidence.json`

## Supported pairs (live copy)

| Family | EP table | Financial table | EP rows | Financial rows | Parity |
|--------|----------|-----------------|---------|----------------|--------|
| commitment | `procore_ep_commitment_contracts` | `procore_financial_contracts` (family=commitment) | 243 | 243 | OK (Phase 4) |
| purchase_order | `procore_ep_purchase_order_contracts` | `procore_financial_contracts` (family=purchase_order) | 16 | 16 (+5 expected commitment-backed) | OK (Phase 4) |
| prime | `procore_ep_prime_contracts` | `procore_financial_contracts` (family=owner) | 7 | 7 | **Match** |
| change_event | `procore_ep_change_events` | `procore_financial_change_events` | 1059 | 1059 | **Match** |
| subcontractor_invoice | `procore_ep_subcontractor_invoices` | `procore_financial_subcontractor_invoices` | 1002 | 1002 | **Match** |

## Unsupported / scoped pairs

| Family | EP rows | Financial rows | Status |
|--------|---------|----------------|--------|
| rfq | 12 | 291 | **unsupported_ep_scope_subset** — financial projection scope exceeds current EP rfqs endpoint sync; reported as info, not silent skip |

## Gate enhancements

- `parity_kind`: `contract_family` (contracts) or `direct_id` (change events, invoices, RFQs)
- Per-record checks: status, amount (where EP field exists), updated timestamp
- `pairs_unsupported` counter for explicitly documented non-parity pairs
- Hashed key samples only — no raw IDs in gate output beyond counts

## Next actions

1. Investigate RFQ financial projection scope (291 vs 12 EP records) before enabling strict RFQ parity.
2. Add prime change-order line item parity when enriched financial equivalents are confirmed.