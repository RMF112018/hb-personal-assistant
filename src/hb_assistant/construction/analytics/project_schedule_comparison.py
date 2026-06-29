"""Shared schedule version comparison for Project Schedule Hub Phase 2."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from hb_assistant.store.connection import open_connection

_ACTIVITY_COLUMNS = """
    activity_id, activity_name, wbs_code, wbs_path, start_date, finish_date,
    actual_start, actual_finish, remaining_start, remaining_finish,
    remaining_early_start, remaining_early_finish, duration_original,
    duration_remaining, constraint_type, is_critical, is_milestone,
    total_float, derived_total_float_days, explicit_total_float_days,
    target_start, target_finish, baseline_start, baseline_finish
"""

DRILLDOWN_TYPES = frozenset(
    {
        "remaining_later",
        "remaining_earlier",
        "finish_changed",
        "new_remaining",
        "worsened_float",
        "improved_float",
        "milestones_later",
        "negative_float",
        "critical_remaining",
        "near_critical_remaining",
        "upstream_cues",
        "baseline_remaining_later",
        "baseline_finish_changed",
        "baseline_milestones_later",
    }
)


def comparison_finish_sql(alias: str) -> str:
    return (
        f"COALESCE(NULLIF(TRIM({alias}.remaining_finish), ''), "
        f"NULLIF(TRIM({alias}.finish_date), ''), "
        f"NULLIF(TRIM({alias}.remaining_early_finish), ''))"
    )


def comparison_finish_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_finish", "finish_date", "remaining_early_finish"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def comparison_start_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_start", "start_date", "remaining_early_start"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def comparison_activity_movement(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_delta_days": _date_delta_days(
            _parse_date(comparison_start_field(previous)),
            _parse_date(comparison_start_field(current)),
        ),
        "finish_delta_days": _date_delta_days(
            _parse_date(comparison_finish_field(previous)),
            _parse_date(comparison_finish_field(current)),
        ),
        "float_delta_days": (
            None
            if _float_days(previous) is None or _float_days(current) is None
            else _float_days(current) - _float_days(previous)
        ),
    }


class ProjectScheduleComparisonService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def compare_versions(
        self,
        *,
        left_key: str,
        right_key: str | None,
        remaining_only: bool = True,
    ) -> dict[str, Any]:
        """Compare left (current) activities to right (prior/baseline) by activity_id."""
        if not right_key:
            return {"summary": {}, "rows": [], "removed_activity_ids": []}

        with open_connection(self._db_path) as conn:
            left_rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                      AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                    """,
                    (left_key,),
                ).fetchall()
            ]
            right_rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                    """,
                    (right_key,),
                ).fetchall()
            ]
        from .project_schedule_canonical_metrics import ProjectScheduleCanonicalMetricService

        cpm_by_id = ProjectScheduleCanonicalMetricService(db_path=self._db_path).cpm_flags_by_activity(left_key)

        right_by_id = {str(row.get("activity_id")): row for row in right_rows if row.get("activity_id")}
        left_ids = {str(row.get("activity_id")) for row in left_rows if row.get("activity_id")}
        removed_ids = sorted(aid for aid in right_by_id if aid not in left_ids)

        rows: list[dict[str, Any]] = []
        new_remaining = 0
        finish_later = 0
        finish_earlier = 0
        finish_changed = 0
        start_later = 0
        worsened_float = 0
        improved_float = 0
        moved_milestones = 0

        for left in left_rows:
            aid = str(left.get("activity_id") or "")
            if not aid:
                continue
            right = right_by_id.get(aid)
            if right is None:
                new_remaining += 1
                if remaining_only:
                    rows.append(self._drilldown_row(left, {}, cpm_by_id.get(aid)))
                continue

            movement = comparison_activity_movement(left, right)
            finish_delta = movement.get("finish_delta_days")
            start_delta = movement.get("start_delta_days")
            float_delta = movement.get("float_delta_days")
            row = self._drilldown_row(left, right, cpm_by_id.get(aid), movement)

            if finish_delta is not None and finish_delta != 0:
                finish_changed += 1
                if finish_delta > 0:
                    finish_later += 1
                    if _is_milestone(left):
                        moved_milestones += 1
                else:
                    finish_earlier += 1
            if start_delta is not None and start_delta > 0:
                start_later += 1
            if float_delta is not None and float_delta < 0:
                worsened_float += 1
            elif float_delta is not None and float_delta > 0:
                improved_float += 1
            rows.append(row)

        common_remaining = len(left_rows) - new_remaining
        return {
            "summary": {
                "common_remaining_activities": common_remaining,
                "new_remaining_activities": new_remaining,
                "removed_activities": len(removed_ids),
                "finish_moved_later_count": finish_later,
                "finish_moved_earlier_count": finish_earlier,
                "finish_changed_count": finish_changed,
                "start_moved_later_count": start_later,
                "worsened_float_count": worsened_float,
                "improved_float_count": improved_float,
                "moved_remaining_milestones_count": moved_milestones,
                "changed_count": finish_changed,
            },
            "rows": rows,
            "removed_activity_ids": removed_ids,
        }

    def filter_rows(self, rows: list[dict[str, Any]], drilldown_type: str) -> list[dict[str, Any]]:
        if drilldown_type in {"remaining_later", "baseline_remaining_later"}:
            return [r for r in rows if (r.get("finish_delta_days") or 0) > 0]
        if drilldown_type == "remaining_earlier":
            return [r for r in rows if (r.get("finish_delta_days") or 0) < 0]
        if drilldown_type in {"finish_changed", "baseline_finish_changed"}:
            return [r for r in rows if r.get("finish_delta_days") not in (None, 0)]
        if drilldown_type == "new_remaining":
            return [r for r in rows if not r.get("prior_finish") and not r.get("prior_start")]
        if drilldown_type == "worsened_float":
            return [r for r in rows if (r.get("float_delta_days") or 0) < 0]
        if drilldown_type == "improved_float":
            return [r for r in rows if (r.get("float_delta_days") or 0) > 0]
        if drilldown_type in {"milestones_later", "baseline_milestones_later"}:
            return [r for r in rows if r.get("is_milestone") and (r.get("finish_delta_days") or 0) > 0]
        if drilldown_type == "negative_float":
            return [r for r in rows if _float_value(r.get("current_float")) is not None and _float_value(r.get("current_float")) < 0]
        if drilldown_type == "critical_remaining":
            return [r for r in rows if r.get("computed_cpm_critical")]
        if drilldown_type == "near_critical_remaining":
            return [r for r in rows if r.get("computed_cpm_near_critical")]
        return rows

    def top_wbs(self, rows: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
        counts = Counter((r.get("wbs_code") or "Unassigned") for r in rows)
        return [{"wbs_code": code, "count": count} for code, count in counts.most_common(limit)]

    def _drilldown_row(
        self,
        current: dict[str, Any],
        previous: dict[str, Any],
        cpm: dict[str, Any] | None,
        movement: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        movement = movement or comparison_activity_movement(current, previous or {})
        cpm = cpm or {}
        current_float = _float_days(current)
        prior_float = _float_days(previous) if previous else None
        return {
            "activity_id": current.get("activity_id"),
            "activity_name": current.get("activity_name"),
            "wbs_code": current.get("wbs_code"),
            "wbs_path": current.get("wbs_path"),
            "prior_start": comparison_start_field(previous) if previous else None,
            "current_start": comparison_start_field(current),
            "start_delta_days": movement.get("start_delta_days"),
            "prior_finish": comparison_finish_field(previous) if previous else None,
            "current_finish": comparison_finish_field(current),
            "finish_delta_days": movement.get("finish_delta_days"),
            "prior_float": prior_float,
            "current_float": current_float,
            "float_delta_days": movement.get("float_delta_days"),
            "is_milestone": _is_milestone(current),
            "source_critical": _truthy(current.get("is_critical")) or (
                current_float is not None and current_float <= 0
            ),
            "computed_cpm_critical": _truthy(cpm.get("computed_critical_flag")),
            "computed_cpm_near_critical": _truthy(cpm.get("computed_near_critical_flag")),
        }


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


def _float_value(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
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


def _date_delta_days(old: date | None, new: date | None) -> int | None:
    if not old or not new:
        return None
    return (new - old).days


def _is_milestone(activity: dict[str, Any]) -> bool:
    if _truthy(activity.get("is_milestone")):
        return True
    name = str(activity.get("activity_name") or "").lower()
    duration = str(activity.get("duration_remaining") or activity.get("duration_original") or "").strip()
    return ("milestone" in name or "substantial completion" in name or "final completion" in name) and duration in {"", "0", "0.0"}


def label_from_source(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip().split("/")[-1]
    text = re.sub(r"\.(zip|xer|xml|pmxml|csv)$", "", text, flags=re.I)
    if not text:
        return None
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{1,3})\b", text.upper())
    return match.group(1) if match else text
