-- PO relationship validation (read-only, no raw payloads)
-- Classifies all PO line items by parent resolution path.

SELECT
  li.record_id AS line_item_record_id,
  li.project_key,
  li.holder_id,
  CASE
    WHEN poc.record_id IS NOT NULL THEN 'matched_po_contract'
    WHEN cc.record_id IS NOT NULL THEN 'matched_commitment_contract'
    ELSE 'unresolved'
  END AS parent_classification,
  poc.record_id AS po_contract_record_id,
  cc.record_id AS commitment_contract_record_id
FROM procore_ep_purchase_order_line_items li
LEFT JOIN procore_ep_purchase_order_contracts poc
  ON poc.record_id = li.holder_id
LEFT JOIN procore_ep_commitment_contracts cc
  ON cc.record_id = li.holder_id
ORDER BY parent_classification, li.project_key, li.record_id;

-- Summary counts (expect 16 matched_po_contract, 12 matched_commitment_contract, 0 unresolved)
SELECT
  CASE
    WHEN poc.record_id IS NOT NULL THEN 'matched_po_contract'
    WHEN cc.record_id IS NOT NULL THEN 'matched_commitment_contract'
    ELSE 'unresolved'
  END AS parent_classification,
  COUNT(*) AS line_item_count
FROM procore_ep_purchase_order_line_items li
LEFT JOIN procore_ep_purchase_order_contracts poc ON poc.record_id = li.holder_id
LEFT JOIN procore_ep_commitment_contracts cc ON cc.record_id = li.holder_id
GROUP BY parent_classification
ORDER BY line_item_count DESC;