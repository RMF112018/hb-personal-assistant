# Schema audit tool design

`scripts/dev_schedule_clean_db_schema_audit.py` discovers schedule tables from `sqlite_master` using name/column heuristics plus an explicit required-table catalog.

## Output sections

1. `discovered_by_heuristic` — per-table PK/FK, count strategy, project row counts, purgeable flag
2. `required_expected_tables_missing_or_unclassified` — package, lineage, CPM, quality, review, membership gaps

## Safety

- Rejects live DB unless `--read-only-live`
- Opens DB read-only when possible
