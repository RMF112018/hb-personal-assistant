# Query manifest — CPM longest-path live queried evidence

## Inputs

- Copied DB: `local-sensitive/clean-db/<redacted>` (local-only; not included)
- Project key: `tropical`
- Schedule version key: `tropical|1071|2026-06-23 08:00`
- SQLite open mode: `read_only` (`file:...?mode=ro`)

## SQL queries executed

### `schema_version`

```sql
SELECT MAX(version) AS schema_version FROM schema_migrations
```

### `activity_count`

```sql
SELECT COUNT(*) AS activity_count FROM procore_ep_schedule_activities WHERE schedule_version_key = ? AND project_key = ?
```

### `relationship_count`

```sql
SELECT COUNT(*) AS relationship_count FROM procore_ep_schedule_relationships WHERE schedule_version_key = ? AND project_key = ?
```

### `schedule_version_exists`

```sql
SELECT COUNT(*) AS cnt FROM procore_ep_schedule_activities WHERE schedule_version_key = ? AND project_key = ?
```

### `cpm_runs_for_version`

```sql
SELECT cpm_run_id, calculation_type, cpm_recalculation_status, source_run_id, import_id, created_at, schedule_start_anchor, schedule_finish_anchor FROM schedule_cpm_runs WHERE schedule_version_key = ? AND project_key = ? AND calculation_type IN ('forward_pass','backward_pass','float','longest_path','criticality') ORDER BY created_at
```

### `activity_results_count`

```sql
SELECT COUNT(*) FROM schedule_cpm_activity_results WHERE cpm_run_id = ?
```

### `relationship_results_count`

```sql
SELECT COUNT(*) FROM schedule_cpm_relationship_results WHERE cpm_run_id = ?
```

### `path_count`

```sql
SELECT COUNT(*) FROM schedule_cpm_paths WHERE cpm_run_id = ?
```

### `path_activities_count`

```sql
SELECT COUNT(*) FROM schedule_cpm_path_activities WHERE cpm_run_id = ?
```

### `paths_for_run`

```sql
SELECT path_id, path_rank, end_activity_id, activity_count, relationship_count, path_duration, path_start_offset_days, path_finish_offset_days, path_basis FROM schedule_cpm_paths WHERE cpm_run_id = ? ORDER BY path_rank
```

## Python / exporter commands

- `scripts/dev_schedule_cpm_longest_path_query_evidence.py --confirm-clean-copy --allow-custom-copy-path`
- `scripts/dev_schedule_cpm_formula_trace_export.py --latest --allow-custom-copy-path (local-only)`
- `scripts/dev_schedule_live_db_unchanged_probe.py --read-only-live`

## Generated files

- `00-repo-state.txt`
- `01-query-manifest.md`
- `02-db-copy-metadata.json`
- `03-schedule-version-proof.json`
- `04-cpm-lineage-proof.json`
- `05-cpm-table-counts.json`
- `06-persisted-longest-path-proof.json`
- `07-cpm-run-summary-sanitized.json`
- `08-cpm-validation-recompute-diff-sanitized.json`
- `09-cpm-formula-audit-sanitized.md`
- `10-cpm-live-path-summary-sanitized.json`
- `12-live-db-compare.json`
- `13-live-db-compare.md`
- `14-evidence-disposition.md`
- `17-query-proof-summary.md`

## Exclusions

No SQLite database file is included in commit-eligible evidence.
Raw activity/relationship/longest-path JSONL traces remain local-only.
