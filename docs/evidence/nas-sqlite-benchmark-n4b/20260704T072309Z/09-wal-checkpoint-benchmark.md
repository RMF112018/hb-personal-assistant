# 09 — WAL / Checkpoint Benchmark

**DB:** NAS scratch benchmark copy only · **N3 final DB:** WAL not modified

## Journal mode

| Stage | Mode |
|---|---|
| Before | wal |
| After explicit `PRAGMA journal_mode=WAL` | wal |

## Timings

| Operation | Latency |
|---|---|
| WAL mode set | 0.01 ms |
| Write burst (100 synthetic rows) | 138.388 ms |
| Checkpoint PASSIVE | **191.231 ms** (result: `[0, 6, 6]`) |
| Checkpoint TRUNCATE | 0.117 ms (result: `[0, 0, 0]`) |
| quick_check after checkpoint | **31.571 s** (result: **ok**) |

## Sidecars (scratch only)

| File | Mid-benchmark | After truncate |
|---|---|---|
| `hb-pa-nas-bench.sqlite-wal` | 24,752 B | 0 B (absorbed/truncated) |
| `hb-pa-nas-bench.sqlite-shm` | 32,768 B | 32,768 B |

**Paths:** `/volume1/personal-assistant/app-support/tmp/sqlite-bench-20260704T072309Z/`  
**sidecars_in_scratch_only:** **true** (confirmed — not in repo, not at N3 final DB path)

## Mac comparison

| Item | Mac | NAS |
|---|---|---|
| Checkpoint passive | 0.141 ms | 191 ms |
| quick_check | 15.3 s | 31.6 s |

NAS checkpoint and quick_check are slower on 4 GiB DB over btrfs — expected. Both complete successfully with `ok`.

Raw JSON: `json/nas-wal.json`
