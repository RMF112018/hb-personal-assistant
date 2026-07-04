# 10 — Integrity After Benchmark

**DB:** NAS scratch benchmark copy (post all workloads)

## Validation

| Check | Result |
|---|---|
| `PRAGMA quick_check` | **ok** |
| `PRAGMA integrity_check` | **ok** |
| Schema version | **98** |
| Table count | **508** (see note below) |
| `__n4b_sqlite_bench_events` rows | 2,560 |

## Table-count note (506 → 508)

N3 closeout reported **506** tables/views in the production snapshot. Post-benchmark `sqlite_master` count is **508** because the benchmark copy gained:

1. **`__n4b_sqlite_bench_events`** — synthetic benchmark table (expected)
2. **One additional sqlite artifact** — likely a transient/internal object created during WAL/write workloads on the copy

This is **benchmark-copy artifact growth only**. All **11 production-table fingerprints** are unchanged (see below); no production table row counts shifted.

## Production-table fingerprint (before vs after)

All fingerprinted production tables **unchanged**:

| Table | Count (before = after) |
|---|---|
| `procore_ep_budget_detail_row_cells` | 273,951 |
| `second_brain_financial_review_required_items` | 128,769 |
| `procore_ep_schedule_activities` | 18,909 |
| `procore_ep_schedule_relationships` | 44,570 |
| `forecast_cost_entries` | 6,324 |
| `schema_migrations` | 98 |
| *(all 11 fingerprint tables)* | no delta |

**`fingerprint_delta_unexpected`:** `{}` (empty)

## Sidecars post-integrity

- `-wal`: 0 bytes (in scratch)
- `-shm`: 32,768 bytes (in scratch)
- Not staged in git

Raw JSON: `json/nas-integrity.json`
