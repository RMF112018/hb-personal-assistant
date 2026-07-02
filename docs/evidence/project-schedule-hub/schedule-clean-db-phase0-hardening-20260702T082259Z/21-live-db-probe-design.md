# Live DB probe design

`scripts/dev_schedule_live_db_unchanged_probe.py` snapshots project-specific schedule table counts and compares before/after.

## Fixture proof

Phase 0 uses fixture DBs under the evidence directory for apply/compare proofs.

## Optional live smoke

Operator may run read-only snapshot against live DB with `--read-only-live` (skipped in this phase closeout).

## Compare semantics

- Fails when Tropical schedule counts change
- File hash/WAL-only changes are warnings when counts are unchanged
