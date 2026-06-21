# Purchase Order Projection Drift Audit

## Summary

Live-copy audit (`docs/evidence/forecasting-gates-live-copy-20260621T133000Z/live-copy.sqlite`, read-only):

| Metric | Value |
|--------|-------|
| EP `procore_ep_purchase_order_contracts` keys | 11 |
| Financial `purchase_order` contract keys | 16 |
| Shared keys | 11 |
| Financial-only keys | 5 |

## Classification (all 5 financial-only keys)

| # | project_key | contract_id_hash | financial_status | Classification |
|---|-------------|------------------|------------------|----------------|
| 1 | caretta | 569cc15064cb0916 | Closed | commitment_backed_po |
| 2 | caretta | a01e7f0872817f4a | Approved | commitment_backed_po |
| 3 | caretta | b6415ed5c15763e6 | Approved | commitment_backed_po |
| 4 | pga-modern-garage | 49475618b40069a0 | Approved | commitment_backed_po |
| 5 | rybovich | 71209725aac2d23b | Approved | commitment_backed_po |

**Decision:** All 5 are **expected financial enrichment**, not projection defects.

## Evidence basis

Each financial-only PO key has the same `contract_id` present in:

- `procore_financial_contracts` with `contract_family = 'commitment'`
- `procore_ep_commitment_contracts`

But is absent from `procore_ep_purchase_order_contracts`.

## Projection code path

`src/hb_assistant/store/procore_commitment_projection.py::_project_purchase_order`

- Writes PO to `procore_financial_contracts` (`contract_family = purchase_order`) even when `_commitment_exists()` is true
- Sets `duplicate_of_commitment` signal in projection result
- Skips amount-fact emission when duplicate to avoid double-counting committed cost

EP PO endpoint rows are not guaranteed when the contract is commitment-primary — financial layer retains PO family row for enrichment/traceability.

## Gate impact

Projection parity gate now:

- Classifies commitment-backed financial-only PO keys as `expected_financial_only_keys` (severity **info**)
- Adjusts PO row-count comparison using `financial_row_count_adjusted`

## Machine evidence

`docs/evidence/forecasting-db-audit-20260621/purchase-order-projection-drift-evidence.json`

## Regeneration

```bash
python3 scripts/audit_po_projection_drift.py \
  --db-path docs/evidence/forecasting-gates-live-copy-20260621T133000Z/live-copy.sqlite \
  --json-out docs/evidence/forecasting-db-audit-20260621/purchase-order-projection-drift-evidence.json
```