-- Dual projection parity: procore_ep_* vs procore_financial_* row counts (read-only)

SELECT 'commitment_contracts' AS family,
       (SELECT COUNT(*) FROM procore_ep_commitment_contracts) AS ep_rows,
       (SELECT COUNT(*) FROM procore_financial_contracts WHERE contract_family = 'commitment') AS financial_rows;

SELECT 'purchase_order_contracts' AS family,
       (SELECT COUNT(*) FROM procore_ep_purchase_order_contracts) AS ep_rows,
       (SELECT COUNT(*) FROM procore_financial_contracts WHERE contract_family = 'purchase_order') AS financial_rows;