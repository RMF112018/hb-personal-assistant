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

-- ERP sidecar vs Procore cumulative (report only; not interchangeable)
SELECT project_key, budget_code AS budget_code_key,
       actual_cost, erp_job_to_date_costs, erp_direct_costs
FROM procore_ep_budget_detail_rows
WHERE (erp_job_to_date_costs IS NOT NULL AND TRIM(erp_job_to_date_costs) <> '')
   OR (erp_direct_costs IS NOT NULL AND TRIM(erp_direct_costs) <> '')
LIMIT 500;