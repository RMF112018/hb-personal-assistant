-- Field inventory seed query. Implementation should replace this with the CLI/inventory module.
-- Emits field names/counts only; no raw values.

.headers on
.mode csv

WITH payloads AS (
  SELECT endpoint_key, raw_payload_id, payload_json
  FROM procore_endpoint_raw_payloads
  WHERE raw_procore_payload_persisted = 1
)
SELECT
  endpoint_key,
  '$.' || j.key AS json_path,
  json_type(j.value) AS observed_type,
  COUNT(*) AS occurrence_count
FROM payloads p, json_each(p.payload_json) AS j
GROUP BY endpoint_key, j.key, json_type(j.value)
ORDER BY endpoint_key, json_path;
