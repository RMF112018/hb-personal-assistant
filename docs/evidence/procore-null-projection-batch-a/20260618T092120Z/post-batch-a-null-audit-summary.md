# Post-Batch-A Null Audit Summary

- Suspected projection defects: `123`
- All-null fields: `579`
- Expected optional fields: `279`

## Batch A Target Fields

| Field | Rows | Non-Null | Suspected Defect | Root Cause |
| --- | ---: | ---: | --- | --- |
| `procore_ep_punch_items.closed_at` | 36 | 13 | `false` | `source_payload_missing_or_endpoint_not_refreshed` |
| `procore_ep_punch_items.closed_by` | 36 | 13 | `false` | `source_payload_missing_or_endpoint_not_refreshed` |
