# Repo-truth audit (Phase A1)

| Question | Finding |
|----------|---------|
| Canonical import preview/commit | `ScheduleImportService.preview_bytes()` / `.commit()` |
| Standalone routes | `POST /api/schedules/import-preview`, `POST /api/schedules/import-commit` |
| Project schedule routes (pre-A1) | `GET /api/projects/{key}/schedule/*` read-only hub surfaces |
| Project-scoped import (pre-A1) | None |
| CPM entrypoint | `ScheduleCpmGraphService` six-step chain |
| CPM mode (pre-A1) | Read-only API; manual chain in tests/scripts only |
| Import commit CPM (pre-A1) | Not triggered |
| Import commit quality/diff (pre-A1) | Yes — `queue_after_commit` + `poll_and_process(1)` + best-effort diff |
| Zero-day narrative origin | `ProjectScheduleDriverAnalysisService.build_narrative()` |
| PM "Not available" / "Unassigned" | `ProjectSchedulePage.text()` fallback + raw `wbs_code` in driver rows |