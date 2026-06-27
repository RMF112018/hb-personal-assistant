# Repo-truth audit (verified against source this session)

## Activity fields used (read-only)
- `activity_id`, `activity_name`, `is_milestone`, `calendar_id`
- `duration_original`, `duration_remaining`, `duration_unit` (TEXT strings)
- `planned_start`, `start_date` (anchor fallback only; ISO "YYYY-MM-DD[ HH:MM]")
- NOT used for logic: early/late dates, total/derived float, source_critical_flag, source_driving_path_flag, is_critical.

## Relationship fields used
- `predecessor_activity_id`, `successor_activity_id`, `relationship_type` (normalized FS/SS/FF/SF), `lag_value`, `lag_unit`, `relationship_row_id`.

## Duration precedence (implemented)
1. `is_milestone` → 0.0 (source "milestone").
2. `duration_original` via normalize_duration_days(hours_per_day=calendar_hours_per_day(...)).
3. else `duration_remaining`.
4. else None → forward_pass_status "missing_duration".
Units: XER/P6-XML duration_unit="hour" → /hpd. MSP duration_original is ISO8601 (PT40H..) → float() fails → missing_duration (documented limitation).

## Lag-unit handling (implemented, reuses normalize_lag_result)
- XER/P6-XML lag_unit="hour" → /hpd; MSP lag_unit="minute_tenth" → /10/60/hpd. Negative preserved.
- Missing/empty lag → 0 with note. Non-empty unparseable → relationship excluded + flagged. Unknown numeric unit ("assumed_days") → applied as days + flagged unsupported_lag_unit (not silent).

## Schedule-start-anchor precedence (implemented)
1. data_date via parse_schedule_version_data_date(svk) (3rd "|" segment). [resolved in the live minimal.xer run → 2026-06-01, source "data_date"]
2. min activity planned_start (parseable ISO).
3. min activity start_date.
4. else block: missing_start_anchor. (Project-level planned start is not persisted as a distinct field, so data_date leads.)

## Reused helpers (not reinvented)
- schedule_quality_normalization.normalize_duration_days / normalize_lag_result / calendar_hours_per_day / DEFAULT_HOURS_PER_DAY (8.0).
- schedule_identity_repository.parse_schedule_version_data_date.
- schedule_activity_repository.list_activities / list_relationships / list_calendars / get_version_summary.
- schedule_cpm_graph.build_graph (Phase 1).
