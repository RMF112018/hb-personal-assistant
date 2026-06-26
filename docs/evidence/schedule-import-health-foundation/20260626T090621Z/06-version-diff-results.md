# Version Diff Results

Enhanced diff computes:

- added/removed/changed activities
- changed activity IDs
- near-term changed activity IDs
- finish/start drift stats
- relationship add/remove
- relationship type changes
- lag changes
- WBS/calendar/code/constraint churn

Existing `/api/schedules/projects/{project_key}/diff` remains compatible. Detailed facts are persisted in `schedule_version_diff_facts`.

Default commit-time diff is best-effort. If it fails, the import is not rolled back and a coded diff capability is persisted.
