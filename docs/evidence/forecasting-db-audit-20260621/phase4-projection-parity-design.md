# Phase 4 Projection Parity Design

## Scope

Compare `procore_ep_*` endpoint projections with `procore_financial_*` enriched contracts for:

- commitments (`procore_ep_commitment_contracts` ↔ `procore_financial_contracts`)
- purchase orders (`procore_ep_purchase_order_contracts` ↔ `procore_financial_contracts`)

## Checks per pair

| Check | Severity (warn) | Notes |
|-------|-----------------|-------|
| `row_count_mismatch` | warning | PO uses adjusted count excluding commitment-backed financial-only keys |
| `missing_target_keys` | warning | EP keys absent from financial layer |
| `expected_financial_only_keys` | info | Commitment-backed PO enrichment |
| `missing_source_keys` | warning | Unexpected financial-only keys |
| `status_field_mismatch` | warning | Normalized status compare on shared keys |
| `amount_field_mismatch` | warning | `grand_total` text compare; hashed key samples only |
| `updated_field_mismatch` | info | `updated_at` vs `updated_at_utc` |

## Safety

- No raw payload export
- Key samples are SHA-256 truncated hashes (`project_key:contract_id`)
- Amounts compared per-record but only mismatch **counts** and hashed keys reported

## Modes

- **warn** (default): informational expected drift stays info; actionable drift warns
- **strict**: warnings promoted to errors (readiness/operator triage)

## Future pairs (backlog)

Prime contracts, change events, RFQs, subcontractor invoices, budget details — require stable EP↔financial key mapping evidence before enabling.