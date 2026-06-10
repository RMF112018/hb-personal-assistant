-- Full raw payload ingestion validation SQL.
-- Use on /tmp DB copies unless Bobby explicitly authorizes production apply.

.headers on
.mode column

SELECT
  source_quality,
  raw_procore_payload_persisted,
  COUNT(*) AS rows
FROM procore_endpoint_raw_payloads
GROUP BY source_quality, raw_procore_payload_persisted
ORDER BY source_quality, raw_procore_payload_persisted;

SELECT
  endpoint_key,
  source_quality,
  raw_procore_payload_persisted,
  COUNT(*) AS rows,
  MAX(payload_seen_last_utc) AS latest_seen
FROM procore_endpoint_raw_payloads
GROUP BY endpoint_key, source_quality, raw_procore_payload_persisted
ORDER BY endpoint_key, source_quality;

SELECT
  'procore_raw_invoice_items' AS table_name,
  source_quality,
  COUNT(*) AS rows,
  SUM(CASE WHEN amount IS NOT NULL AND TRIM(amount) != '' THEN 1 ELSE 0 END) AS non_null_amount,
  ROUND(100.0 * SUM(CASE WHEN amount IS NOT NULL AND TRIM(amount) != '' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS amount_pct
FROM procore_raw_invoice_items
GROUP BY source_quality
UNION ALL
SELECT 'procore_raw_invoices', source_quality, COUNT(*),
  SUM(CASE WHEN amount IS NOT NULL AND TRIM(amount) != '' THEN 1 ELSE 0 END),
  ROUND(100.0 * SUM(CASE WHEN amount IS NOT NULL AND TRIM(amount) != '' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)
FROM procore_raw_invoices
GROUP BY source_quality
UNION ALL
SELECT 'procore_raw_change_orders', source_quality, COUNT(*),
  SUM(CASE WHEN amount IS NOT NULL AND TRIM(amount) != '' THEN 1 ELSE 0 END),
  ROUND(100.0 * SUM(CASE WHEN amount IS NOT NULL AND TRIM(amount) != '' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)
FROM procore_raw_change_orders
GROUP BY source_quality
ORDER BY table_name, source_quality;

SELECT
  endpoint_key,
  COUNT(*) AS suspect_placeholder_payloads
FROM procore_endpoint_raw_payloads
WHERE raw_procore_payload_persisted = 1
  AND (
    payload_json IS NULL
    OR TRIM(payload_json) IN ('', '{}', '[]', 'null', '"NULL"', '"[redacted]"', '"[scrubbed]"')
  )
GROUP BY endpoint_key
ORDER BY suspect_placeholder_payloads DESC;
