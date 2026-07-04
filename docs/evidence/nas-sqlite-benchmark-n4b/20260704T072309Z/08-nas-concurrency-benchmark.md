# 08 — NAS Concurrency Benchmark

**DB:** NAS scratch benchmark copy only

## Scenarios

| Scenario | Duration | Ops done | Read p50 | Read p95 | Read p99 | Write p50 | Write p95 | Write p99 | BUSY | Retries |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 readers | 0.144 s | 100/100 | 0.084 ms | 5.807 ms | 135.534 ms | — | — | — | 0 | 0 |
| 10 readers | 0.281 s | 200/200 | 0.524 ms | 5.846 ms | 249.212 ms | — | — | — | 0 | 0 |
| 5 readers + 1 writer | 1.454 s | 120/120 | 0.077 ms | 2.044 ms | 143.568 ms | 72.445 ms | 109.383 ms | 137.269 ms | 0 | 0 |
| 10 readers + 1 writer | 1.633 s | 220/220 | 0.592 ms | 6.651 ms | 258.350 ms | 72.477 ms | 120.457 ms | 124.891 ms | 0 | 0 |
| 1 long reader + 1 writer | 2.056 s | 60/60 | 0.016 ms | 0.029 ms | 35.740 ms | 71.211 ms | 129.026 ms | 139.157 ms | 0 | 0 |

## Totals

| Metric | Value |
|---|---|
| **SQLITE_BUSY count** | **0** |
| **Retry count** | **0** |
| Read errors | 0 |
| Write errors | 0 |

## Assessment

No lock contention failures under tested concurrency (up to 10 concurrent readers + 1 writer). Sporadic read p99 spikes (~135–258 ms) occur but remain far below the 1500 ms gate and complete without busy errors.

## Mac comparison

Mac showed similar zero-BUSY behavior with lower absolute latencies (SSD). NAS concurrency profile is acceptable for single-process backend with moderate concurrent reads.

Raw JSON: `json/nas-concurrency.json`
