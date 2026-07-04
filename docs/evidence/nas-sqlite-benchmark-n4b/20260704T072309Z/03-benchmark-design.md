# 03 — Benchmark Design

## Why benchmark copies

- **Live Mac DB** and **N3 final NAS DB** are protected sources — opened read-only for backup/validation only.
- All read/write/concurrency/WAL workloads run against **scratch copies** so production data is never mutated.
- Synthetic writes go only to `__n4b_sqlite_bench_events`.

## Workloads

| # | Workload | Target |
|---|---|---|
| 1 | Read-only metadata / common `COUNT(*)` queries | Benchmark copy |
| 2 | Synthetic write transactions | Benchmark copy (`__n4b_*` table only) |
| 3 | Concurrent readers + synthetic writer | Benchmark copy |
| 4 | WAL / checkpoint | Benchmark copy |
| 5 | Post-benchmark integrity + fingerprint | Benchmark copy |

## Tooling

- Script: `scripts/nas_sqlite_benchmark_n4b.py` (benchmark-only; **not** wired into CLI, schedulers, or app startup)
- Repo helper allowed: `SQLiteMigrator.current_version()` on Mac copy only
- Skipped: repository/store helpers that may open write-capable connections or apply migrations

## Metrics captured

- p50, p95, p99, max latency (ms)
- Error count, `SQLITE_BUSY` count, retry count
- Throughput (ops completed / duration)
- DB size before/after, WAL/SHM sidecar sizes
- Production-table count fingerprints before/after

## Acceptance thresholds

| Metric | Gate |
|---|---|
| Read p50 | < 100 ms |
| Read p95 | < 500 ms |
| Read p99 | < 1500 ms |
| Write p95 | < 1000 ms |
| Write p99 | < 3000 ms |
| `SQLITE_BUSY` (controlled concurrency) | 0 (or explainable + recoverable) |
| Post-benchmark `integrity_check` | ok |
| Schema version | 98 |

## Mutable paths (only)

| Location | Purpose |
|---|---|
| `/tmp/hb-nas-sqlite-bench-20260704T072309Z/` | Mac scratch |
| `/volume1/personal-assistant/app-support/tmp/sqlite-bench-20260704T072309Z/` | NAS scratch |

## Decision weighting

Mac write/concurrency results are **comparison baseline only**. N4B PASS/WARN/FAIL is determined primarily from **NAS-local** behavior on `/volume1`.
