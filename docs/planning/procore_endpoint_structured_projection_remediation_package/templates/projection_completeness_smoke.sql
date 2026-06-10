-- Projection completeness smoke checks.
-- Run against a /tmp copy unless deliberately applying after merge.

.headers on
.mode column

SELECT
  source_quality,
  raw_procore_payload_persisted,
  COUNT(*) AS rows
FROM procore_endpoint_raw_payloads
GROUP BY source_quality, raw_procore_payload_persisted
ORDER BY source_quality, raw_procore_payload_persisted;

-- Replace/add endpoint-specific coverage queries as implementation defines tables.
SELECT
  'procore_change_events' AS table_name,
  COUNT(*) AS rows,
  SUM(raw_payload_id IS NOT NULL AND TRIM(raw_payload_id) <> '') AS linked_rows,
  SUM(source_quality = 'live_full_payload') AS live_full_rows
FROM procore_change_events;

SELECT
  'procore_change_event_items' AS table_name,
  COUNT(*) AS rows,
  SUM(change_event_id IS NOT NULL AND TRIM(change_event_id) <> '') AS parent_linked_rows,
  SUM(raw_payload_id IS NOT NULL AND TRIM(raw_payload_id) <> '') AS raw_linked_rows
FROM procore_change_event_items;
