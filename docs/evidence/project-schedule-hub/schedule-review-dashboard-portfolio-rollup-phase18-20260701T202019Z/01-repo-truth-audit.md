# Phase 18 repo-truth audit

Verified on `origin/main` at merge commit `19d37316` (PR #258 Phase 17). Phase 17 evidence present at `schedule-review-workbench-action-loop-phase17-20260701T192338Z/`.

## Audit answers

1. **Project list route:** `GET /api/projects` → `ProjectSummaryReadModelService` (`procore_ep_projects`).
2. **Portfolio placeholders:** `GET /api/projects/portfolio` and `/api/projects/all/overview` → `AnalyticsService` (not schedule-aware; left unchanged).
3. **Per-project schedule:** `GET /api/projects/{key}/schedule` → `ProjectScheduleSummaryService.build_summary()`.
4. **Analytics trust:** `project_schedule_analytics_trust_service.py` via `_hub_analytics_trust` / `ledger_for_hub_version`.
5. **Identity trust:** `project_schedule_identity_trust_service.py` via hub trust envelope.
6. **CPM trust:** `schedule_cpm_trust.py` + observability repo, surfaced on analytics ledger.
7. **Quality trust:** `ProjectScheduleQualityControlsService.build_quality_controls()`.
8. **Review rollups:** `build_review_status_rollup()` in `project_schedule_review_rollup_service.py` (per-project).
9. **No-schedule projects:** Included via `ScheduleProjectCatalog.list_browse_projects()` union with committed-import keys.
10. **Staleness:** Introduced in Phase 18 (`SCHEDULE_STALENESS_THRESHOLD_DAYS = 30`).
11. **Schedule links:** Per-project routes under `/projects/{key}/schedule/*` and `/schedules/identity-review`.
12. **Raw ID leaks:** Existing PM denylist extended for portfolio payloads (version keys, import IDs, hashes, etc.).
13. **Best dashboard home:** `/projects/all/schedule/review` with `ProjectScheduleReviewDashboardPage`.
14. **Portfolio gaps closed:** Thin portfolio read model, dashboard API, next-action engine, UI, export, navigation.

## Phase 18 approach

- **No `build_summary()` in portfolio loop.** Uses new `build_portfolio_trust_slice()` (version resolve + trust only).
- **Per-project loop** over catalog projects for review items + quality preview cues; documented in `16-known-limitations.md`.
- **Missing schedules** classified `operator_action_required` and sorted above stale/degraded.
- **`ready`** requires current schedule, all trust dimensions ready, no open review items, no preview cues.
