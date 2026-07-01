# Portfolio rollup read model

Service: `project_schedule_portfolio_review_service.py`

## Thin read path (per project)

1. `ScheduleProjectCatalog.list_browse_projects()` — project enumeration (EP + schedule-only keys).
2. `ProjectScheduleSummaryService.build_portfolio_trust_slice()` — versions, current resolve, analytics/identity/CPM trust, quality headline (**no** `build_summary()`, drivers, or narratives).
3. `ProjectScheduleReviewService.list_items()` — persisted review counts.
4. `ProjectScheduleReviewCueService.list_quality_preview_cues()` — quality preview cue counts (no full workbench preview sync).
5. `build_review_status_rollup()` — PM-safe review status block.
6. `resolve_recommended_next_action()` — deterministic next action.
7. `classify_portfolio_status()` + priority sort.

## Staleness

- `SCHEDULE_STALENESS_THRESHOLD_DAYS = 30`
- `current` ≤ 30 days; `stale` > 30 days; `missing` no committed schedule; `unknown` no reliable data date.

## Sort priority

1. blocked
2. operator_action_required (includes missing schedule)
3. needs_review
4. stale
5. degraded
6. ready
7. unknown

## PM-safe payload

Forbidden keys stripped via `_PM_FORBIDDEN_KEYS`. Technical nested payload only when `include_technical=1` and operator/admin role.
