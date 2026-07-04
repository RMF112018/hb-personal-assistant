# 06 — NAS Read Benchmark

**DB:** `/volume1/personal-assistant/app-support/tmp/sqlite-bench-20260704T072309Z/hb-pa-nas-bench.sqlite`

## Connection

| Metric | p50 | p95 | p99 | max |
|---|---|---|---|---|
| Open/close (×10) | 0.128 ms | 0.234 ms | 0.234 ms | 0.234 ms |

## Metadata queries

| Query | p50 | p95 | p99 |
|---|---|---|---|
| `SELECT MAX(version) FROM schema_migrations` | 0.008 ms | 17.159 ms | 17.159 ms |
| Table count (`sqlite_master`) | 0.213 ms | 0.336 ms | 0.336 ms |

## Common COUNT(*) queries (hot tables)

| Table | p50 | p95 | p99 |
|---|---|---|---|
| `procore_ep_budget_detail_row_cells` | 3.339 ms | 3.779 ms | 3.779 ms |
| `second_brain_financial_review_required_items` | 4.079 ms | 4.393 ms | **4.393 ms** |
| `procore_ep_schedule_relationships` | 0.027 ms | 0.538 ms | 0.538 ms |
| `procore_ep_schedule_activities` | 0.009 ms | 0.088 ms | 0.088 ms |

## Aggregate read gate (worst hot-table COUNT)

| Percentile | NAS | Threshold | Pass |
|---|---|---|---|
| p50 | **4.079 ms** | < 100 ms | Yes |
| p95 | **4.393 ms** | < 500 ms | Yes |
| p99 | **4.393 ms** | < 1500 ms | Yes |

## Top tables by row count (names + counts only)

1. `procore_financial_amount_facts` — 447,152  
2. `procore_ep_budget_detail_row_cells` — 273,951  
3. `schedule_version_diff_detail_facts` — 209,437  
4. `procore_endpoint_raw_payloads` — 136,458  
5. `second_brain_financial_review_required_items` — 128,769  

## Mac comparison (same queries)

| Percentile | Mac | NAS | Ratio |
|---|---|---|---|
| p50 (worst COUNT) | 2.774 ms | 4.079 ms | ~1.5× |
| p95 | 2.899 ms | 4.393 ms | ~1.5× |
| p99 | 2.899 ms | 4.393 ms | ~1.5× |

NAS reads are slightly slower than Mac SSD baseline but well within acceptance gates.

**Errors:** 0 · **SQLITE_BUSY:** 0

Raw JSON: `json/nas-read.json`
