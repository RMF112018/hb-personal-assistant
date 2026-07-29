# Phase D failed run 001 — production locator lookup scalability

Disposition: preserved failure; superseded only by a later passing exact-candidate rehearsal

## Observed result

- Started: 2026-07-27 19:58:13 America/New_York
- Stopped: 2026-07-28 01:49:45 America/New_York
- Elapsed: 5 hours 51 minutes
- Active case: first fresh 400,000-file generation
- Durable generation progress: 209,000 files observed and 209,000 metadata rows upserted
- Process state: running at approximately 97–100% CPU; peak physical footprint approximately 153 MiB
- Effective throughput: approximately 9.9 files/second
- Terminal disposition: manually interrupted after the result had already demonstrated a decisive failure
  of the 500 files/second Phase D SLO. The scratch tree/database were cleaned by the harness `finally` block.

## Diagnostic evidence

The interruption stack was inside:

```text
scan_source_root
  -> _flush
  -> _index_source_metadata
  -> upsert_source_file
  -> _upsert_source_file_locked
  -> _locator_for_path
  -> sqlite3.Connection.execute
```

A one-second live stack sample showed sustained SQLite B-tree table seeks and page reads, not a sleeping
process or deadlock.

## Root cause

`SourceIndexRepository._locator_for_path()` looked up every new file by `(source_kind, rel_path,
source_root_key)` with `is_current_locator=1`, but omitted `tombstoned_at IS NULL`.
`idx_locators_active_path` is a partial index on `(source_root_key, rel_path)` whose predicate is
`is_current_locator=1 AND tombstoned_at IS NULL`; SQLite therefore could not use it for the production
query. Each inserted file caused a progressively larger locator-table scan, producing quadratic behavior.

## Corrective action

The production lookup now includes the complete partial-index predicate. A Phase D regression test executes
`EXPLAIN QUERY PLAN` against the exact query shape and requires `idx_locators_active_path` with no locator
table scan. The failed run is not represented as a pass and remains part of the Phase D evidence history.
