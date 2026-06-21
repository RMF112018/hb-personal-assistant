-- Budget dynamic column profiling (read-only). No raw cell values exported.

SELECT budget_view_id, column_id, column_key, name, label, data_type, field_path
FROM procore_ep_budget_detail_columns
WHERE is_current = 1
ORDER BY budget_view_id, position;

-- Numeric cell population by column (counts only)
SELECT column_key, column_name,
       SUM(CASE WHEN value_decimal_text IS NOT NULL AND TRIM(value_decimal_text) <> '' THEN 1 ELSE 0 END) AS numeric_cells,
       COUNT(*) AS total_cells
FROM procore_ep_budget_detail_row_cells
WHERE is_current = 1
GROUP BY column_key, column_name
ORDER BY numeric_cells DESC
LIMIT 200;