-- Detect same budget_code with concurrent exposure from multiple workflow stages.
-- Read-only aggregate check; does not export raw payloads.

WITH change_event_cost AS (
  SELECT
    project_key,
    budget_code_id,
    COUNT(*) AS ce_line_count,
    SUM(CASE WHEN latest_cost_values_amount IS NOT NULL AND TRIM(latest_cost_values_amount) <> '' THEN 1 ELSE 0 END) AS ce_amount_populated
  FROM procore_ep_change_events_change_items
  WHERE budget_code_id IS NOT NULL
  GROUP BY project_key, budget_code_id
),
rfq_cost AS (
  SELECT
    ce.project_key,
    li.cost_code_id AS budget_code_proxy,
    COUNT(*) AS rfq_line_count
  FROM procore_ep_rfqs_change_event_change_event_line_items li
  JOIN procore_ep_rfqs r ON r.record_key = li.primary_record_key
  JOIN procore_ep_change_events ce ON ce.record_id = r.change_event_id
  WHERE li.cost_code_id IS NOT NULL
  GROUP BY ce.project_key, li.cost_code_id
),
cco_cost AS (
  SELECT
    cc.project_key,
    COUNT(*) AS cco_count
  FROM procore_ep_commitment_change_orders cco
  JOIN procore_ep_commitment_contracts cc ON cc.record_id = cco.contract_id
  GROUP BY cc.project_key
)
SELECT
  ce.project_key,
  ce.budget_code_id,
  ce.ce_line_count,
  COALESCE(r.rfq_line_count, 0) AS rfq_line_count,
  CASE
    WHEN ce.ce_amount_populated > 0 AND COALESCE(r.rfq_line_count, 0) > 0 THEN 'review_double_count_risk'
    ELSE 'ok'
  END AS risk_flag
FROM change_event_cost ce
LEFT JOIN rfq_cost r
  ON r.project_key = ce.project_key
 AND r.budget_code_proxy = ce.budget_code_id
WHERE ce.ce_amount_populated > 0
ORDER BY risk_flag DESC, ce.project_key
LIMIT 500;