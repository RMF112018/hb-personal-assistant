"""PM-facing project Schedule Hub read model.

This service is deliberately read-only. It summarizes already-persisted schedule import,
identity, diff, activity, and CPM facts for the Project module Schedule Hub. It never imports,
recomputes CPM, computes new diffs, or mutates schedule source rows.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository

from .schedule_import_service import ensure_schedule_schema

_RAW_KEY_PATTERN = re.compile(r"^[^|]+\|[^|]+\|.+$")
_FORBIDDEN_STORY_WORDS = (
    "caused the delay",
    "responsible for the delay",
    "compensable delay",
    "excusable delay",
    "contractor-caused",
    "owner-caused",
    "claim impact",
)
_LOG = logging.getLogger(__name__)
_SLOW_STAGE_MS = 250.0

_VERSION_CAP = 12
_TOP_ACTIONS_CAP = 5
_ALL_ACTIONS_CAP = 25
_TOP_IMPACTED_CAP = 10
_DIRECT_REMAINING_CHANGE_CAP = 10
_UPSTREAM_REMAINING_IMPACT_CAP = 10
_RECENT_COMPLETIONS_CAP = 10
_RECENT_STARTS_CAP = 10
_CRITICAL_PATH_PREVIEW_CAP = 20
_MILESTONE_CAP = 20
_REMAINING_SAMPLE_CAP = 25

_ACTIVITY_COLUMNS = """
    activity_id, activity_name, wbs_code, wbs_path, start_date, finish_date,
    actual_start, actual_finish, remaining_start, remaining_finish,
    remaining_early_start, remaining_early_finish, duration_original,
    duration_remaining, constraint_type, is_critical, is_milestone,
    total_float, derived_total_float_days, explicit_total_float_days,
    target_start, target_finish, baseline_start, baseline_finish
"""


@dataclass(frozen=True)
class _VersionChoice:
    version: dict[str, Any]
    identity_match: dict[str, Any] | None


class ProjectScheduleSummaryService:
    """Build the Project module Schedule Hub envelope."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._identity = ScheduleIdentityRepository(db_path=db_path)
        self._mapping = ScheduleMappingRepository(db_path=db_path)
        self._stage_timings: list[dict[str, Any]] = []

    def build_summary(self, project_key: str, *, as_of: date | None = None) -> dict[str, Any]:
        self._stage_timings = []
        ensure_schedule_schema(self._db_path)
        as_of_date = as_of or datetime.now(timezone.utc).date()
        project_name = self._timed(
            "project_display_lookup",
            project_key=project_key,
            fn=lambda: self._project_display_name(project_key),
        )
        versions = self._timed(
            "version_resolution",
            project_key=project_key,
            query_key="hub_project_versions",
            cap=_VERSION_CAP,
            fn=lambda: self._hub_project_versions(project_key),
        )
        if not versions:
            return self._empty_summary(project_key, project_name, as_of_date)

        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        if current_choice is None:
            return self._review_required_summary(project_key, project_name, as_of_date, versions)

        current = current_choice.version
        current_key = str(current["schedule_version_key"])
        current_label = self._friendly_label(current)
        current_data_date = self._data_date(current)
        previous_choice = self._resolve_previous(project_key, current_choice, versions)
        previous = previous_choice.version if previous_choice else None
        previous_key = str(previous["schedule_version_key"]) if previous else None
        previous_data_date = self._data_date(previous) if previous else None

        activity_summary = self._timed(
            "current_activity_summary",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_activity_summary",
            fn=lambda: self._activity_summary(current_key),
        )
        remaining = self._timed(
            "remaining_activity_sample",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_remaining_activities",
            cap=_REMAINING_SAMPLE_CAP,
            fn=lambda: self._remaining_activity_rows(current_key, limit=_REMAINING_SAMPLE_CAP),
        )

        recent = self._timed(
            "recent_progress",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_recent_progress",
            cap=_RECENT_COMPLETIONS_CAP + _RECENT_STARTS_CAP,
            fn=lambda: self._recent_progress(
                current_key=current_key,
                previous_key=previous_key,
                previous_data_date=previous_data_date,
                current_data_date=current_data_date,
                as_of_date=as_of_date,
            ),
        )
        cpm_summary = self._timed(
            "cpm_summary_path_reads",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_cpm_preview",
            cap=_CRITICAL_PATH_PREVIEW_CAP,
            fn=lambda: self._computed_cpm(current_key),
        )
        change_impact = self._timed(
            "diff_and_change_impact",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_change_impact",
            cap=_DIRECT_REMAINING_CHANGE_CAP + _UPSTREAM_REMAINING_IMPACT_CAP,
            fn=lambda: self._change_impact(
                project_key=project_key,
                current=current,
                previous=previous,
                current_key=current_key,
                previous_key=previous_key,
            ),
        )
        milestones = self._timed(
            "milestones",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_milestones",
            cap=_MILESTONE_CAP,
            fn=lambda: self._milestones(current_key, previous_key, recent),
        )
        remaining_health = self._remaining_health(
            remaining=remaining,
            activity_summary=activity_summary,
            change_impact=change_impact,
            cpm_summary=cpm_summary,
            current_choice=current_choice,
            previous=previous,
        )
        forecast = self._timed(
            "forecast_finish",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_forecast_finish",
            fn=lambda: self._forecast_finish(current_key, previous_key),
        )
        actions = self._actions(
            readiness_inputs={
                "previous": previous,
                "current_choice": current_choice,
                "cpm_summary": cpm_summary,
                "change_impact": change_impact,
                "remaining": remaining,
            },
            remaining_health=remaining_health,
            forecast=forecast,
            milestones=milestones,
        )
        trends = self._trends(versions, current_choice)
        readiness = self._readiness(
            versions=versions,
            current_choice=current_choice,
            previous=previous,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            milestones=milestones,
            remaining_count=activity_summary["remaining_count"],
            trends=trends,
        )
        command = self._command_summary(
            forecast=forecast,
            remaining=remaining,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            milestones=milestones,
        )
        story = self._schedule_story(
            current_label=current_label,
            current_data_date=current_data_date,
            previous=previous,
            previous_data_date=previous_data_date,
            forecast=forecast,
            recent=recent,
            remaining=remaining,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            actions=actions,
            readiness=readiness,
        )

        return {
            "surface": "project_schedule_hub",
            "project_key": project_key,
            "project_display_name": project_name,
            "as_of_date": as_of_date.isoformat(),
            "status": "ready" if readiness["ready_for_pm_review"] else "partial",
            "current_schedule": {
                "available": True,
                "friendly_label": current_label,
                "source_filename": current.get("display_label"),
                "data_date": _date_str(current_data_date),
                "imported_at": current.get("imported_at"),
                "source_format": current.get("source_format"),
                "activity_count": current.get("activity_count"),
                "relationship_count": current.get("relationship_count"),
            },
            "previous_update": {
                "available": previous is not None,
                "friendly_label": self._friendly_label(previous) if previous else None,
                "data_date": _date_str(previous_data_date),
                "comparison_ready": previous is not None and not readiness["identity_review_required"]["required"],
                "comparison_basis": "same_schedule_identity" if previous else None,
            },
            "readiness": readiness,
            "schedule_story": story,
            "command_summary": command,
            "recent_progress": recent,
            "change_impact": change_impact,
            "remaining_health": remaining_health,
            "critical_path": cpm_summary["critical_path"],
            "milestones": milestones,
            "computed_cpm": cpm_summary["summary"],
            "trend_summary": trends,
            "actions": {
                "preview_limit": _TOP_ACTIONS_CAP,
                "preview": actions[:_TOP_ACTIONS_CAP],
                "all_items": actions,
                "total_count": len(actions),
            },
            "technical_links": self._technical_links(project_key, current_key, previous_key, change_impact),
            "technical_evidence": {
                "collapsed_by_default": True,
                "raw_keys_available": True,
                "performance_stage_timings": self._stage_timings,
                "schedule_version_key": current_key,
                "previous_schedule_version_key": previous_key,
                "schedule_identity_key": (
                    current_choice.identity_match.get("schedule_identity_key")
                    if current_choice.identity_match
                    else None
                ),
                "source_export_evidence": "separate",
            },
        }

    # ------------------------------------------------------------------ resolvers

    def _resolve_current(
        self, project_key: str, versions: list[dict[str, Any]], *, as_of_date: date
    ) -> _VersionChoice | None:
        del project_key
        choices = [
            _VersionChoice(v, self._identity.get_match_for_version(str(v["schedule_version_key"])))
            for v in versions
        ]
        resolved = [
            c for c in choices if not _requires_identity_review(c.identity_match)
        ] or choices
        non_future = [
            c for c in resolved
            if (data_date := self._data_date(c.version)) is None or data_date <= as_of_date
        ]
        if non_future:
            resolved = non_future
        resolved.sort(key=lambda c: (_date_sort_key(self._data_date(c.version)), str(c.version.get("imported_at") or "")), reverse=True)
        if len(resolved) > 1:
            first = resolved[0]
            second = resolved[1]
            if (
                self._data_date(first.version) == self._data_date(second.version)
                and str(first.version.get("imported_at") or "") == str(second.version.get("imported_at") or "")
                and _identity_key(first.identity_match) != _identity_key(second.identity_match)
            ):
                return None
        return resolved[0] if resolved else None

    def _resolve_previous(
        self, project_key: str, current: _VersionChoice, versions: list[dict[str, Any]]
    ) -> _VersionChoice | None:
        del project_key
        current_key = str(current.version["schedule_version_key"])
        current_identity = _identity_key(current.identity_match)
        current_date = self._data_date(current.version)
        candidates: list[_VersionChoice] = []
        for version in versions:
            version_key = str(version["schedule_version_key"])
            if version_key == current_key:
                continue
            match = self._identity.get_match_for_version(version_key)
            if _requires_identity_review(match):
                continue
            if current_identity and _identity_key(match) and current_identity != _identity_key(match):
                continue
            vdate = self._data_date(version)
            if current_date and vdate and vdate >= current_date:
                continue
            candidates.append(_VersionChoice(version, match))
        candidates.sort(
            key=lambda c: (_date_sort_key(self._data_date(c.version)), str(c.version.get("imported_at") or "")),
            reverse=True,
        )
        return candidates[0] if candidates else None

    # ------------------------------------------------------------------ bounded hub reads

    def _timed(
        self,
        stage: str,
        *,
        project_key: str,
        fn: Callable[[], Any],
        schedule_version_key: str | None = None,
        query_key: str | None = None,
        cap: int | None = None,
    ) -> Any:
        started = time.perf_counter()
        result = fn()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        row_count = _result_row_count(result)
        entry = {
            "stage": stage,
            "elapsed_ms": elapsed_ms,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "query_key": query_key,
            "row_count": row_count,
            "cap": cap,
        }
        self._stage_timings.append(entry)
        if elapsed_ms >= _SLOW_STAGE_MS:
            _LOG.warning(
                "project_schedule_hub_slow_stage stage=%s elapsed_ms=%.3f project_key=%s "
                "schedule_version_key=%s query_key=%s row_count=%s cap=%s",
                stage,
                elapsed_ms,
                project_key,
                schedule_version_key,
                query_key,
                row_count,
                cap,
            )
        return result

    def explain_query_plan(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
        return [dict(row) for row in rows]

    def explain_version_resolution_queries(self, project_key: str) -> dict[str, list[dict[str, Any]]]:
        before_sql = """
            SELECT i.import_id, i.project_key, i.schedule_version_key, i.source_type,
                   i.source_format, i.import_status, i.activity_count, i.relationship_count,
                   i.cost_loaded_status, i.created_at, i.source_filename_redacted,
                   COUNT(DISTINCT a.activity_id) AS activity_count_live,
                   COUNT(DISTINCT r.id) AS relationship_count_live
            FROM schedule_file_imports i
            LEFT JOIN procore_ep_schedule_activities a
              ON a.import_id = i.import_id
            LEFT JOIN procore_ep_schedule_relationships r
              ON r.import_id = i.import_id
            WHERE i.import_status='committed' AND i.project_key=?
            GROUP BY i.import_id ORDER BY i.created_at DESC
        """
        after_sql = """
            SELECT import_id, project_key, schedule_version_key, source_type,
                   source_format, import_status, activity_count, relationship_count,
                   cost_loaded_status, created_at, source_filename_redacted
            FROM schedule_file_imports
            WHERE import_status='committed'
              AND project_key=?
              AND schedule_version_key IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ?
        """
        return {
            "before": self.explain_query_plan(before_sql, (project_key,)),
            "after": self.explain_query_plan(after_sql, (project_key, _VERSION_CAP)),
        }

    def _hub_project_versions(self, project_key: str) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT import_id, project_key, schedule_version_key, source_type,
                       source_format, import_status, activity_count, relationship_count,
                       cost_loaded_status, created_at, source_filename_redacted
                FROM schedule_file_imports
                WHERE import_status='committed'
                  AND project_key=?
                  AND schedule_version_key IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_key, _VERSION_CAP),
            ).fetchall()
            versions = [dict(row) for row in rows]
            for version in versions:
                version["activity_count_live"] = version.get("activity_count")
                version["relationship_count_live"] = version.get("relationship_count")
                version["display_label"] = version.get("source_filename_redacted")
                version["source_filename"] = version.get("source_filename_redacted")
                version["imported_at"] = version.get("created_at")
                version["data_date"] = _date_str(self._data_date(version))
                diff = conn.execute(
                    """
                    SELECT id AS diff_id FROM schedule_version_diffs
                    WHERE project_key=? AND to_schedule_version_key=?
                    ORDER BY created_at DESC, diff_id DESC
                    LIMIT 1
                    """,
                    (project_key, version["schedule_version_key"]),
                ).fetchone()
                version["default_diff_id"] = int(diff["diff_id"]) if diff else None
        return versions

    def _activity_summary(self, schedule_version_key: str) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_count,
                  SUM(CASE WHEN actual_finish IS NULL OR TRIM(actual_finish)='' THEN 1 ELSE 0 END) AS remaining_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '0') AS REAL) < 0
                           THEN 1 ELSE 0 END) AS negative_float_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) = 0
                           THEN 1 ELSE 0 END) AS zero_float_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) > 0
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) <= 10
                           THEN 1 ELSE 0 END) AS near_critical_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND constraint_type IS NOT NULL AND TRIM(constraint_type) <> ''
                           THEN 1 ELSE 0 END) AS constrained_remaining_count
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (schedule_version_key,),
            ).fetchone()
        data = dict(row) if row else {}
        return {key: int(data.get(key) or 0) for key in (
            "total_count",
            "remaining_count",
            "negative_float_count",
            "zero_float_count",
            "near_critical_count",
            "constrained_remaining_count",
        )}

    def _remaining_activity_rows(self, schedule_version_key: str, *, limit: int) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                ORDER BY
                  CASE WHEN CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) < 0 THEN 0 ELSE 1 END,
                  CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL),
                  COALESCE(remaining_finish, remaining_early_finish, finish_date, activity_id)
                LIMIT ?
                """,
                (schedule_version_key, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _activity_rows_by_ids(self, schedule_version_key: str | None, activity_ids: set[str]) -> dict[str, dict[str, Any]]:
        if not schedule_version_key or not activity_ids:
            return {}
        ids = sorted(activity_ids)
        placeholders = ",".join("?" for _ in ids)
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND activity_id IN ({placeholders})
                """,
                (schedule_version_key, *ids),
            ).fetchall()
        return {str(row["activity_id"]): dict(row) for row in rows}

    # ------------------------------------------------------------------ model pieces

    def _recent_progress(
        self,
        *,
        current_key: str,
        previous_key: str | None,
        previous_data_date: date | None,
        current_data_date: date | None,
        as_of_date: date,
    ) -> dict[str, Any]:
        start = previous_data_date or (as_of_date - timedelta(days=14))
        end = current_data_date or as_of_date
        with open_connection(self._db_path) as conn:
            completed_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                """,
                (current_key, start.isoformat(), end.isoformat()),
            ).fetchone()[0] or 0)
            started_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities c
                WHERE c.schedule_version_key=?
                  AND c.actual_start IS NOT NULL AND TRIM(c.actual_start) <> ''
                  AND (
                    (c.actual_start >= ? AND c.actual_start <= ?)
                    OR (
                      ? IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM procore_ep_schedule_activities previous
                        WHERE previous.schedule_version_key=?
                          AND previous.activity_id=c.activity_id
                          AND previous.actual_start IS NOT NULL
                          AND TRIM(previous.actual_start) <> ''
                      )
                    )
                  )
                """,
                (current_key, start.isoformat(), end.isoformat(), previous_key, previous_key),
            ).fetchone()[0] or 0)
            completed_milestone_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                  AND (is_milestone=1 OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%')
                """,
                (current_key, start.isoformat(), end.isoformat()),
            ).fetchone()[0] or 0)
            completed_critical_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                  AND (
                    is_critical=1
                    OR CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) <= 10
                  )
                """,
                (current_key, start.isoformat(), end.isoformat()),
            ).fetchone()[0] or 0)
            open_should_have_finished = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND COALESCE(remaining_finish, remaining_early_finish, finish_date) < ?
                """,
                (current_key, (current_data_date or as_of_date).isoformat()),
            ).fetchone()[0] or 0)
            completed_rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                ORDER BY actual_finish DESC, activity_id
                LIMIT ?
                """,
                (current_key, start.isoformat(), end.isoformat(), _RECENT_COMPLETIONS_CAP),
            ).fetchall()
            started_rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities c
                WHERE c.schedule_version_key=?
                  AND c.actual_start IS NOT NULL AND TRIM(c.actual_start) <> ''
                  AND (
                    (c.actual_start >= ? AND c.actual_start <= ?)
                    OR (
                      ? IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM procore_ep_schedule_activities previous
                        WHERE previous.schedule_version_key=?
                          AND previous.activity_id=c.activity_id
                          AND previous.actual_start IS NOT NULL
                          AND TRIM(previous.actual_start) <> ''
                      )
                    )
                  )
                ORDER BY c.actual_start DESC, c.activity_id
                LIMIT ?
                """,
                (current_key, start.isoformat(), end.isoformat(), previous_key, previous_key, _RECENT_STARTS_CAP),
            ).fetchall()
        return {
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "window_basis": "previous_schedule_data_date" if previous_data_date else "last_14_calendar_days",
            "completed_count": completed_count,
            "started_count": started_count,
            "completed_milestone_count": completed_milestone_count,
            "completed_critical_or_near_critical_count": completed_critical_count,
            "open_forecast_complete_count": open_should_have_finished,
            "completed_items": [_activity_item(dict(a)) for a in completed_rows],
            "started_items": [_activity_item(dict(a)) for a in started_rows],
        }

    def _direct_remaining_comparison(
        self,
        current_key: str,
        previous_key: str,
    ) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            current_rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                      AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                    """,
                    (current_key,),
                ).fetchall()
            ]
        previous_by_id = self._activity_rows_by_ids(
            previous_key,
            {str(row.get("activity_id")) for row in current_rows if row.get("activity_id")},
        )

        new_remaining = 0
        finish_later = 0
        finish_earlier = 0
        finish_changed = 0
        start_later = 0
        worsened_float = 0
        improved_float = 0
        moved_milestones = 0
        finish_changed_items: list[dict[str, Any]] = []

        for current in current_rows:
            aid = str(current.get("activity_id") or "")
            if not aid:
                continue
            previous = previous_by_id.get(aid)
            if previous is None:
                new_remaining += 1
                continue

            movement = _comparison_activity_movement(current, previous)
            finish_delta = movement.get("finish_delta_days")
            start_delta = movement.get("start_delta_days")
            float_delta = movement.get("float_delta_days")

            if finish_delta is not None and finish_delta != 0:
                finish_changed += 1
                finish_changed_items.append({"activity": _activity_item(current), **movement})
                if finish_delta > 0:
                    finish_later += 1
                    if _is_milestone(current):
                        moved_milestones += 1
                else:
                    finish_earlier += 1
            if start_delta is not None and start_delta > 0:
                start_later += 1
            if float_delta is not None and float_delta < 0:
                worsened_float += 1
            elif float_delta is not None and float_delta > 0:
                improved_float += 1

        finish_changed_items.sort(
            key=lambda item: abs(item.get("finish_delta_days") or 0),
            reverse=True,
        )
        top_wbs = Counter(
            (item["activity"].get("wbs_code") or "Unassigned") for item in finish_changed_items
        ).most_common(5)
        common_remaining = len(current_rows) - new_remaining

        return {
            "summary": {
                "common_remaining_activities": common_remaining,
                "new_remaining_activities": new_remaining,
                "finish_moved_later_count": finish_later,
                "finish_moved_earlier_count": finish_earlier,
                "finish_changed_count": finish_changed,
                "start_moved_later_count": start_later,
                "worsened_float_count": worsened_float,
                "improved_float_count": improved_float,
                "moved_remaining_milestones_count": moved_milestones,
                "changed_count": finish_changed,
            },
            "top_impacted_wbs": [{"wbs_code": code, "count": count} for code, count in top_wbs],
            "top_impacted_activities": finish_changed_items[:_TOP_IMPACTED_CAP],
            "items": finish_changed_items[:_DIRECT_REMAINING_CHANGE_CAP],
        }

    def _change_impact(
        self,
        *,
        project_key: str,
        current: dict[str, Any],
        previous: dict[str, Any] | None,
        current_key: str,
        previous_key: str | None,
    ) -> dict[str, Any]:
        if not previous or not previous_key:
            return {
                "available": False,
                "reason": "no_prior_update",
                "direct_remaining_changes": {"items": [], "summary": {}},
                "upstream_remaining_impact": {"items": [], "summary": {}},
            }
        direct_comparison = self._direct_remaining_comparison(current_key, previous_key)
        diff_id = current.get("default_diff_id")
        detail_rows = (
            self._mapping.list_diff_detail_facts(
                int(diff_id),
                project_key=project_key,
                limit=_DIRECT_REMAINING_CHANGE_CAP + _UPSTREAM_REMAINING_IMPACT_CAP + 50,
                offset=0,
            )
            if diff_id
            else []
        )
        changed_ids = {str(r.get("activity_id")) for r in detail_rows if r.get("activity_id")}
        current_by_id = self._activity_rows_by_ids(current_key, changed_ids)
        previous_by_id = self._activity_rows_by_ids(previous_key, changed_ids)
        upstream_candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for aid in sorted(changed_ids):
            current_activity = current_by_id.get(aid)
            previous_activity = previous_by_id.get(aid, {})
            if not current_activity:
                continue
            movement = _comparison_activity_movement(current_activity, previous_activity)
            if _nonempty(current_activity.get("actual_start")) or _nonempty(current_activity.get("actual_finish")):
                upstream_candidates.append((aid, current_activity, movement))
        upstream = self._upstream_remaining_impact(
            current_key=current_key,
            candidates=upstream_candidates[: _UPSTREAM_REMAINING_IMPACT_CAP * 2],
        )
        return {
            "available": True,
            "diff_id": diff_id,
            "comparison_basis": "resolved_finish_date",
            "direct_remaining_changes": {
                **direct_comparison,
                "default_limit": _DIRECT_REMAINING_CHANGE_CAP,
            },
            "upstream_remaining_impact": {
                "summary": {
                    "changed_upstream_count": len(upstream),
                    "affected_remaining_successor_count": sum(int(u.get("affected_remaining_successor_count") or 0) for u in upstream),
                },
                "items": upstream[:_UPSTREAM_REMAINING_IMPACT_CAP],
                "default_limit": _UPSTREAM_REMAINING_IMPACT_CAP,
                "caveat": "Associations are based on persisted relationships and changed activities; they are review cues, not causation findings.",
            },
        }

    def _upstream_remaining_impact(
        self,
        *,
        current_key: str,
        candidates: list[tuple[str, dict[str, Any], dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        out: list[dict[str, Any]] = []
        with open_connection(self._db_path) as conn:
            for aid, activity, movement in candidates:
                rows = conn.execute(
                    """
                    SELECT r.successor_activity_id,
                           a.total_float, a.derived_total_float_days, a.explicit_total_float_days,
                           a.is_critical
                    FROM procore_ep_schedule_relationships r
                    JOIN procore_ep_schedule_activities a
                      ON a.schedule_version_key=r.schedule_version_key
                     AND a.activity_id=r.successor_activity_id
                    WHERE r.schedule_version_key=?
                      AND r.predecessor_activity_id=?
                      AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                    LIMIT ?
                    """,
                    (current_key, aid, _UPSTREAM_REMAINING_IMPACT_CAP),
                ).fetchall()
                if not rows:
                    continue
                critical_affected = sum(1 for row in rows if _is_critical_or_near(dict(row)))
                out.append(
                    {
                        "activity": _activity_item(activity),
                        "language": "appears associated with remaining successor movement; review sequence and logic",
                        "affected_remaining_successor_count": len(rows),
                        "affected_critical_or_near_count": critical_affected,
                        **movement,
                    }
                )
                if len(out) >= _UPSTREAM_REMAINING_IMPACT_CAP:
                    break
        return out

    def _computed_cpm(self, current_key: str) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            runs: dict[str, dict[str, Any]] = {}
            for row in conn.execute(
                    """
                    SELECT cpm_run_id, calculation_type, cpm_recalculation_status,
                           analysis_scope, source_run_id, created_at, node_count,
                           edge_count, diagnostic_count, computed_activity_count,
                           blocked_activity_count, is_acyclic
                    FROM schedule_cpm_runs
                    WHERE schedule_version_key=?
                    ORDER BY created_at DESC, cpm_run_id DESC
                    """,
                    (current_key,),
            ).fetchall():
                calc_type = str(row["calculation_type"])
                if calc_type not in runs:
                    runs[calc_type] = dict(row)
            source_run = next(
                (
                    runs[k]
                    for k in ("criticality", "float", "backward_pass", "forward_pass")
                    if runs.get(k)
                ),
                None,
            )
            critical_count = 0
            near_count = 0
            if source_run:
                row = conn.execute(
                    """
                    SELECT
                      SUM(CASE WHEN car.computed_critical_flag=1 THEN 1 ELSE 0 END) AS critical_count,
                      SUM(CASE WHEN car.computed_near_critical_flag=1 THEN 1 ELSE 0 END) AS near_count
                    FROM schedule_cpm_activity_results car
                    JOIN procore_ep_schedule_activities a
                      ON a.schedule_version_key=car.schedule_version_key
                     AND a.activity_id=car.activity_id
                    WHERE car.schedule_version_key=?
                      AND car.cpm_run_id=?
                      AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                    """,
                    (current_key, source_run["cpm_run_id"]),
                ).fetchone()
                critical_count = int((row["critical_count"] if row else 0) or 0)
                near_count = int((row["near_count"] if row else 0) or 0)
            lp_run = runs.get("longest_path")
            primary_path = None
            path_items: list[dict[str, Any]] = []
            if lp_run:
                primary_path = conn.execute(
                    """
                    SELECT path_id, path_type, path_rank, path_status, path_basis,
                           start_activity_id, end_activity_id, activity_count,
                           relationship_count, path_duration, path_start_offset_days,
                           path_finish_offset_days, path_total_float
                    FROM schedule_cpm_paths
                    WHERE cpm_run_id=? AND schedule_version_key=?
                    ORDER BY path_rank, path_id
                    LIMIT 1
                    """,
                    (lp_run["cpm_run_id"], current_key),
                ).fetchone()
                if primary_path:
                    path_items = [
                        dict(row)
                        for row in conn.execute(
                            """
                            SELECT activity_id, activity_name,
                                   computed_early_start AS forecast_start,
                                   computed_early_finish AS forecast_finish,
                                   computed_total_float AS total_float,
                                   path_sequence
                            FROM schedule_cpm_path_activities
                            WHERE path_id=?
                            ORDER BY path_sequence
                            LIMIT ?
                            """,
                            (primary_path["path_id"], _CRITICAL_PATH_PREVIEW_CAP),
                        ).fetchall()
                    ]
        available = bool(runs)
        missing = [
            kind
            for kind in ("graph_diagnostics", "forward_pass", "backward_pass", "float", "longest_path", "criticality")
            if kind not in runs
        ]
        return {
            "summary": {
                "available": available,
                "summary": "Computed CPM is available for this update." if available else "Computed CPM is unavailable for this update.",
                "critical_remaining_count": critical_count,
                "near_critical_remaining_count": near_count,
                "drilldown_url": "/schedules/cpm",
                "missing_dependency_reasons": missing,
                "evidence_class": "application_computed_cpm",
                "source_export_evidence": "separate",
            },
            "critical_path": {
                "available": bool(primary_path),
                "basis": "computed_cpm" if primary_path else "unavailable",
                "activity_count": dict(primary_path).get("activity_count") if primary_path else None,
                "items": [_activity_item(a) for a in path_items],
                "default_limit": _CRITICAL_PATH_PREVIEW_CAP,
                "caveats": [] if primary_path else ["No persisted longest-path CPM run is available."],
            },
        }

    def _remaining_health(
        self,
        *,
        remaining: list[dict[str, Any]],
        activity_summary: dict[str, Any],
        change_impact: dict[str, Any],
        cpm_summary: dict[str, Any],
        current_choice: _VersionChoice,
        previous: dict[str, Any] | None,
    ) -> dict[str, Any]:
        del remaining
        remaining_count = int(activity_summary.get("remaining_count") or 0)
        negative_float_count = int(activity_summary.get("negative_float_count") or 0)
        zero_float_count = int(activity_summary.get("zero_float_count") or 0)
        near_count = int(activity_summary.get("near_critical_count") or 0)
        constrained_count = int(activity_summary.get("constrained_remaining_count") or 0)
        drivers: list[str] = []
        if negative_float_count:
            drivers.append(f"{negative_float_count} remaining activities have negative float.")
        if change_impact.get("available") and change_impact["direct_remaining_changes"]["summary"].get("finish_moved_later_count"):
            drivers.append("Remaining activities moved later since the prior update.")
        if _requires_identity_review(current_choice.identity_match):
            drivers.append("Schedule identity review is required before comparison is reliable.")
        if not previous:
            drivers.append("No prior comparable update is available.")
        if not cpm_summary["summary"]["available"]:
            drivers.append("Computed CPM is unavailable.")
        if not drivers:
            drivers.append("Remaining-work schedule indicators are available for review.")
        status = "unknown"
        if remaining_count:
            status = "good"
            if near_count or constrained_count or not previous:
                status = "watch"
            if negative_float_count or near_count >= 10:
                status = "at_risk"
            if _requires_identity_review(current_choice.identity_match):
                status = "blocked"
        return {
            "status": status,
            "remaining_activity_count": remaining_count,
            "drivers": drivers[:5],
            "float_pressure": {
                "negative_float_count": negative_float_count,
                "zero_float_count": zero_float_count,
                "near_critical_count": near_count,
            },
            "logic_risk": {
                "constrained_remaining_count": constrained_count,
                "missing_logic_count": None,
                "status": "relationship_detail_available" if remaining_count else "not_applicable",
            },
            "comparison_readiness": {
                "prior_update_available": previous is not None,
                "identity_review_required": _requires_identity_review(current_choice.identity_match),
            },
        }

    def _milestones(
        self,
        current_key: str,
        previous_key: str | None,
        recent: dict[str, Any],
    ) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            remaining_milestone_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND (
                    is_milestone=1
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%substantial completion%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%final completion%'
                  )
                """,
                (current_key,),
            ).fetchone()[0] or 0)
            at_risk_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND (
                    is_milestone=1
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%substantial completion%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%final completion%'
                  )
                  AND (
                    is_critical=1
                    OR CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) <= 10
                  )
                """,
                (current_key,),
            ).fetchone()[0] or 0)
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                      AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                      AND (
                        is_milestone=1
                        OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%'
                        OR LOWER(COALESCE(activity_name, '')) LIKE '%substantial completion%'
                        OR LOWER(COALESCE(activity_name, '')) LIKE '%final completion%'
                      )
                    ORDER BY COALESCE(remaining_finish, remaining_early_finish, finish_date, activity_id)
                    LIMIT ?
                    """,
                    (current_key, _MILESTONE_CAP),
                ).fetchall()
            ]
        previous_by_id = self._activity_rows_by_ids(previous_key, {str(a.get("activity_id")) for a in rows})
        moved_later = 0
        items = []
        for a in rows:
            prev = previous_by_id.get(str(a.get("activity_id")), {})
            movement = _date_delta_days(_parse_date(_comparison_finish_field(prev)), _parse_date(_comparison_finish_field(a)))
            if movement and movement > 0:
                moved_later += 1
            item = _activity_item(a)
            item["forecast_date"] = _comparison_finish_field(a)
            item["movement_days"] = movement
            item["inferred"] = not _truthy(a.get("is_milestone"))
            items.append(item)
        return {
            "items": items,
            "remaining_milestone_count": remaining_milestone_count,
            "at_risk_count": at_risk_count,
            "moved_later_count": moved_later,
            "completed_recently_count": recent.get("completed_milestone_count", 0),
        }

    def _forecast_finish(
        self, current_key: str, previous_key: str | None
    ) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            current_finish = _parse_date(conn.execute(
                f"""
                SELECT MAX({_comparison_finish_sql("a")})
                FROM procore_ep_schedule_activities a
                WHERE a.schedule_version_key=?
                  AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                """,
                (current_key,),
            ).fetchone()[0])
            previous_finish = None
            if previous_key:
                previous_finish = _parse_date(conn.execute(
                    f"""
                    SELECT MAX({_comparison_finish_sql("p")})
                    FROM procore_ep_schedule_activities c
                    JOIN procore_ep_schedule_activities p
                      ON p.activity_id=c.activity_id
                     AND p.schedule_version_key=?
                    WHERE c.schedule_version_key=?
                      AND (c.actual_finish IS NULL OR TRIM(c.actual_finish)='')
                    """,
                    (previous_key, current_key),
                ).fetchone()[0])
        return {
            "current_forecast_finish": _date_str(current_finish),
            "previous_forecast_finish": _date_str(previous_finish),
            "movement_days": _date_delta_days(previous_finish, current_finish),
        }

    def _actions(
        self,
        *,
        readiness_inputs: dict[str, Any],
        remaining_health: dict[str, Any],
        forecast: dict[str, Any],
        milestones: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        def add(priority: int, code: str, title: str, explanation: str, evidence: str, review: str) -> None:
            actions.append(
                {
                    "priority": priority,
                    "code": code,
                    "title": title,
                    "explanation": _safe_story_text(explanation),
                    "evidence_basis": evidence,
                    "recommended_review": _safe_story_text(review),
                    "drilldown_anchor": code,
                }
            )

        current_choice = readiness_inputs["current_choice"]
        if _requires_identity_review(current_choice.identity_match):
            add(100, "identity_review", "Resolve schedule series match", "Comparison is blocked until the current update is matched to the correct schedule series.", "schedule identity match requires review", "Open identity review before relying on update comparison.")
        if not readiness_inputs["previous"]:
            add(90, "no_prior_update", "Import or confirm a prior update", "No comparable prior update is available, so movement and trend context are limited.", "no prior comparable schedule", "Confirm whether an earlier update should be imported or matched.")
        neg = remaining_health["float_pressure"]["negative_float_count"]
        if neg:
            add(80, "negative_float", "Review remaining negative-float work", f"{neg} remaining activities are below zero float.", "remaining-work float pressure", "Review the activities and confirm the current completion sequence.")
        movement = forecast.get("movement_days")
        if movement and movement > 0:
            add(75, "forecast_finish_moved_later", "Review forecast finish movement", f"Forecast finish moved {movement} days later versus comparable remaining work.", "current-vs-previous forecast finish comparison", "Confirm which activities are driving the finish movement.")
        direct = readiness_inputs["change_impact"].get("direct_remaining_changes", {}).get("summary", {})
        if direct.get("finish_moved_later_count"):
            add(70, "remaining_work_moved_later", "Review remaining activities that moved later", f"{direct['finish_moved_later_count']} remaining activities moved later.", "direct persisted activity comparison", "Review the top changed remaining activities and affected WBS areas.")
        upstream = readiness_inputs["change_impact"].get("upstream_remaining_impact", {}).get("summary", {})
        if upstream.get("changed_upstream_count"):
            add(60, "upstream_sequence_review", "Review upstream changes tied to remaining successors", "Completed or in-progress changed activities appear associated with remaining successor work.", "persisted relationships and changed activity facts", "Review sequence and logic before the next update.")
        if milestones.get("moved_later_count"):
            add(55, "milestones_moved", "Review moved remaining milestones", f"{milestones['moved_later_count']} remaining milestones moved later.", "milestone forecast comparison", "Confirm milestone dates and downstream implications.")
        if not readiness_inputs["cpm_summary"]["summary"]["available"]:
            add(40, "cpm_unavailable", "Confirm critical path evidence", "Computed CPM is unavailable, so critical-path confidence is limited.", "computed CPM run availability", "Use technical CPM drilldown or run the approved CPM workflow outside this page.")
        actions.sort(key=lambda a: (-int(a["priority"]), str(a["code"])))
        return actions[:_ALL_ACTIONS_CAP]

    def _readiness(
        self,
        *,
        versions: list[dict[str, Any]],
        current_choice: _VersionChoice,
        previous: dict[str, Any] | None,
        cpm_summary: dict[str, Any],
        change_impact: dict[str, Any],
        milestones: dict[str, Any],
        remaining_count: int,
        trends: dict[str, Any],
    ) -> dict[str, Any]:
        del versions, milestones
        identity_required = _requires_identity_review(current_choice.identity_match)
        checks = {
            "no_schedule": {"required": False, "reason": None},
            "no_prior_update": {"required": previous is None, "reason": "no comparable prior update" if previous is None else None},
            "identity_review_required": {"required": identity_required, "reason": "schedule identity match requires review" if identity_required else None},
            "cpm_unavailable": {"required": not cpm_summary["summary"]["available"], "reason": "no persisted computed CPM run" if not cpm_summary["summary"]["available"] else None},
            "diff_unavailable": {"required": not change_impact.get("available"), "reason": change_impact.get("reason") if not change_impact.get("available") else None},
            "baseline_unavailable": {"required": True, "reason": "baseline summary is not available in the Project Schedule Hub v1 contract"},
            "no_remaining_activities": {"required": remaining_count == 0, "reason": "all activities have actual finish values" if remaining_count == 0 else None},
            "insufficient_trend_history": {"required": not trends.get("available"), "reason": trends.get("reason") if not trends.get("available") else None},
        }
        blocking = identity_required or remaining_count == 0
        return {
            **checks,
            "ready_for_pm_review": not blocking,
            "partial_reasons": [
                key for key, value in checks.items() if value.get("required")
            ],
        }

    def _trends(self, versions: list[dict[str, Any]], current_choice: _VersionChoice) -> dict[str, Any]:
        current_identity = _identity_key(current_choice.identity_match)
        comparable: list[dict[str, Any]] = []
        for version in versions:
            match = self._identity.get_match_for_version(str(version["schedule_version_key"]))
            if current_identity and _identity_key(match) != current_identity:
                continue
            comparable.append(version)
        comparable.sort(key=lambda v: _date_sort_key(self._data_date(v)))
        if len(comparable) < 2:
            return {
                "available": False,
                "reason": "at_least_two_comparable_updates_required",
                "minimum_required": 2,
                "comparable_update_count": len(comparable),
                "series": [],
            }
        return {
            "available": True,
            "reason": None,
            "minimum_required": 2,
            "comparable_update_count": len(comparable),
            "series": [
                {
                    "friendly_label": self._friendly_label(v),
                    "data_date": _date_str(self._data_date(v)),
                    "activity_count": v.get("activity_count"),
                }
                for v in comparable[-_VERSION_CAP:]
            ],
        }

    def _command_summary(
        self,
        *,
            forecast: dict[str, Any],
            remaining: list[dict[str, Any]],
        remaining_health: dict[str, Any],
        cpm_summary: dict[str, Any],
        change_impact: dict[str, Any],
        milestones: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "forecast_finish": forecast.get("current_forecast_finish"),
            "forecast_finish_delta_days": forecast.get("movement_days"),
            "remaining_activity_count": remaining_health["remaining_activity_count"],
            "remaining_milestone_count": milestones.get("remaining_milestone_count", 0),
            "critical_remaining_count": cpm_summary["summary"].get("critical_remaining_count") or sum(1 for a in remaining if _truthy(a.get("is_critical"))),
            "near_critical_remaining_count": cpm_summary["summary"].get("near_critical_remaining_count") or remaining_health["float_pressure"]["near_critical_count"],
            "negative_float_remaining_count": remaining_health["float_pressure"]["negative_float_count"],
            "zero_float_remaining_count": remaining_health["float_pressure"]["zero_float_count"],
            "remaining_finish_moved_later_count": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("finish_moved_later_count", 0),
            "remaining_finish_moved_earlier_count": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("finish_moved_earlier_count", 0),
            "remaining_finish_changed_count": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("finish_changed_count", 0),
            "new_remaining_activities": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("new_remaining_activities", 0),
            "health_status": remaining_health["status"],
            "health_summary": remaining_health["drivers"][0] if remaining_health["drivers"] else None,
        }

    def _schedule_story(
        self,
        *,
        current_label: str,
        current_data_date: date | None,
        previous: dict[str, Any] | None,
        previous_data_date: date | None,
        forecast: dict[str, Any],
        recent: dict[str, Any],
        remaining: list[dict[str, Any]],
        remaining_health: dict[str, Any],
        cpm_summary: dict[str, Any],
        change_impact: dict[str, Any],
        actions: list[dict[str, Any]],
        readiness: dict[str, Any],
    ) -> dict[str, Any]:
        movement = forecast.get("movement_days")
        if movement is None:
            headline = f"{current_label} is ready for remaining-work review."
        elif movement > 0:
            headline = f"Forecast finish moved {movement} days later since the previous update."
        elif movement < 0:
            headline = f"Forecast finish moved {abs(movement)} days earlier since the previous update."
        else:
            headline = "Forecast finish is unchanged from the previous update."
        primary_driver = "No comparable prior update is available."
        if change_impact.get("available"):
            summary = change_impact["direct_remaining_changes"]["summary"]
            later = int(summary.get("finish_moved_later_count") or 0)
            earlier = int(summary.get("finish_moved_earlier_count") or 0)
            if later and earlier:
                primary_driver = (
                    f"{later} remaining activities moved later and {earlier} moved earlier "
                    "in the persisted update comparison."
                )
            elif later:
                primary_driver = f"{later} remaining activities moved later in the persisted update comparison."
            elif earlier:
                primary_driver = f"{earlier} remaining activities moved earlier in the persisted update comparison."
            else:
                primary_driver = "No remaining finish movement detected in the persisted update comparison."
        recent_summary = f"{recent['completed_count']} activities completed and {recent['started_count']} activities started in the review window."
        remaining_summary = f"{remaining_health['remaining_activity_count']} activities remain open; health is {remaining_health['status'].replace('_', ' ')}."
        cp_summary = (
            f"Computed CPM shows {cpm_summary['summary']['critical_remaining_count']} critical and {cpm_summary['summary']['near_critical_remaining_count']} near-critical remaining activities."
            if cpm_summary["summary"]["available"]
            else "Computed CPM is unavailable, so critical-path confidence is limited."
        )
        review_next = actions[0]["title"] if actions else "Review remaining work and milestone movement."
        synopsis = (
            f"The current update is {current_label} with data date {_date_str(current_data_date) or 'unknown'}. "
            f"Previous data date is {_date_str(previous_data_date) if previous else 'not available'}. "
            f"{recent_summary} {remaining_summary} {primary_driver}"
        )
        caveats = []
        if readiness["identity_review_required"]["required"]:
            caveats.append("Schedule identity review is required before relying on update comparison.")
        if readiness["diff_unavailable"]["required"]:
            caveats.append("Version-diff detail is unavailable for this project update.")
        if readiness["cpm_unavailable"]["required"]:
            caveats.append("Computed CPM is unavailable for this update.")
        caveats.append("This summary identifies schedule movement and review priorities. It does not determine delay causation, responsibility, entitlement, or compensability.")
        return {
            "headline": _safe_story_text(headline),
            "synopsis": _safe_story_text(synopsis),
            "primary_change_driver": _safe_story_text(primary_driver),
            "recent_progress_summary": _safe_story_text(recent_summary),
            "remaining_work_summary": _safe_story_text(remaining_summary),
            "critical_path_summary": _safe_story_text(cp_summary),
            "review_next_summary": _safe_story_text(review_next),
            "caveats": [_safe_story_text(c) for c in caveats],
        }

    # ------------------------------------------------------------------ states and helpers

    def _empty_summary(self, project_key: str, project_name: str, as_of_date: date) -> dict[str, Any]:
        readiness = {
            "no_schedule": {"required": True, "reason": "no committed schedule imports for project"},
            "no_prior_update": {"required": True, "reason": "no schedule update available"},
            "identity_review_required": {"required": False, "reason": None},
            "cpm_unavailable": {"required": True, "reason": "no schedule update available"},
            "diff_unavailable": {"required": True, "reason": "no schedule update available"},
            "baseline_unavailable": {"required": True, "reason": "no schedule update available"},
            "no_remaining_activities": {"required": False, "reason": None},
            "insufficient_trend_history": {"required": True, "reason": "at_least_two_comparable_updates_required"},
            "ready_for_pm_review": False,
            "partial_reasons": ["no_schedule", "no_prior_update", "cpm_unavailable", "diff_unavailable", "baseline_unavailable", "insufficient_trend_history"],
        }
        return {
            "surface": "project_schedule_hub",
            "project_key": project_key,
            "project_display_name": project_name,
            "as_of_date": as_of_date.isoformat(),
            "status": "no_schedule",
            "current_schedule": {"available": False},
            "previous_update": {"available": False},
            "readiness": readiness,
            "schedule_story": {
                "headline": "No schedule update is imported for this project.",
                "synopsis": "Import a schedule update to review remaining work, movement, critical path, and PM review actions.",
                "primary_change_driver": "No schedule data is available.",
                "recent_progress_summary": "Recent progress is unavailable until a schedule is imported.",
                "remaining_work_summary": "Remaining work is unavailable until a schedule is imported.",
                "critical_path_summary": "Critical path is unavailable until schedule and CPM evidence are available.",
                "review_next_summary": "Import a schedule update for this project.",
                "caveats": ["No schedule conclusions are available without imported schedule data."],
            },
            "command_summary": {},
            "recent_progress": {},
            "change_impact": {"available": False, "reason": "no_schedule"},
            "remaining_health": {"status": "unknown", "drivers": ["No schedule data is available."]},
            "critical_path": {"available": False},
            "milestones": {"items": []},
            "computed_cpm": {"available": False, "summary": "Computed CPM is unavailable because no schedule is imported."},
            "trend_summary": {"available": False, "reason": "at_least_two_comparable_updates_required", "comparable_update_count": 0},
            "actions": {
                "preview_limit": 5,
                "preview": [{
                    "priority": 100,
                    "code": "import_schedule",
                    "title": "Import a schedule update",
                    "explanation": "No schedule is imported for this project.",
                    "evidence_basis": "schedule import list",
                    "recommended_review": "Open schedule import and upload the current project schedule.",
                    "drilldown_anchor": "import_schedule",
                }],
                "all_items": [],
                "total_count": 1,
            },
            "technical_links": {"schedule_import_url": f"/schedules/imports?project={project_key}"},
            "technical_evidence": {"collapsed_by_default": True, "raw_keys_available": False},
        }

    def _review_required_summary(
        self, project_key: str, project_name: str, as_of_date: date, versions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        out = self._empty_summary(project_key, project_name, as_of_date)
        out["status"] = "review_required"
        out["current_schedule"] = {"available": False, "candidate_count": len(versions)}
        out["readiness"]["no_schedule"] = {"required": False, "reason": None}
        out["readiness"]["identity_review_required"] = {"required": True, "reason": "multiple possible current schedules require review"}
        out["schedule_story"]["headline"] = "Schedule identity review is required."
        out["schedule_story"]["synopsis"] = "Multiple possible current schedule updates exist. Resolve schedule identity before relying on comparison or remaining-work health."
        return out

    def _project_display_name(self, project_key: str) -> str:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT display_name FROM procore_ep_projects
                WHERE project_key=?
                ORDER BY is_current DESC, updated_utc DESC
                LIMIT 1
                """,
                (project_key,),
            ).fetchone()
        return str(row[0]) if row and row[0] else project_key

    @staticmethod
    def _data_date(version: dict[str, Any] | None) -> date | None:
        if not version:
            return None
        return _parse_date(version.get("data_date")) or _parse_date(str(version.get("schedule_version_key") or "").split("|")[-1])

    @staticmethod
    def _friendly_label(version: dict[str, Any] | None) -> str:
        if not version:
            return ""
        for value in (version.get("display_label"), version.get("source_filename"), version.get("source_filename_redacted")):
            label = _label_from_source(value)
            if label:
                return label
        data_date = ProjectScheduleSummaryService._data_date(version)
        if data_date:
            return f"Update {data_date.strftime('%b %d, %Y')}"
        raw = str(version.get("schedule_version_key") or "")
        return "Schedule Update" if _RAW_KEY_PATTERN.match(raw) else raw or "Schedule Update"

    @staticmethod
    def _technical_links(
        project_key: str, current_key: str, previous_key: str | None, change_impact: dict[str, Any]
    ) -> dict[str, Any]:
        encoded_current = current_key.replace("|", "%7C")
        links = {
            "schedule_versions_url": f"/schedules/versions?project={project_key}",
            "schedule_health_url": f"/schedules/quality?project={project_key}&version={encoded_current}",
            "computed_cpm_url": f"/schedules/cpm?project={project_key}&version={encoded_current}",
            "activities_url": f"/schedules/activities?project={project_key}&version={encoded_current}",
            "identity_review_url": f"/schedules/identity-review?project={project_key}",
            "schedule_import_url": f"/schedules/imports?project={project_key}",
        }
        if change_impact.get("diff_id"):
            links["version_comparison_url"] = f"/schedules/version-diff?project={project_key}&diff_id={change_impact['diff_id']}"
        elif previous_key:
            links["version_comparison_url"] = f"/schedules/version-diff?project={project_key}"
        return links


def _result_row_count(result: Any) -> int | None:
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        for key in ("total_count", "remaining_count", "completed_count", "activity_count"):
            value = result.get(key)
            if isinstance(value, int):
                return value
        for key in ("items", "series", "preview", "all_items"):
            value = result.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _date_str(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date_sort_key(value: date | None) -> str:
    return value.isoformat() if value else ""


def _date_delta_days(old: date | None, new: date | None) -> int | None:
    if not old or not new:
        return None
    return (new - old).days


def _date_in_window(value: date | None, start: date, end: date) -> bool:
    return bool(value and start <= value <= end)


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float_days(activity: dict[str, Any]) -> float | None:
    for key in ("total_float", "derived_total_float_days", "explicit_total_float_days", "computed_total_float"):
        value = activity.get(key)
        if value is None or str(value).strip() == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _comparison_finish_sql(alias: str) -> str:
    return (
        f"COALESCE(NULLIF(TRIM({alias}.remaining_finish), ''), "
        f"NULLIF(TRIM({alias}.finish_date), ''), "
        f"NULLIF(TRIM({alias}.remaining_early_finish), ''))"
    )


def _comparison_start_sql(alias: str) -> str:
    return (
        f"COALESCE(NULLIF(TRIM({alias}.remaining_start), ''), "
        f"NULLIF(TRIM({alias}.start_date), ''), "
        f"NULLIF(TRIM({alias}.remaining_early_start), ''))"
    )


def _comparison_finish_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_finish", "finish_date", "remaining_early_finish"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _comparison_start_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_start", "start_date", "remaining_early_start"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _forecast_finish_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_finish", "remaining_early_finish", "finish_date", "planned_finish", "target_finish", "baseline_finish"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _forecast_start_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_start", "remaining_early_start", "start_date", "planned_start", "target_start", "baseline_start"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _comparison_activity_movement(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_delta_days": _date_delta_days(
            _parse_date(_comparison_start_field(previous)),
            _parse_date(_comparison_start_field(current)),
        ),
        "finish_delta_days": _date_delta_days(
            _parse_date(_comparison_finish_field(previous)),
            _parse_date(_comparison_finish_field(current)),
        ),
        "float_delta_days": (
            None
            if _float_days(previous) is None or _float_days(current) is None
            else _float_days(current) - _float_days(previous)
        ),
    }


def _activity_movement(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return _comparison_activity_movement(current, previous)


def _activity_item(activity: dict[str, Any]) -> dict[str, Any]:
    return {
        "activity_id": activity.get("activity_id"),
        "activity_name": activity.get("activity_name"),
        "wbs_code": activity.get("wbs_code"),
        "wbs_path": activity.get("wbs_path"),
        "forecast_start": _forecast_start_field(activity),
        "forecast_finish": _forecast_finish_field(activity),
        "actual_start": activity.get("actual_start"),
        "actual_finish": activity.get("actual_finish"),
        "total_float": activity.get("total_float") or activity.get("computed_total_float"),
    }


def _is_milestone(activity: dict[str, Any]) -> bool:
    if _truthy(activity.get("is_milestone")):
        return True
    name = str(activity.get("activity_name") or "").lower()
    duration = str(activity.get("duration_remaining") or activity.get("duration_original") or "").strip()
    return ("milestone" in name or "substantial completion" in name or "final completion" in name) and duration in {"", "0", "0.0"}


def _is_critical_or_near(activity: dict[str, Any]) -> bool:
    if _truthy(activity.get("is_critical")) or _truthy(activity.get("computed_critical_flag")) or _truthy(activity.get("computed_near_critical_flag")):
        return True
    f = _float_days(activity)
    return f is not None and f <= 10


def _successor_map(relationships: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for rel in relationships:
        pred = str(rel.get("predecessor_activity_id") or "")
        succ = str(rel.get("successor_activity_id") or "")
        if pred and succ:
            out.setdefault(pred, []).append(succ)
    return out


def _remaining_successors(
    activity_id: str, successor_map: dict[str, list[str]], remaining_ids: set[str]
) -> list[str]:
    found: list[str] = []
    seen = {activity_id}
    queue: deque[str] = deque(successor_map.get(activity_id, []))
    while queue and len(found) < 25:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if node in remaining_ids:
            found.append(node)
        queue.extend(successor_map.get(node, []))
    return found


def _identity_key(match: dict[str, Any] | None) -> str | None:
    return str(match.get("schedule_identity_key")) if match and match.get("schedule_identity_key") else None


def _requires_identity_review(match: dict[str, Any] | None) -> bool:
    return bool(match and int(match.get("requires_review") or 0))


def _label_from_source(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip().split("/")[-1]
    text = re.sub(r"\.(zip|xer|xml|pmxml|csv)$", "", text, flags=re.I)
    if not text or _RAW_KEY_PATTERN.match(text):
        return None
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{1,3})\b", text.upper())
    return match.group(1) if match else text


def _safe_story_text(text: str) -> str:
    safe = text
    for word in _FORBIDDEN_STORY_WORDS:
        safe = re.sub(re.escape(word), "schedule movement", safe, flags=re.I)
    return safe
