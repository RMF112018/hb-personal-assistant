"""Read-only trend aggregation for Project Schedule Hub visualization metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from hb_assistant.store.connection import open_connection

from .project_schedule_canonical_metrics import ProjectScheduleCanonicalMetricService
from .project_schedule_comparison import ProjectScheduleComparisonService, comparison_finish_sql
from .project_schedule_summary_service import ProjectScheduleSummaryService, _date_str, _parse_date
from .project_schedule_selected_baseline_service import ProjectScheduleSelectedBaselineService
from .project_schedule_udf_normalization_service import (
    UDF_DEPENDENT_METRICS,
    ProjectScheduleUdfNormalizationService,
)
from .project_schedule_visualization_metric_contract import (
    NON_CAUSATION_CAVEAT,
    ProjectScheduleVisualizationMetricContractService,
)

SUPPORTED_TREND_METRICS: frozenset[str] = frozenset(
    {
        "monthly_activity_start_finish_distribution",
        "planned_vs_actual_percent_complete",
        "schedule_performance_ratio",
        "schedule_delay_over_time",
        "schedule_changes_over_time",
        "project_schedule_health_index",
        "schedule_feasibility_score",
        "required_recovery_days",
        "critical_path_length_index",
        "total_float_consumption_index",
    }
)
READINESS_AWARE_TREND_METRICS: frozenset[str] = frozenset(
    {
        "schedule_compression_ratio",
        *UDF_DEPENDENT_METRICS,
    }
)

_VERSION_CAP = 12


class ProjectScheduleTrendAggregationService:
    """Build chart-ready schedule trend payloads without mutating state."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._contracts = ProjectScheduleVisualizationMetricContractService(db_path=db_path)
        self._summary = ProjectScheduleSummaryService(db_path=db_path)
        self._comparison = ProjectScheduleComparisonService(db_path=db_path)
        self._canonical = ProjectScheduleCanonicalMetricService(db_path=db_path)
        self._udf = ProjectScheduleUdfNormalizationService(db_path=db_path)

    def build_trend(
        self,
        project_key: str,
        metric_key: str,
        *,
        as_of: date | None = None,
        weighting_basis: str | None = None,
    ) -> dict[str, Any]:
        contract = self._contract(metric_key)
        selected_weighting = weighting_basis or str(contract["default_weighting_basis"])
        self._validate_metric(contract, selected_weighting)

        as_of_date = as_of or datetime.now().date()
        versions = self._eligible_versions(project_key, as_of_date)
        envelope = self._envelope(
            project_key=project_key,
            contract=contract,
            as_of_date=as_of_date,
            weighting_basis=selected_weighting,
            versions=versions,
        )
        if not versions:
            return {
                **envelope,
                "available": False,
                "reason": "no_eligible_schedule_versions",
                "data_quality_notes": ["No hub-eligible schedule versions were available on or before as_of."],
            }

        builder = {
            "monthly_activity_start_finish_distribution": self._monthly_distribution,
            "planned_vs_actual_percent_complete": self._planned_vs_actual,
            "schedule_performance_ratio": self._schedule_performance_ratio,
            "schedule_delay_over_time": self._schedule_delay,
            "schedule_changes_over_time": self._schedule_changes,
            "project_schedule_health_index": self._health_index,
            "schedule_feasibility_score": self._feasibility_score,
            "required_recovery_days": self._required_recovery_days,
            "critical_path_length_index": self._critical_path_length_index,
            "total_float_consumption_index": self._total_float_consumption_index,
            "schedule_compression_ratio": self._schedule_compression_ratio,
            "delay_analysis": self._udf_dependent_metric,
            "window_start_accuracy": self._udf_dependent_metric,
            "window_finish_accuracy": self._udf_dependent_metric,
            "should_have_finished_status": self._udf_dependent_metric,
            "critical_issues_category_model": self._udf_dependent_metric,
        }[metric_key]
        self._current_metric_key = metric_key
        payload = builder(project_key, versions, selected_weighting)
        return {**envelope, **payload}

    def build_trends(
        self,
        project_key: str,
        *,
        metric_keys: list[str] | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        keys = metric_keys or sorted(SUPPORTED_TREND_METRICS)
        trends: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for key in keys:
            try:
                trends.append(self.build_trend(project_key, key, as_of=as_of))
            except ValueError as exc:
                errors.append({"metric_key": key, "detail": str(exc)})
        return {
            "available": bool(trends),
            "project_key": project_key,
            "as_of_date": (as_of or datetime.now().date()).isoformat(),
            "metrics": trends,
            "errors": errors,
        }

    def _contract(self, metric_key: str) -> dict[str, Any]:
        try:
            return self._contracts.contract_by_key(metric_key)
        except KeyError as exc:
            raise ValueError("unsupported_metric_key") from exc

    def _validate_metric(self, contract: dict[str, Any], weighting_basis: str) -> None:
        metric_key = str(contract["metric_key"])
        if metric_key not in SUPPORTED_TREND_METRICS and metric_key not in READINESS_AWARE_TREND_METRICS:
            raise ValueError("metric_not_trend_ready")
        if weighting_basis in {"cost_weighted", "cost_weighted_deferred"}:
            raise ValueError("cost_weighted_unavailable")
        if weighting_basis not in set(contract["weighting_basis"]):
            raise ValueError("unsupported_weighting_basis")

    def _eligible_versions(self, project_key: str, as_of_date: date) -> list[dict[str, Any]]:
        versions = self._summary._hub_project_versions(project_key)  # Existing hub eligibility source.
        current_choice = self._summary._resolve_current(project_key, versions, as_of_date=as_of_date)
        if not current_choice:
            return []
        identity_key = (
            current_choice.identity_match.get("schedule_identity_key")
            if current_choice.identity_match
            else None
        )
        eligible: list[dict[str, Any]] = []
        for version in versions:
            version_date = self._summary._data_date(version)
            if version_date and version_date > as_of_date:
                continue
            match = self._summary._identity.get_match_for_version(str(version["schedule_version_key"]))
            if identity_key and (match or {}).get("schedule_identity_key") != identity_key:
                continue
            eligible.append(version)
        eligible.sort(
            key=lambda v: (
                self._summary._data_date(v) or date.min,
                str(v.get("created_at") or ""),
                str(v.get("schedule_version_key") or ""),
            )
        )
        return eligible[-_VERSION_CAP:]

    def _envelope(
        self,
        *,
        project_key: str,
        contract: dict[str, Any],
        as_of_date: date,
        weighting_basis: str,
        versions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "available": True,
            "project_key": project_key,
            "metric_key": contract["metric_key"],
            "display_name": contract["display_name"],
            "readiness_status": contract["readiness_status"],
            "as_of_date": as_of_date.isoformat(),
            "basis_labels": list(contract["basis_labels"]),
            "comparison_basis": list(contract["comparison_basis"]),
            "weighting_basis": weighting_basis,
            "caveats": list(contract["caveats"]),
            "formula_summary": contract["formula_summary"],
            "points": [],
            "summary": {},
            "unavailable_variants": self._unavailable_variants(contract),
            "source_version_keys": [str(v["schedule_version_key"]) for v in versions],
            "data_quality_notes": [],
        }

    @staticmethod
    def _unavailable_variants(contract: dict[str, Any]) -> list[dict[str, str]]:
        variants: list[dict[str, str]] = []
        if "cost_weighted_deferred" in contract.get("weighting_basis", []):
            variants.append({"variant": "cost_weighted", "reason": "cost_weighted_unavailable"})
        return variants

    def _monthly_distribution(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        notes = ["Baseline monthly buckets are unavailable unless an active selected baseline exists."]
        date_fields = {
            "actual_start": "actual_start",
            "actual_finish": "actual_finish",
            "planned_start": "planned_start",
            "planned_finish": "planned_finish",
            "current_start": "start_date",
            "current_finish": "finish_date",
            "source_early_start": "early_start",
            "source_early_finish": "early_finish",
            "source_late_start": "late_start",
            "source_late_finish": "late_finish",
        }
        for version in versions:
            version_key = str(version["schedule_version_key"])
            buckets: dict[tuple[str, str], int] = defaultdict(int)
            with open_connection(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT actual_start, actual_finish, planned_start, planned_finish,
                           start_date, finish_date, early_start, early_finish,
                           late_start, late_finish
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                    """,
                    (version_key,),
                ).fetchall()
                cpm_run = self._canonical.selected_cpm_run(version_key)
                cpm_rows = []
                if cpm_run:
                    cpm_rows = conn.execute(
                        """
                        SELECT computed_early_start, computed_early_finish,
                               computed_late_start, computed_late_finish
                        FROM schedule_cpm_activity_results
                        WHERE schedule_version_key=? AND cpm_run_id=?
                        """,
                        (version_key, cpm_run["cpm_run_id"]),
                    ).fetchall()
            for row in rows:
                data = dict(row)
                for family, field in date_fields.items():
                    month = _month_bucket(data.get(field))
                    if month:
                        buckets[(family, month)] += 1
            for row in cpm_rows:
                data = dict(row)
                for family, field in {
                    "computed_early_start": "computed_early_start",
                    "computed_early_finish": "computed_early_finish",
                    "computed_late_start": "computed_late_start",
                    "computed_late_finish": "computed_late_finish",
                }.items():
                    month = _month_bucket(data.get(field))
                    if month:
                        buckets[(family, month)] += 1
            for (family, month), count in sorted(buckets.items()):
                points.append(
                    {
                        "schedule_version_key": version_key,
                        "data_date": _date_str(self._summary._data_date(version)),
                        "month": month,
                        "date_family": family,
                        "activity_count": count,
                    }
                )
        return {"points": points, "summary": {"point_count": len(points)}, "data_quality_notes": notes}

    def _planned_vs_actual(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key
        points = [self._progress_point(version, weighting_basis) for version in versions]
        return {"points": points, "summary": {"default_weighting_basis": "duration_weighted"}}

    def _schedule_performance_ratio(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key
        points = []
        for version in versions:
            progress = self._progress_point(version, weighting_basis)
            planned = progress.get("planned_percent_complete") or 0
            actual = progress.get("actual_percent_complete") or 0
            ratio = None if planned <= 0 else actual / planned
            points.append(
                {
                    **progress,
                    "schedule_performance_ratio": ratio,
                    "ev_duration": progress.get("actual_weighted_value"),
                    "pv_duration": progress.get("planned_weighted_value"),
                }
            )
        return {
            "points": points,
            "summary": {
                "default_weighting_basis": "duration_weighted",
                "earned_value_spi": False,
            },
            "data_quality_notes": ["This is a duration-weighted schedule performance ratio, not certified earned-value SPI."],
        }

    def _progress_point(self, version: dict[str, Any], weighting_basis: str) -> dict[str, Any]:
        version_key = str(version["schedule_version_key"])
        data_date = self._summary._data_date(version)
        with open_connection(self._db_path) as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT planned_start, planned_finish, start_date, finish_date,
                           actual_start, actual_finish, duration_original,
                           percent_complete, duration_percent_complete, physical_percent_complete
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                    """,
                    (version_key,),
                ).fetchall()
            ]
        if weighting_basis == "activity_count":
            total = len(rows)
            actual = sum(1 for row in rows if _nonempty(row.get("actual_finish")))
            planned = sum(
                1
                for row in rows
                if data_date and (finish := _parse_date(row.get("planned_finish") or row.get("finish_date"))) and finish <= data_date
            )
            return {
                "schedule_version_key": version_key,
                "data_date": _date_str(data_date),
                "actual_percent_complete": _safe_ratio(actual, total),
                "planned_percent_complete": _safe_ratio(planned, total),
                "actual_weighted_value": actual,
                "planned_weighted_value": planned,
                "denominator": total,
                "weighting_basis": weighting_basis,
            }
        actual_weight = 0.0
        planned_weight = 0.0
        total_weight = 0.0
        for row in rows:
            duration = _float_value(row.get("duration_original")) or 1.0
            total_weight += duration
            actual_weight += _percent_complete(row) * duration
            planned_weight += _planned_fraction(row, data_date) * duration
        return {
            "schedule_version_key": version_key,
            "data_date": _date_str(data_date),
            "actual_percent_complete": _safe_ratio(actual_weight, total_weight),
            "planned_percent_complete": _safe_ratio(planned_weight, total_weight),
            "actual_weighted_value": actual_weight,
            "planned_weighted_value": planned_weight,
            "denominator": total_weight,
            "weighting_basis": weighting_basis,
        }

    def _schedule_delay(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        previous_version: dict[str, Any] | None = None
        for version in versions:
            current_key = str(version["schedule_version_key"])
            current_finish = self._forecast_finish(current_key)
            previous_key = str(previous_version["schedule_version_key"]) if previous_version else None
            prior_finish = self._forecast_finish(previous_key) if previous_key else None
            movement = _date_delta(prior_finish, current_finish)
            points.append(
                {
                    "period": _date_str(self._summary._data_date(version)),
                    "prior_version_key": previous_key,
                    "current_version_key": current_key,
                    "prior_forecast_finish": _date_str(prior_finish),
                    "current_forecast_finish": _date_str(current_finish),
                    "baseline_finish": None,
                    "delay_days": movement if movement is not None and movement > 0 else 0,
                    "gain_days": abs(movement) if movement is not None and movement < 0 else 0,
                    "planned_variance_days": None,
                    "net_movement_days": movement,
                }
            )
            previous_version = version
        return {
            "points": points,
            "summary": {"baseline_variance_separate": True},
            "data_quality_notes": ["Baseline variance is kept separate from prior-update movement."],
        }

    def _schedule_changes(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        for version in versions:
            current_key = str(version["schedule_version_key"])
            with open_connection(self._db_path) as conn:
                diff = conn.execute(
                    """
                    SELECT * FROM schedule_version_diffs
                    WHERE to_schedule_version_key=?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (current_key,),
                ).fetchone()
                critical_changes = near_critical_changes = duration_changes = lag_changes = 0
                if diff:
                    diff_id = int(diff["id"])
                    critical_changes = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM schedule_version_diff_detail_facts WHERE diff_id=? AND is_critical_path_related=1",
                            (diff_id,),
                        ).fetchone()[0]
                        or 0
                    )
                    duration_changes = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM schedule_version_diff_detail_facts WHERE diff_id=? AND (field_name LIKE '%duration%' OR change_type LIKE '%duration%')",
                            (diff_id,),
                        ).fetchone()[0]
                        or 0
                    )
                    lag_changes = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM schedule_version_diff_detail_facts WHERE diff_id=? AND (field_name LIKE '%lag%' OR change_type LIKE '%lag%')",
                            (diff_id,),
                        ).fetchone()[0]
                        or 0
                    )
                    near_critical_changes = 0
            row = dict(diff) if diff else {}
            points.append(
                {
                    "period": _date_str(self._summary._data_date(version)),
                    "schedule_version_key": current_key,
                    "categories": {
                        "total_activities": int(version.get("activity_count") or 0),
                        "activity_changes": int(row.get("activity_changed_count") or 0),
                        "logic_changes": int(row.get("relationship_added_count") or 0)
                        + int(row.get("relationship_removed_count") or 0),
                        "duration_changes": duration_changes,
                        "critical_changes": critical_changes,
                        "near_critical_changes": near_critical_changes,
                        "lag_changes": lag_changes,
                        "calendar_changes": int(row.get("calendar_churn_count") or 0),
                        "deleted_activity_changes": int(row.get("activity_removed_count") or 0),
                        "added_activity_changes": int(row.get("activity_added_count") or 0),
                    },
                }
            )
        return {"points": points, "summary": {"category_count": 10}}

    def _health_index(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        with open_connection(self._db_path) as conn:
            for version in versions:
                version_key = str(version["schedule_version_key"])
                row = conn.execute(
                    """
                    SELECT sc.quality_score, sc.quality_grade, sc.finding_counts_json,
                           r.completed_at, r.status
                    FROM schedule_quality_scorecards sc
                    LEFT JOIN schedule_quality_evaluation_runs r
                      ON r.evaluation_run_id=sc.evaluation_run_id
                    WHERE sc.schedule_version_key=?
                      AND (r.status IS NULL OR r.status='completed')
                    ORDER BY COALESCE(r.completed_at, sc.created_at) DESC
                    LIMIT 1
                    """,
                    (version_key,),
                ).fetchone()
                if row:
                    points.append(
                        {
                            "schedule_version_key": version_key,
                            "data_date": _date_str(self._summary._data_date(version)),
                            "health_index": _float_value(row["quality_score"]),
                            "quality_grade": row["quality_grade"],
                            "basis": "quality_scorecard",
                        }
                    )
        notes = [] if points else ["No completed schedule quality scorecards were available for the selected trend window."]
        return {"available": True, "points": points, "summary": {"quality_point_count": len(points)}, "data_quality_notes": notes}

    def _feasibility_score(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        return {
            "available": False,
            "reason": "dependency_inputs_unavailable",
            "points": [],
            "summary": {"dependency_inputs": ["schedule_compression_ratio", "project_schedule_health_index", "schedule_performance_ratio"]},
            "data_quality_notes": ["Feasibility score is not fabricated without dependency metric inputs."],
        }

    def _required_recovery_days(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        previous_version: dict[str, Any] | None = None
        for version in versions:
            version_key = str(version["schedule_version_key"])
            path = self._longest_path(version_key)
            if not path:
                previous_version = version
                continue
            current_finish = self._forecast_finish(version_key)
            previous_finish = self._forecast_finish(str(previous_version["schedule_version_key"])) if previous_version else None
            forecast_movement = _date_delta(previous_finish, current_finish) or 0
            critical_path_delay = _float_value(path.get("path_finish_offset_days")) or _float_value(path.get("path_duration"))
            required = None if critical_path_delay is None else critical_path_delay - forecast_movement
            points.append(
                {
                    "period": _date_str(self._summary._data_date(version)),
                    "schedule_version_key": version_key,
                    "critical_path_delay_days": critical_path_delay,
                    "forecast_finish_movement_days": forecast_movement,
                    "required_recovery_days": required,
                    "cpm_run_id": path.get("cpm_run_id"),
                }
            )
            previous_version = version
        return {
            "available": bool(points),
            "reason": None if points else "cpm_path_facts_unavailable",
            "points": points,
            "summary": {"non_causation_caveat": NON_CAUSATION_CAVEAT},
            "data_quality_notes": [] if points else ["Selected CPM path facts were unavailable."],
        }

    def _critical_path_length_index(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        for version in versions:
            version_key = str(version["schedule_version_key"])
            path = self._longest_path(version_key)
            if path:
                points.append(
                    {
                        "data_date": _date_str(self._summary._data_date(version)),
                        "schedule_version_key": version_key,
                        "criticality_basis": "computed_cpm_path",
                        "critical_path_length_index": _float_value(path.get("path_duration")),
                        "path_activity_count": int(path.get("activity_count") or 0),
                        "cpm_run_id": path.get("cpm_run_id"),
                    }
                )
        return {
            "available": bool(points),
            "reason": None if points else "cpm_path_facts_unavailable",
            "points": points,
            "summary": {"criticality_basis": "computed_cpm_preferred"},
            "data_quality_notes": [] if points else ["Computed CPM path facts were unavailable; no source/export fallback was substituted."],
        }

    def _total_float_consumption_index(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del project_key, weighting_basis
        points: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None
        for version in versions:
            version_key = str(version["schedule_version_key"])
            source_float = self._source_float_sum(version_key)
            computed_float = self._computed_float_sum(version_key)
            elapsed = _date_delta(self._summary._data_date(previous) if previous else None, self._summary._data_date(version))
            points.append(
                {
                    "data_date": _date_str(self._summary._data_date(version)),
                    "schedule_version_key": version_key,
                    "series": [
                        {"float_basis": "source_export", "total_float_days": source_float, "elapsed_days": elapsed},
                        {"float_basis": "computed_cpm", "total_float_days": computed_float, "elapsed_days": elapsed},
                    ],
                }
            )
            previous = version
        return {
            "points": points,
            "summary": {"float_bases_separate": True},
            "data_quality_notes": ["Source/export and computed CPM float are separate series."],
        }

    def _schedule_compression_ratio(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del weighting_basis
        if not versions:
            return {
                "available": False,
                "reason": "no_eligible_schedule_versions",
                "points": [],
                "readiness": {"ready": False, "blockers": ["no_eligible_schedule_versions"]},
                "recompute_required": False,
                "data_quality_notes": ["No hub-eligible schedule version was available for selected-baseline compression."],
            }
        current = versions[-1]
        return ProjectScheduleSelectedBaselineService(db_path=self._db_path).compression_payload(
            project_key=project_key,
            current_schedule_version_key=str(current["schedule_version_key"]),
            as_of_date=self._summary._data_date(current) or datetime.now().date(),
        )

    def _udf_dependent_metric(
        self, project_key: str, versions: list[dict[str, Any]], weighting_basis: str
    ) -> dict[str, Any]:
        del weighting_basis
        if not versions:
            return {
                "available": False,
                "reason": "no_eligible_schedule_versions",
                "points": [],
                "readiness": {"ready": False, "blockers": ["no_eligible_schedule_versions"]},
                "data_quality_notes": ["No hub-eligible schedule version was available for UDF-dependent metrics."],
            }
        current = versions[-1]
        version_key = str(current["schedule_version_key"])
        as_of_date = self._summary._data_date(current) or datetime.now().date()
        metric_key = getattr(self, "_current_metric_key", "")
        return self._udf.build_metric_payload(
            metric_key=metric_key,
            project_key=project_key,
            version_key=version_key,
            as_of_date=as_of_date,
            data_date=as_of_date,
        )

    def _forecast_finish(self, version_key: str | None) -> date | None:
        if not version_key:
            return None
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                f"""
                SELECT MAX({comparison_finish_sql('a')}) AS forecast_finish
                FROM procore_ep_schedule_activities a
                WHERE a.schedule_version_key=?
                  AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                """,
                (version_key,),
            ).fetchone()
        return _parse_date(row["forecast_finish"]) if row else None

    def _longest_path(self, version_key: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM schedule_cpm_paths
                WHERE schedule_version_key=?
                  AND path_status IN ('complete', 'completed', 'available', 'success', 'successful')
                ORDER BY created_at DESC, path_rank ASC, path_id DESC
                LIMIT 1
                """,
                (version_key,),
            ).fetchone()
        return dict(row) if row else None

    def _source_float_sum(self, version_key: str) -> float | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT SUM(CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '0') AS REAL)) AS total_float
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                """,
                (version_key,),
            ).fetchone()
        return _float_value(row["total_float"]) if row else None

    def _computed_float_sum(self, version_key: str) -> float | None:
        selected = self._canonical.selected_cpm_run(version_key)
        if not selected:
            return None
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT SUM(car.computed_total_float) AS total_float
                FROM schedule_cpm_activity_results car
                JOIN procore_ep_schedule_activities a
                  ON a.schedule_version_key=car.schedule_version_key
                 AND a.activity_id=car.activity_id
                WHERE car.schedule_version_key=?
                  AND car.cpm_run_id=?
                  AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                """,
                (version_key, selected["cpm_run_id"]),
            ).fetchone()
        return _float_value(row["total_float"]) if row else None


def _month_bucket(value: Any) -> str | None:
    parsed = _parse_date(value)
    if not parsed:
        return None
    return f"{parsed.year:04d}-{parsed.month:02d}"


def _float_value(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _percent_complete(row: dict[str, Any]) -> float:
    if _nonempty(row.get("actual_finish")):
        return 1.0
    for field in ("duration_percent_complete", "percent_complete", "physical_percent_complete"):
        value = _float_value(row.get(field))
        if value is not None:
            return max(0.0, min(1.0, value / 100 if value > 1 else value))
    return 0.0


def _planned_fraction(row: dict[str, Any], data_date: date | None) -> float:
    if not data_date:
        return 0.0
    start = _parse_date(row.get("planned_start") or row.get("start_date"))
    finish = _parse_date(row.get("planned_finish") or row.get("finish_date"))
    if not finish:
        return 0.0
    if finish <= data_date:
        return 1.0
    if not start or start >= data_date:
        return 0.0
    total = max(1, (finish - start).days)
    elapsed = max(0, (data_date - start).days)
    return max(0.0, min(1.0, elapsed / total))


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def _date_delta(left: date | None, right: date | None) -> int | None:
    if not left or not right:
        return None
    return (right - left).days
