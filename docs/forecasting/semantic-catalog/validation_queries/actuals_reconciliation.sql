-- Actuals reconciliation (read-only). Compare sources; never sum all fields together.

-- Cumulative budget actual vs periodized monthly actual (materiality evaluated in gate code)
SELECT b.project_key, b.budget_code AS budget_code_key,
       b.actual_cost AS budget_cumulative_actual,
       m.amount AS monthly_actual, m.month
FROM procore_ep_budget_detail_rows b
JOIN forecast_monthly_actuals_by_budget_code m
  ON m.project_key = b.project_key AND m.budget_code_key = b.budget_code
WHERE b.actual_cost IS NOT NULL AND TRIM(b.actual_cost) <> ''
  AND m.amount IS NOT NULL AND TRIM(m.amount) <> ''
LIMIT 500;

-- ERP sidecar vs Procore job-to-date (aggregate compare only; not interchangeable)
SELECT project_key,
       COUNT(*) AS compared_rows,
       SUM(ABS(CAST(job_to_date_costs AS REAL) - CAST(erp_job_to_date_costs AS REAL))) AS abs_diff_sum
FROM procore_ep_budget_detail_rows
WHERE job_to_date_costs IS NOT NULL AND TRIM(job_to_date_costs) <> ''
  AND erp_job_to_date_costs IS NOT NULL AND TRIM(erp_job_to_date_costs) <> ''
GROUP BY project_key;

-- Invoice detail vs budget code coverage (counts only)
SELECT b.project_key, b.budget_code AS budget_code_key,
       COUNT(DISTINCT b.record_key) AS budget_rows,
       COUNT(DISTINCT i.detail_line_item_id) AS invoice_detail_rows
FROM procore_ep_budget_detail_rows b
JOIN procore_ep_subcontractor_invoice_contract_detail_items i
  ON CAST(i.cost_code_id AS TEXT) = CAST(b.budget_code_id AS TEXT)
WHERE b.job_to_date_costs IS NOT NULL AND TRIM(b.job_to_date_costs) <> ''
GROUP BY b.project_key, b.budget_code
LIMIT 200;

-- Payment timing population (cash-flow facts)
SELECT COUNT(*) AS invoice_count,
       SUM(CASE WHEN payment_date IS NOT NULL AND TRIM(payment_date) <> '' THEN 1 ELSE 0 END) AS payment_date_pop
FROM procore_ep_subcontractor_invoices;