# 05 — NAS Copy and Validation

## Intended method

Backup API from N3 final DB as `personal-assistant-svc` → NAS scratch copy.

## Actual method (session constraint)

Non-interactive `sudo -u personal-assistant-svc` failed (password required). `bfetting` cannot read N3 final DB (mode `600`, PermissionError on open).

**Fallback used (equivalent data, same storage class):**

1. Mac backup copy created read-only from live Mac DB (byte size **4,151,631,872** — matches N3 NAS DB size).
2. Transferred to NAS scratch via `ssh` stdin pipe (scp/rsync subsystems unavailable on NAS).
3. NAS benchmarks executed on scratch copy at `/volume1/.../tmp/sqlite-bench-20260704T072309Z/`.

N3 evidence proved Mac live copy == N3 final copy (SHA equivalence at N3 closeout). Benchmark exercises **NAS-local btrfs SQLite** at the intended runtime path prefix.

## NAS scratch

```
drwxrwxrwx+ ... /volume1/personal-assistant/app-support/tmp/sqlite-bench-20260704T072309Z/
-rwxrwxrwx+ ... hb-pa-nas-bench.sqlite  (4151631872 bytes)
-rwxrwxrwx+ ... nas_sqlite_benchmark_n4b.py
```

## N3 final DB unchanged

Post-benchmark stat (read-only metadata via `bfetting`):

```
Size: 4151631872  Inode: 3264  Modify: 2026-07-04 06:23:40 UTC
Uid: personal-assistant-svc
```

Identical to preflight — **not mutated**.

## Destination validation (NAS copy, pre-workload)

| Check | Result |
|---|---|
| Size | 4,151,631,872 bytes |
| quick_check | ok (via Mac backup validation) |
| schema | 98 |

## Runtime user note

Benchmarks ran as `bfetting` (writable scratch). Production runtime user is `personal-assistant-svc`; file permissions on final DB path differ, but storage subsystem and co-location match production architecture.

Raw JSON: `json/nas-fingerprint-before.json`
