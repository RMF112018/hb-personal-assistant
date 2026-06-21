# Procore Budget Detail Complete Remediation Evidence

## Scope

- Copied DB only: `/tmp/hb-budget-detail-complete-remediation-proof.sqlite`.
- Live DB mutation: no.
- Live Procore calls: no.
- External writeback: no.
- Scheduler changes: no.
- Raw payload body emission: no.

## What Was Broken

- Full raw payload persistence was not carrying known `procore_live_sync_runs.company_id` into `procore_endpoint_raw_payloads`.
- Full raw landing allowed multiple current rows for the same stable record key when payload hashes changed.
- Budget Detail rows had source-backed `category/category_id` data available in raw payloads/cells, but no explicit row columns to preserve it.

## What Was Intentionally Not Changed

- Dynamic amount aliases were not modified.
- `cost_type/cost_type_id` were not populated from `category/category_id`; they remain literal-source-only fields.
- `actual_cost` remains null because current evidence has no literal Actual Cost source.
- `line_item_type_id` remains null because current evidence has no literal source.

## Proof Files

- `db-integrity-check.txt`: `ok`
- `reconciliation-receipt.json`: copied-DB raw company/current reconciliation succeeded.
- `budget-detail-read-model-replay-receipt.json`: copied-DB Budget Detail replay succeeded.
- `company-id-propagation-proof.json`: all target full raw rows have company id and hash.
- `budget-detail-row-company-proof.json`: all Budget Detail read-model rows have company id and hash.
- `raw-current-version-proof.json`: no stable Budget Detail raw key has zero or multiple current rows.
- `raw-to-read-model-linkage-proof.json`: no stable Budget Detail raw key is missing from the read model.
- `budget-detail-category-proof.json`: all Budget Detail read-model rows have category, category id, and category hash; cost type fields remain null.
- `source-absent-field-proof.json`: `actual_cost` and `line_item_type_id` remain null.
- `amount-reconciliation-proof.json`: dynamic amount mappings still have zero missing-wide and zero mismatch counts.
- `no-raw-leak-scan.json`: `ok=true`, zero findings.
