# Project Schedule Hub Performance Fix Evidence - 2026-06-28

## Scope

- Endpoint/read model: `GET /api/projects/{project_key}/schedule` via `ProjectScheduleSummaryService.build_summary("tropical")`.
- Fix target confirmed by instrumentation and query review: Project Schedule Hub version resolution and downstream full-dataset reads.
- Standalone `/schedules/*` repository behavior was preserved; hub-specific bounded reads were added in the Project Schedule Hub service.

## Before-Fix Evidence

- User-provided hang sample: `/private/tmp/project-schedule-hang-sample.txt`.
- Sample showed AnyIO worker blocked in SQLite execution:
  - `pysqlite_connection_execute`
  - `sqlite3_step`
  - `sqlite3VdbeExec`
  - `vdbeSorterListToPMA` / `vdbeSorterSort` / `pwrite`
- Interpretation: the pre-fix read path was spilling a large SQLite sort/group/distinct/join to temp storage.

### Before EXPLAIN

Representative large `tropical` fixture, old version-resolution query:

```text
SCAN i USING INDEX sqlite_autoindex_schedule_file_imports_1
SEARCH a USING INDEX idx_schedule_activities_import (import_id=?) LEFT-JOIN
SEARCH r USING AUTOMATIC COVERING INDEX (import_id=?) LEFT-JOIN
USE TEMP B-TREE FOR count(DISTINCT)
USE TEMP B-TREE FOR count(DISTINCT)
USE TEMP B-TREE FOR ORDER BY
```

## Patch Summary

- Replaced hub version resolution with a project-scoped, capped `schedule_file_imports` query only.
- Removed hub reads that embedded or traversed full activity, relationship, CPM, or diff datasets.
- Added controlled metadata-only stage timing in `technical_evidence.performance_stage_timings`.
- Added hub-specific bounded reads:
  - latest comparable versions: 12
  - top actions: 5
  - all actions: 25
  - direct remaining changes: 10
  - upstream remaining impact: 10
  - top impacted activities: 10
  - recent completions: 10
  - recent starts: 10
  - critical path preview: 20
  - milestones: 20
- No new indexes or migrations were added. The after plan was fast enough without schema changes.

### After EXPLAIN

Representative large `tropical` fixture, new version-resolution query:

```text
SCAN schedule_file_imports
USE TEMP B-TREE FOR ORDER BY
```

This after plan no longer joins activity or relationship tables and no longer performs `COUNT(DISTINCT)`.

## Timing Evidence

Representative large fixture: 1,800 current activities, 1,799 relationships, persisted diff detail, persisted CPM activity/path rows.

Service timing:

```json
{
  "elapsed_ms": 168.795,
  "status": "ready",
  "remaining_count": 1636,
  "counts_unchanged": true,
  "mutated_tables": []
}
```

Stage timings:

```text
project_display_lookup: 6.682 ms
version_resolution: 8.940 ms
current_activity_summary: 8.184 ms
remaining_activity_sample: 7.423 ms
recent_progress: 8.025 ms
cpm_summary_path_reads: 7.811 ms
diff_and_change_impact: 29.431 ms
milestones: 15.624 ms
forecast_finish: 7.809 ms
```

HTTP timing:

- `curl` was blocked by local command policy: `Live endpoint calls require explicit authorization and output redaction.`
- Equivalent localhost HTTP probe against a temporary seeded API instance:

```json
{"http_code": 200, "time_total": 0.200598, "bytes": 32126}
```

## API Shape Proof

Representative large fixture response caps:

```json
{
  "actions_preview": 5,
  "actions_all": 5,
  "direct_changes": 10,
  "upstream": 5,
  "critical_path_preview": 20,
  "milestones": 16,
  "trend_points": 2
}
```

Automated tests assert:

- no full `activities`, `relationships`, `diagnostics`, `detail_rows`, `cpm_activity_results`, or `diff_detail_facts` datasets in the API response
- raw technical identifiers are absent from default PM-facing response fields
- all default PM lists obey hard caps
- no mutation on read by comparing schedule table counts before and after
- no passive recompute by monkeypatching import diff and CPM compute write paths to fail if invoked

## Validation

```text
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest tests/test_project_schedule_hub_api.py -q
........s

.venv/bin/python -m ruff check src/hb_assistant/construction/analytics/project_schedule_summary_service.py tests/test_project_schedule_hub_api.py
All checks passed!

npm test -- ProjectSchedulePage.test.tsx
4 passed
```
