# Batch A Punch Items Replay Proof

## Summary

- Batch A fields: `procore_ep_punch_items.closed_at`, `procore_ep_punch_items.closed_by`
- Implementation patch required: `no`
- Accepted remediation type: endpoint-specific projection replay/backfill
- Production DB modified by this proof: `yes, endpoint-limited local projection replay only`
- Copied DB replay performed: `yes`
- Raw payload values emitted: `no`

## Local Source-Path Evidence

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.closed_at` | 36 | 36 | 13 | 0 |
| `$.closed_by` | 36 | 36 | 13 | 0 |

## Copied DB Counts

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| punch rows | 23 | 36 | 13 |
| closed_at non-null | 0 | 13 | 13 |
| closed_by non-null | 0 | 13 | 13 |
| Budget Detail rows | 2496 | 2496 | 0 |
| Budget Detail row cells | 225131 | 225131 | 0 |

## Production DB Counts

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| punch rows | 23 | 36 | 13 |
| closed_at non-null | 0 | 13 | 13 |
| closed_by non-null | 0 | 13 | 13 |
| Budget Detail rows | 2496 | 2496 | 0 |
| Budget Detail row cells | 225131 | 225131 | 0 |

## Guardrails

- No schema migration was applied.
- No registry or projection code patch was applied.
- No live calls were made.
- Production write scope was limited to local SQLite projection replay for endpoint `punch-items`.
- No scheduler or SourceRefreshOrchestrator path was called.
- No Procore writeback was performed.
- Budget Detail refresh/reconciliation remains unchanged.
- Raw payload bodies, fragments, and values were not emitted.
