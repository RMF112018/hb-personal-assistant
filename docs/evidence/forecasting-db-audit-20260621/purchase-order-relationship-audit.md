# Purchase Order Relationship Audit

**Date:** 2026-06-21  
**Evidence:** `docs/evidence/forecasting-db-complete-evidence/20260621T114232Z/`  
**DB:** local SQLite (read-only queries; no raw payloads exported)

## Summary

All **28** `procore_ep_purchase_order_line_items` rows are classified. **Zero** are truly unresolved.

| Classification | Count | Evidence basis |
|----------------|-------|----------------|
| `matched_po_contract` | 16 | row-profile-supported |
| `matched_commitment_contract` | 12 | row-profile-supported |
| `unresolved` | 0 | — |

## Root cause of apparent 12/28 unmatched join

The evidence package join tested only:

```
purchase_order_contracts.record_id → purchase_order_line_items.holder_id
```

Twelve line items have `holder_id` values that match `procore_ep_commitment_contracts.record_id`, not PO contracts:

| Project | PO contracts | Unmatched-to-PO holder_ids | Commitment match |
|---------|-------------|---------------------------|------------------|
| caretta | 0 | 11567828, 11574438, 13293281 | all 10 lines match commitments |
| rybovich | 1 (13519613) | 14359852 | 1 line matches commitment 14359852 |
| tropical | 9 | — | all 7 tropical PO-holder lines match PO contracts |

## Conclusion

This is **not a projection defect**. It is a **polymorphic holder pattern**:

- Procore PO line items can reference commitment contract IDs as `holder_id`
- Repo code already anticipates PO/commitment overlap via `duplicate_of_commitment` dedup in `procore_commitment_projection.py`

## Canonical parent key recommendation

1. **Primary:** `holder_id` → `procore_ep_purchase_order_contracts.record_id`
2. **Fallback:** `holder_id` → `procore_ep_commitment_contracts.record_id`
3. **`parent_record_id`:** mirrors `holder_id` in all 28 rows (redundant)

**Confidence:** medium (row-profile-supported; Procore-doc-supported pending)

## Exposure model recommendation

- Maintain separate `fact_purchase_order_exposure` for lines resolving to PO contracts
- Route commitment-holder lines to `fact_commitment_exposure`
- Do **not** fold all PO lines into commitment exposure blindly — tropical PO lines are genuine PO contracts
- Apply existing repo dedup when PO contract shares `contract_id` with commitment

## Validation query

`docs/forecasting/semantic-catalog/validation_queries/purchase_order_relationships.sql`