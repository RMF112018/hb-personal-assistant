"""Canonical Project Schedule Hub metric and CPM/float read contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from hb_assistant.store.connection import open_connection

from .project_schedule_comparison import ProjectScheduleComparisonService, comparison_finish_sql
from .schedule_cpm_criticality import DEFAULT_CRITICAL_THRESHOLD, DEFAULT_NEAR_CRITICAL_THRESHOLD

MetricBasis = str

BASIS_PERSISTED_DB_FACT: MetricBasis = "persisted_db_fact"
BASIS_DIFF_DERIVED: MetricBasis = "diff_derived"
BASIS_CPM_COMPUTED: MetricBasis = "cpm_computed"
BASIS_SOURCE_EXPORTED: MetricBasis = "source_exported"
BASIS_SERVICE_DERIVED: MetricBasis = "service_derived"

CPM_SELECTED_RUN_ORDER: tuple[str, ...] = ("criticality", "float", "backward_pass", "forward_pass")
CPM_RUN_CHAIN_ORDER: tuple[str, ...] = (
    "graph_diagnostics",
    "forward_pass",
    "backward_pass",
    "float",
    "longest_path",
    "criticality",
)
_SUCCESSFUL_CPM_STATUSES = {
    "",
    "available",
    "complete",
    "completed",
    "computed",
    "persisted",
    "success",
    "successful",
}


@dataclass(frozen=True)
class CanonicalMetricDefinition:
    metric_key: str
    label: str
    basis: MetricBasis
    source: str
    definition: str


CANONICAL_METRIC_DEFINITIONS: dict[str, CanonicalMetricDefinition] = {
    "remaining_work": CanonicalMetricDefinition(
        "remaining_work",
        "Remaining work",
        BASIS_PERSISTED_DB_FACT,
        "procore_ep_schedule_activities.actual_finish",
        "Count current-version activities whose actual finish is null or blank.",
    ),
    "remaining_later": CanonicalMetricDefinition(
        "remaining_later",
        "Remaining later",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version activities whose resolved finish moved later than the comparison version.",
    ),
    "remaining_earlier": CanonicalMetricDefinition(
        "remaining_earlier",
        "Remaining earlier",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version activities whose resolved finish moved earlier than the comparison version.",
    ),
    "finish_changed": CanonicalMetricDefinition(
        "finish_changed",
        "Finish changed",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version activities with any non-zero resolved-finish delta.",
    ),
    "new_remaining": CanonicalMetricDefinition(
        "new_remaining",
        "New remaining",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version activities that do not exist in the comparison version.",
    ),
    "worsened_float": CanonicalMetricDefinition(
        "worsened_float",
        "Worsened float",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version activities whose source/export float decreased versus comparison.",
    ),
    "improved_float": CanonicalMetricDefinition(
        "improved_float",
        "Improved float",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version activities whose source/export float increased versus comparison.",
    ),
    "moved_remaining_milestones": CanonicalMetricDefinition(
        "moved_remaining_milestones",
        "Moved remaining milestones",
        BASIS_DIFF_DERIVED,
        "ProjectScheduleComparisonService.compare_versions",
        "Count remaining current-version milestone activities whose resolved finish moved later.",
    ),
    "source_export_negative_float": CanonicalMetricDefinition(
        "source_export_negative_float",
        "Source/export negative float",
        BASIS_SOURCE_EXPORTED,
        "procore_ep_schedule_activities.total_float/derived_total_float_days/explicit_total_float_days",
        "Count remaining current-version activities with negative source/export float.",
    ),
    "computed_cpm_critical_remaining": CanonicalMetricDefinition(
        "computed_cpm_critical_remaining",
        "Computed CPM critical remaining",
        BASIS_CPM_COMPUTED,
        "selected schedule_cpm_activity_results.computed_critical_flag",
        "Count remaining current-version activities marked critical in the selected application-computed CPM run.",
    ),
    "computed_cpm_near_critical_remaining": CanonicalMetricDefinition(
        "computed_cpm_near_critical_remaining",
        "Computed CPM near-critical remaining",
        BASIS_CPM_COMPUTED,
        "selected schedule_cpm_activity_results.computed_near_critical_flag",
        "Count remaining current-version activities marked near-critical in the selected application-computed CPM run.",
    ),
    "forecast_finish": CanonicalMetricDefinition(
        "forecast_finish",
        "Forecast finish",
        BASIS_SERVICE_DERIVED,
        "procore_ep_schedule_activities resolved finish",
        "Maximum resolved finish date across remaining current-version activities.",
    ),
}


class ProjectScheduleCanonicalMetricService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._comparison = ProjectScheduleComparisonService(db_path=db_path)

    def build_metrics(
        self,
        *,
        project_key: str,
        current_key: str,
        previous_key: str | None,
        comparison_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        activity_summary = self.activity_summary(current_key)
        comparison = self.comparison_summary(current_key=current_key, previous_key=previous_key)
        cpm = self.computed_cpm_summary(current_key)
        forecast = self.forecast_finish(current_key=current_key, previous_key=previous_key)
        values = {
            "remaining_work": activity_summary["remaining_count"],
            "remaining_later": comparison.get("finish_moved_later_count", 0),
            "remaining_earlier": comparison.get("finish_moved_earlier_count", 0),
            "finish_changed": comparison.get("finish_changed_count", 0),
            "new_remaining": comparison.get("new_remaining_activities", 0),
            "worsened_float": comparison.get("worsened_float_count", 0),
            "improved_float": comparison.get("improved_float_count", 0),
            "moved_remaining_milestones": comparison.get("moved_remaining_milestones_count", 0),
            "source_export_negative_float": activity_summary["negative_float_count"],
            "computed_cpm_critical_remaining": cpm["critical_remaining_count"],
            "computed_cpm_near_critical_remaining": cpm["near_critical_remaining_count"],
            "forecast_finish": forecast["current_forecast_finish"],
        }
        return {
            "project_key": project_key,
            "current_schedule_version_key": current_key,
            "previous_schedule_version_key": previous_key,
            "comparison_basis": "prior_update",
            "finish_movement_basis": "resolved_finish_date",
            "comparison_context": comparison_context,
            "activity_summary": activity_summary,
            "comparison_summary": comparison,
            "computed_cpm_summary": cpm,
            "forecast": forecast,
            "values": values,
            "metrics": {
                key: {"value": value, **_definition_payload(CANONICAL_METRIC_DEFINITIONS[key])}
                for key, value in values.items()
            },
        }

    def activity_summary(self, schedule_version_key: str) -> dict[str, int]:
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
        return {
            key: int(data.get(key) or 0)
            for key in (
                "total_count",
                "remaining_count",
                "negative_float_count",
                "zero_float_count",
                "near_critical_count",
                "constrained_remaining_count",
            )
        }

    def comparison_summary(self, *, current_key: str, previous_key: str | None) -> dict[str, int]:
        summary = self._comparison.compare_versions(left_key=current_key, right_key=previous_key).get("summary", {})
        return {
            "common_remaining_activities": int(summary.get("common_remaining_activities") or 0),
            "new_remaining_activities": int(summary.get("new_remaining_activities") or 0),
            "removed_activities": int(summary.get("removed_activities") or 0),
            "finish_moved_later_count": int(summary.get("finish_moved_later_count") or 0),
            "finish_moved_earlier_count": int(summary.get("finish_moved_earlier_count") or 0),
            "finish_changed_count": int(summary.get("finish_changed_count") or 0),
            "start_moved_later_count": int(summary.get("start_moved_later_count") or 0),
            "worsened_float_count": int(summary.get("worsened_float_count") or 0),
            "improved_float_count": int(summary.get("improved_float_count") or 0),
            "moved_remaining_milestones_count": int(summary.get("moved_remaining_milestones_count") or 0),
            "changed_count": int(summary.get("changed_count") or 0),
        }

    def selected_cpm_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            rows = self._cpm_run_rows(conn, schedule_version_key)
        return _select_cpm_run(rows)

    def cpm_flags_by_activity(self, schedule_version_key: str) -> dict[str, dict[str, Any]]:
        selected = self.selected_cpm_run(schedule_version_key)
        if not selected or not selected.get("cpm_run_id"):
            return {}
        with open_connection(self._db_path) as conn:
            return {
                str(row["activity_id"]): dict(row)
                for row in conn.execute(
                    """
                    SELECT activity_id, computed_critical_flag, computed_near_critical_flag,
                           computed_total_float, computed_criticality_class,
                           computed_criticality_status, computed_criticality_basis,
                           critical_float_threshold_days, near_critical_float_threshold_days,
                           cpm_run_id
                    FROM schedule_cpm_activity_results
                    WHERE schedule_version_key=? AND cpm_run_id=?
                    """,
                    (schedule_version_key, selected["cpm_run_id"]),
                ).fetchall()
            }

    def computed_cpm_summary(self, schedule_version_key: str) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            all_runs = self._cpm_run_rows(conn, schedule_version_key)
            selected = _select_cpm_run(all_runs)
            critical_count = 0
            near_count = 0
            criticality_basis = None
            activity_critical_threshold = None
            activity_near_threshold = None
            if selected:
                row = conn.execute(
                    """
                    SELECT
                      SUM(CASE WHEN car.computed_critical_flag=1 THEN 1 ELSE 0 END) AS critical_count,
                      SUM(CASE WHEN car.computed_near_critical_flag=1 THEN 1 ELSE 0 END) AS near_count,
                      MAX(NULLIF(car.computed_criticality_basis, '')) AS criticality_basis,
                      MAX(car.critical_float_threshold_days) AS activity_critical_threshold,
                      MAX(car.near_critical_float_threshold_days) AS activity_near_threshold
                    FROM schedule_cpm_activity_results car
                    JOIN procore_ep_schedule_activities a
                      ON a.schedule_version_key=car.schedule_version_key
                     AND a.activity_id=car.activity_id
                    WHERE car.schedule_version_key=?
                      AND car.cpm_run_id=?
                      AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                    """,
                    (schedule_version_key, selected["cpm_run_id"]),
                ).fetchone()
                critical_count = int((row["critical_count"] if row else 0) or 0)
                near_count = int((row["near_count"] if row else 0) or 0)
                criticality_basis = row["criticality_basis"] if row else None
                activity_critical_threshold = row["activity_critical_threshold"] if row else None
                activity_near_threshold = row["activity_near_threshold"] if row else None
            meta = conn.execute(
                """
                SELECT source_filename_redacted, created_at
                FROM schedule_file_imports
                WHERE schedule_version_key=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (schedule_version_key,),
            ).fetchone()

        runs_by_kind = _latest_runs_by_kind(all_runs)
        sorted_runs = sorted(all_runs, key=_cpm_run_sort_key, reverse=True)
        all_run_payloads = [_run_payload(row) for row in sorted_runs]
        selected_payload = _run_payload(selected)
        excluded_run_payloads = [
            payload for payload in all_run_payloads
            if payload and payload.get("cpm_run_id") != (selected or {}).get("cpm_run_id")
        ]
        critical_threshold = _coalesce_float(
            (selected or {}).get("critical_float_threshold_days"),
            activity_critical_threshold,
            DEFAULT_CRITICAL_THRESHOLD,
        )
        near_threshold = _coalesce_float(
            (selected or {}).get("near_critical_float_threshold_days"),
            activity_near_threshold,
            DEFAULT_NEAR_CRITICAL_THRESHOLD,
        )
        return {
            "available": bool(all_runs),
            "summary": "Computed CPM is available for this update." if all_runs else "Computed CPM is unavailable for this update.",
            "critical_remaining_count": critical_count,
            "near_critical_remaining_count": near_count,
            "drilldown_url": "/schedules/cpm",
            "missing_dependency_reasons": [kind for kind in CPM_RUN_CHAIN_ORDER if kind not in runs_by_kind],
            "evidence_class": "application_computed_cpm",
            "source_export_evidence": "separate",
            "basis": BASIS_CPM_COMPUTED,
            "source_cpm_run_id": (selected or {}).get("cpm_run_id"),
            "selected_cpm_run": selected_payload,
            "all_cpm_runs": all_run_payloads,
            "excluded_cpm_runs": excluded_run_payloads,
            "run_availability": {kind: _run_payload(run) for kind, run in runs_by_kind.items()},
            "selected_run_policy": {
                "calculation_type_order": list(CPM_SELECTED_RUN_ORDER),
                "prefer_successful_status": True,
                "tie_breakers": ["created_at_desc", "cpm_run_id_desc"],
                "excluded_from_counts": "Runs outside the selected calculation type/status/date/run-id choice are reported but not counted.",
            },
            "schedule_version_key": schedule_version_key,
            "data_date": _data_date_from_schedule_version_key(schedule_version_key),
            "import_created_at": dict(meta).get("created_at") if meta else None,
            "source_filename_redacted": dict(meta).get("source_filename_redacted") if meta else None,
            "computed_at": (selected or {}).get("created_at"),
            "run_status": (selected or {}).get("cpm_recalculation_status"),
            "calculation_type": (selected or {}).get("calculation_type"),
            "criticality_basis": criticality_basis or "application_computed_cpm",
            "critical_float_threshold_days": critical_threshold,
            "near_critical_float_threshold_days": near_threshold,
            "near_critical_threshold_source": (
                "selected_cpm_run"
                if _coalesce_float((selected or {}).get("near_critical_float_threshold_days")) is not None
                else "activity_results"
                if _coalesce_float(activity_near_threshold) is not None
                else "default"
            ),
            "default_near_critical_float_threshold_days": DEFAULT_NEAR_CRITICAL_THRESHOLD,
            "source_export_float_basis": "procore_ep_schedule_activities.total_float -> derived_total_float_days -> explicit_total_float_days",
            "app_computed_float_basis": "selected schedule_cpm_activity_results.computed_total_float for source_cpm_run_id",
        }

    def forecast_finish(self, *, current_key: str, previous_key: str | None) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            current_finish = _parse_date(
                conn.execute(
                    f"""
                    SELECT MAX({comparison_finish_sql("a")})
                    FROM procore_ep_schedule_activities a
                    WHERE a.schedule_version_key=?
                      AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                    """,
                    (current_key,),
                ).fetchone()[0]
            )
            previous_finish = None
            if previous_key:
                previous_finish = _parse_date(
                    conn.execute(
                        f"""
                        SELECT MAX({comparison_finish_sql("p")})
                        FROM procore_ep_schedule_activities c
                        JOIN procore_ep_schedule_activities p
                          ON p.activity_id=c.activity_id
                         AND p.schedule_version_key=?
                        WHERE c.schedule_version_key=?
                          AND (c.actual_finish IS NULL OR TRIM(c.actual_finish)='')
                        """,
                        (previous_key, current_key),
                    ).fetchone()[0]
                )
        return {
            "current_forecast_finish": _date_str(current_finish),
            "previous_forecast_finish": _date_str(previous_finish),
            "movement_days": _date_delta_days(previous_finish, current_finish),
        }

    @staticmethod
    def _cpm_run_rows(conn: Any, schedule_version_key: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT cpm_run_id, project_key, schedule_version_key, import_id,
                       calculation_type, cpm_recalculation_status,
                       analysis_scope, source_run_id, created_at, node_count,
                       edge_count, diagnostic_count, computed_activity_count,
                       blocked_activity_count, is_acyclic,
                       critical_float_threshold_days, near_critical_float_threshold_days,
                       computed_critical_activity_count, computed_near_critical_activity_count,
                       computed_noncritical_activity_count, unclassified_activity_count,
                       longest_path_member_count
                FROM schedule_cpm_runs
                WHERE schedule_version_key=?
                """,
                (schedule_version_key,),
            ).fetchall()
        ]


def _definition_payload(definition: CanonicalMetricDefinition) -> dict[str, str]:
    return {
        "label": definition.label,
        "basis": definition.basis,
        "source": definition.source,
        "definition": definition.definition,
    }


def _select_cpm_run(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for calculation_type in CPM_SELECTED_RUN_ORDER:
        candidates = [row for row in rows if str(row.get("calculation_type") or "") == calculation_type]
        if not candidates:
            continue
        successful = [row for row in candidates if _successful_cpm_status(row.get("cpm_recalculation_status"))]
        return sorted(successful or candidates, key=_cpm_run_sort_key, reverse=True)[0]
    return None


def _latest_runs_by_kind(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for calculation_type in CPM_RUN_CHAIN_ORDER:
        candidates = [row for row in rows if str(row.get("calculation_type") or "") == calculation_type]
        if candidates:
            out[calculation_type] = sorted(candidates, key=_cpm_run_sort_key, reverse=True)[0]
    return out


def _cpm_run_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_at") or ""), str(row.get("cpm_run_id") or ""))


def _successful_cpm_status(value: Any) -> bool:
    return str(value or "").strip().lower() in _SUCCESSFUL_CPM_STATUSES


def _run_payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "cpm_run_id": row.get("cpm_run_id"),
        "calculation_type": row.get("calculation_type"),
        "status": row.get("cpm_recalculation_status"),
        "analysis_scope": row.get("analysis_scope"),
        "source_run_id": row.get("source_run_id"),
        "created_at": row.get("created_at"),
        "schedule_version_key": row.get("schedule_version_key"),
        "import_id": row.get("import_id"),
        "successful_status": _successful_cpm_status(row.get("cpm_recalculation_status")),
        "critical_float_threshold_days": _coalesce_float(row.get("critical_float_threshold_days")),
        "near_critical_float_threshold_days": _coalesce_float(row.get("near_critical_float_threshold_days")),
        "computed_activity_count": _opt_int(row.get("computed_activity_count")),
        "computed_critical_activity_count": _opt_int(row.get("computed_critical_activity_count")),
        "computed_near_critical_activity_count": _opt_int(row.get("computed_near_critical_activity_count")),
    }


def _coalesce_float(*values: Any) -> float | None:
    for value in values:
        if value is None or str(value).strip() == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _opt_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _data_date_from_schedule_version_key(schedule_version_key: str) -> str | None:
    token = str(schedule_version_key).split("|")[-1]
    return _date_str(_parse_date(token))


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


def _date_str(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date_delta_days(old: date | None, new: date | None) -> int | None:
    if not old or not new:
        return None
    return (new - old).days
