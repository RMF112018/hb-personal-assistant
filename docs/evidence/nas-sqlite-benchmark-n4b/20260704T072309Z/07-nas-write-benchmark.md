# 07 — NAS Write Benchmark

**Synthetic table only:** `__n4b_sqlite_bench_events`  
**Production tables:** not written

## Journal / sync

| Setting | Value |
|---|---|
| journal_mode (before/after) | wal |
| synchronous | 2 (FULL) |

## Write latency

| Scenario | p50 ms | p95 ms | p99 ms | max ms |
|---|---|---|---|---|
| Autocommit single insert (×5) | 64.275 | 164.292 | 164.292 | 164.292 |
| Batch insert 10 | 36.525 | 36.525 | 36.525 | 36.525 |
| Batch insert 100 | 79.891 | 79.891 | 79.891 | 79.891 |
| Batch insert 1000 | 53.05 | 53.05 | 53.05 | 53.05 |
| Update synthetic rows | 316.637 | 316.637 | 316.637 | 316.637 |
| Delete synthetic subset | 33.116 | 33.116 | 33.116 | 33.116 |

## Write gate (worst synthetic transaction)

| Percentile | NAS | Threshold | Pass |
|---|---|---|---|
| p50 | 64.275 ms | — | — |
| p95 | **316.637 ms** | < 1000 ms | Yes |
| p99 | **316.637 ms** | < 3000 ms | Yes |

## Size / sidecars

| Item | Before | After |
|---|---|---|
| DB file | 4,151,631,872 B | 4,151,631,872 B |
| `-wal` sidecar | 0 B (pre-existing shm 32 KiB) | merged |
| Sidecars in scratch only | **Yes** | **Yes** |

**Errors:** 0 · **SQLITE_BUSY:** 0

## Mac comparison

Mac autocommit p95 **0.218 ms** vs NAS **164 ms** — NAS writes ~750× slower than Mac SSD for single-row autocommit, but batched 1000-row transaction **53 ms** on NAS vs **2.3 ms** on Mac. NAS write latency remains within gates; batching is strongly preferred on NAS.

Raw JSON: `json/nas-write.json`
