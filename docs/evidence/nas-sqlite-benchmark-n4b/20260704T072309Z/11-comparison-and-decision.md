# 11 — Comparison and Decision

## N4B result: **PASS**

NAS-local SQLite on `/volume1` btrfs meets all acceptance thresholds with zero lock failures and intact integrity.

## Key NAS metrics

| Category | p50 | p95 | p99 |
|---|---|---|---|
| **Read** (worst hot COUNT) | 4.079 ms | 4.393 ms | 4.393 ms |
| **Write** (worst synthetic txn) | 64.275 ms | 316.637 ms | 316.637 ms |

| Concurrency | Value |
|---|---|
| SQLITE_BUSY | **0** |
| Retries | **0** |

| WAL | Value |
|---|---|
| Checkpoint passive | 191 ms |
| quick_check after | ok (31.6 s) |
| Sidecars | scratch only |

| Integrity | Value |
|---|---|
| quick_check | ok |
| integrity_check | ok |
| schema | 98 |

## Mac vs NAS summary

| Dimension | Mac (SSD) | NAS (btrfs) | Assessment |
|---|---|---|---|
| Read COUNT p99 | ~2.9 ms | ~4.4 ms | NAS ~1.5× slower; both far under gates |
| Single-row write p95 | ~0.2 ms | ~164 ms | NAS slower; still under 1000 ms gate |
| Batch 1000 insert | ~2.3 ms | ~53 ms | NAS acceptable with batching |
| Concurrency BUSY | 0 | 0 | Equivalent reliability |
| WAL checkpoint | sub-ms | ~191 ms | Acceptable |

## Bottlenecks observed

1. **Single-row autocommit writes** on NAS (~64–164 ms) — mitigate with batched transactions (1000-row batch **53 ms**).
2. **Full quick_check** on 4 GiB DB takes ~32 s on NAS — run offline/during maintenance, not per-request.
3. **Schema version query p95 outlier** (17 ms) — cold-cache effect; p50 **0.008 ms**.

## Use-case suitability

| Use case | Acceptable? | Notes |
|---|---|---|
| Post-N4B loopback backend smoke | **Yes** | Reads well within gates; single-process |
| Limited personal production use | **Yes** | With batched writes; monitor WAL size |
| Always-on background ingestion | **Caution** | No BUSY in tests, but sustained write-heavy ingestion untested at production volume |
| Future multi-user use | **No** | SQLite single-writer limits; plan PostgreSQL before multi-user |

## Recommendation: **KEEP_SQLITE_WITH_LIMITS**

NAS-local SQLite is performant enough for N4 loopback smoke and limited single-user production **if**:

- Writes use batched transactions (app already uses WAL + busy_timeout=5000)
- Ingestion schedulers are enabled incrementally with monitoring
- PostgreSQL migration is planned before multi-user or heavy concurrent write workloads

Not **POSTGRESQL_REQUIRED_BEFORE_CUTOVER** — observed NAS-local performance supports proceeding to bounded N4 smoke.

Not bare **KEEP_SQLITE_FOR_NOW** — write latency profile warrants explicit batching/monitoring limits.

Raw JSON summaries: `json/nas-*.json`, `json/mac-*.json`
