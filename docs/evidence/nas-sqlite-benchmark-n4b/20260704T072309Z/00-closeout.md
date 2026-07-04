# 00 — N4B Closeout

**Result: PASS** · Timestamp `20260704T072309Z` · Branch `bench/nas-sqlite-n4b-20260704T072309Z`

## Summary

N4B evaluated NAS-local SQLite performance using benchmark copies on `/volume1` btrfs scratch paths. NAS-local reads, synthetic writes, concurrency, WAL/checkpoint, and post-workload integrity all meet acceptance thresholds. **Zero `SQLITE_BUSY`** events under tested concurrency.

## Headline metrics (NAS)

| Metric | Value |
|---|---|
| Read p50 / p95 / p99 | 4.079 / 4.393 / 4.393 ms |
| Write p50 / p95 / p99 | 64.275 / 316.637 / 316.637 ms |
| Concurrency SQLITE_BUSY | **0** (retries: 0) |
| WAL checkpoint passive | 191 ms |
| Post-benchmark integrity | quick_check=ok, integrity_check=ok, schema=98 |

## Recommendation

**KEEP_SQLITE_WITH_LIMITS** — NAS-local SQLite is acceptable for loopback backend smoke and limited single-user production with batched writes; plan PostgreSQL before multi-user or heavy concurrent ingestion.

## Evidence index

| File | Topic |
|---|---|
| `01-preflight.md` | Gates, N3 inheritance |
| `02-environment-and-storage.md` | Mac + NAS environment |
| `03-benchmark-design.md` | Workloads, thresholds |
| `04-mac-baseline.md` | Mac comparison baseline |
| `05-nas-copy-and-validation.md` | Copy method + validation |
| `06-nas-read-benchmark.md` | NAS read results |
| `07-nas-write-benchmark.md` | NAS write results |
| `08-nas-concurrency-benchmark.md` | NAS concurrency |
| `09-wal-checkpoint-benchmark.md` | WAL/checkpoint |
| `10-integrity-after-benchmark.md` | Post-workload integrity |
| `11-comparison-and-decision.md` | PASS + recommendation |
| `12-boundaries-maintained.md` | Boundary attestation |
| `13-git-status.md` | Git posture |
| `json/*.json` | Machine-readable summaries (sanitized) |
| `local-sensitive/` | Gitignored — full-path backup fingerprint |

## Scratch cleanup (post-closeout hygiene)

Non-interactive `sudo` was unavailable to lock NAS scratch to `personal-assistant-svc:users` (700/600). **Both scratch directories were deleted** after evidence capture:

| Path | Action |
|---|---|
| `/tmp/hb-nas-sqlite-bench-20260704T072309Z/` (Mac) | **Deleted** |
| `/volume1/personal-assistant/app-support/tmp/sqlite-bench-20260704T072309Z/` (NAS) | **Deleted** |

N3 final DB path untouched.

## Boundaries

No live DB / N3 final DB / secrets / backend / container / vault / scheduler / router changes occurred. No commit or push yet.

## Next

N4 production startup remains **NOT authorized** until explicitly instructed in a separate operator prompt.
