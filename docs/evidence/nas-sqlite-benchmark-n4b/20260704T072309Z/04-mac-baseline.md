# 04 — Mac Baseline (Comparison Only)

**Note:** Mac results inform comparison; N4B decision is NAS-primary.

## Copy creation

| Item | Value |
|---|---|
| Source | Live Mac DB (read-only URI + `query_only=ON`) |
| Copy | `/tmp/hb-nas-sqlite-bench-20260704T072309Z/hb-pa-mac-bench.sqlite` |
| Method | SQLite backup API |
| Elapsed | 4.606 s |
| Source unchanged | **Yes** (size/mtime/ino identical) |
| Validation | `quick_check=ok`, schema=98 |

## Read benchmark (Mac copy)

| Query group | p50 ms | p95 ms | p99 ms |
|---|---|---|---|
| Connection open/close | 0.052 | 0.21 | 0.21 |
| Schema version | 0.003 | 6.974 | 6.974 |
| Table count | 0.09 | 0.175 | 0.175 |
| `procore_ep_budget_detail_row_cells` COUNT | 2.352 | 2.526 | 2.526 |
| `second_brain_financial_review_required_items` COUNT | 2.774 | 2.899 | 2.899 |
| `SQLiteMigrator.current_version()` | — | — | 7.94 (single) |

**Worst-case read among hot COUNT queries:** p50 **2.774 ms**, p95 **2.899 ms**, p99 **2.899 ms**

## Write benchmark (Mac copy — comparison)

| Scenario | p50 ms | p95 ms | p99 ms |
|---|---|---|---|
| Autocommit insert (×5) | 0.06 | 0.218 | 0.218 |
| Batch insert 1000 | 2.31 | 2.31 | 2.31 |
| Update synthetic | 0.852 | 0.852 | 0.852 |

## Concurrency (Mac copy — comparison)

| Scenario | Read p95 ms | Write p95 ms | SQLITE_BUSY |
|---|---|---|---|
| 5 readers | 0.865 | — | 0 |
| 10 readers | 0.073 | — | 0 |
| 5 readers + 1 writer | 0.025 | 0.227 | 0 |
| 10 readers + 1 writer | 1.189 | 0.407 | 0 |

**Total SQLITE_BUSY:** 0 · **Retries:** 0

## WAL (Mac copy — comparison)

| Item | Value |
|---|---|
| Checkpoint passive | 0.141 ms |
| Checkpoint truncate | 0.034 ms |
| quick_check after | ok (15.3 s) |
| Sidecars | scratch only |

Raw JSON: `json/mac-*.json`
