-- Dual projection parity: procore_ep_* vs procore_financial_* row counts (read-only)

SELECT 'commitment_contracts' AS family,
       (SELECT COUNT(*) FROM procore_ep_commitment_contracts) AS ep_rows,
       (SELECT COUNT(*) FROM procore_financial_contracts WHERE contract_family = 'commitment') AS financial_rows;

SELECT 'purchase_order_contracts' AS family,
       (SELECT COUNT(*) FROM procore_ep_purchase_order_contracts) AS ep_rows,
       (SELECT COUNT(*) FROM procore_financial_contracts WHERE contract_family = 'purchase_order') AS financial_rows;

-- Financial-only PO keys that are commitment-backed (expected enrichment)
SELECT fin.project_key,
       fin.contract_id,
       'commitment_backed_po' AS classification
FROM procore_financial_contracts fin
LEFT JOIN procore_ep_purchase_order_contracts ep
  ON ep.project_key = fin.project_key AND CAST(ep.record_id AS TEXT) = fin.contract_id
WHERE fin.contract_family = 'purchase_order'
  AND ep.record_id IS NULL
  AND EXISTS (
    SELECT 1 FROM procore_financial_contracts c
    WHERE c.project_key = fin.project_key
      AND c.contract_id = fin.contract_id
      AND c.contract_family = 'commitment'
  )
LIMIT 200;