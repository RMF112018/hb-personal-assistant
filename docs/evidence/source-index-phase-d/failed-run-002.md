# Phase D failed run 002 — no-change batch lookup and stamp scalability

Disposition: preserved failure; superseded only by a later passing exact-candidate rehearsal

## Successful prefix

The run began after correcting the per-file current-locator lookup identified by failed run 001.

- Fresh 400,000-file generation: completed; 400,000 active rows; 17 passes; 194.154 seconds;
  approximately 2,060 files/second.
- Fresh 1,000,000-file generation: completed; 1,000,000 active rows; 41 passes; 1,020.988 seconds;
  approximately 979 files/second.
- Both fresh scans retained zero content-indexed rows and did not trigger the parser/hash tripwires.

## Failed no-change case

The first no-change pass fast-skipped the expected 25,000 rows with zero metadata upserts, but required
approximately 159 seconds. A live stack sample was inside SQLite `fetchall`/B-tree table reads, and the
interrupt stack was inside `SourceIndexRepository.stamp_last_seen()`. Continuing would have turned the
remaining no-change and delta cases into another multi-hour run, so the attempt was stopped and preserved as
a Phase D scalability failure.

The first interrupt reached the harness cleanup; a second interrupt landed during recursive scratch-tree
deletion. The one remaining exact synthetic directory was first moved recoverably to the user Trash, then
permanently removed after its identity was validated. No failed-run scratch content remains.

## Root cause

Both no-change hot-path queries omitted the complete predicate required by the partial locator path index:

- `load_metadata_state_batch()` joined current locators without `l.tombstoned_at IS NULL`;
- `stamp_last_seen()` updated current locators without `tombstoned_at IS NULL`.

SQLite therefore could not use `idx_locators_active_path`, causing repeated million-row locator scans for
bounded batches.

## Corrective action

Both exact production queries now include `tombstoned_at IS NULL`. A Phase D query-plan regression test
requires `idx_locators_active_path` and rejects `SCAN l` for both the batch-state read and observation stamp.
