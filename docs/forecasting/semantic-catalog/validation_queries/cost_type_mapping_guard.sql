-- Cost type population and category guard (read-only).
-- category/category_id MUST NOT be treated as cost_type/cost_type_id without explicit evidence.

SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN cost_type IS NOT NULL AND TRIM(cost_type) <> '' THEN 1 ELSE 0 END) AS cost_type_populated,
       SUM(CASE WHEN category IS NOT NULL AND TRIM(category) <> '' THEN 1 ELSE 0 END) AS category_populated,
       ROUND(1.0 - (1.0 * SUM(CASE WHEN cost_type IS NOT NULL AND TRIM(cost_type) <> '' THEN 1 ELSE 0 END) / COUNT(*)), 4) AS cost_type_null_rate
FROM procore_ep_budget_detail_rows;