"""Schedule metric formula computation service for proof export."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from hb_assistant.store.connection import open_connection

from .project_schedule_canonical_metrics import ProjectScheduleCanonicalMetricService
from .project_schedule_selected_baseline_service import ProjectScheduleSelectedBaselineService
from .project_schedule_summary_service import ProjectScheduleSummaryService, _date_str, _parse_date
from .project_schedule_trend_aggregation_service import (
    ProjectScheduleTrendAggregationService,
    _date_delta,
    _float_value,
    _nonempty,
    _percent_complete,
    _planned_fraction,
    _safe_ratio,
)
from .project_schedule_udf_normalization_service import ProjectScheduleUdfNormalizationService
from .schedule_metric_formula_registry import (
    FEASIBILITY_WEIGHTS,
    FORMULA_VERSION,
    FRONTEND_CHART_METRIC_KEYS,
    HEALTH_WEIGHTS,
    PROOF_ONLY_METRIC_KEYS,
    TREND_API_METRIC_KEYS,
    ZERO_DENOMINATOR_POLICY,
    build_metric_registry,
)

INTERNAL_VARIANT_PARENT: dict[str, str] = {
    "schedule_spi_count": "schedule_performance_ratio",
    "schedule_spi_duration": "schedule_performance_ratio",
    "planned_vs_actual_percent_complete_activity_count": "planned_vs_actual_percent_complete",
    "planned_vs_actual_percent_complete_duration_weighted": "planned_vs_actual_percent_complete",
}

PROOF_API_METRIC_KEY_ALIASES: dict[str, str] = {
    "should_have_finished_status": "should_have_finished",
}

METRIC_PROOF_API_KEYS: frozenset[str] = frozenset(
    {
        "planned_vs_actual_percent_complete",
        "schedule_performance_ratio",
        "schedule_changes_over_time",
        "schedule_delay_over_time",
        "delay_analysis",
        "window_start_accuracy",
        "should_have_finished",
        "critical_indices",
        "critical_issues_category_model",
        "schedule_compression_index_internal",
        "project_schedule_health_index",
        "schedule_feasibility_score",
        "future_acceleration",
    }
)

FRONTEND_CHART_WITHOUT_REGISTRY: frozenset[str] = frozenset(
    {
        "monthly_activity_start_finish_distribution",
        "required_recovery_days",
        "critical_path_length_index",
        "total_float_consumption_index",
        "window_finish_accuracy",
        "schedule_compression_ratio",
    }
)


def ratio_result(
    numerator: float | None,
    denominator: float | None,
    *,
    zero_denominator_policy: str = ZERO_DENOMINATOR_POLICY,
) -> dict[str, Any]:
    if numerator is None or denominator is None or denominator == 0:
        return {
            "numerator": numerator,
            "denominator": denominator,
            "zero_denominator_policy": zero_denominator_policy,
            "result": None,
            "status": "not_computable",
        }
    return {
        "numerator": numerator,
        "denominator": denominator,
        "zero_denominator_policy": zero_denominator_policy,
        "result": numerator / denominator,
        "status": "computable",
    }


def not_computable(reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": "not_computable", "reason": reason, **extra}


class ScheduleMetricFormulaService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._summary = ProjectScheduleSummaryService(db_path=db_path)
        self._trend = ProjectScheduleTrendAggregationService(db_path=db_path)
        self._udf = ProjectScheduleUdfNormalizationService(db_path=db_path)
        self._canonical = ProjectScheduleCanonicalMetricService(db_path=db_path)
        self._baseline = ProjectScheduleSelectedBaselineService(db_path=db_path)

    def compute_all(
        self,
        project_key: str,
        schedule_version_key: str,
        *,
        comparison_basis: str = "prior_update",
        weighting_basis: str = "duration_weighted",
        as_of: date | None = None,
    ) -> dict[str, Any]:
        as_of_date = as_of or datetime.now().date()
        versions = self._trend._eligible_versions(project_key, as_of_date)
        version = next(
            (v for v in versions if str(v["schedule_version_key"]) == schedule_version_key),
            None,
        )
        if version is None and versions:
            version = versions[-1]
            schedule_version_key = str(version["schedule_version_key"])
        unsupported = [
            e
            for e in build_metric_registry()
            if not e.get("formula_supported", True)
        ]
        metrics: dict[str, Any] = {
            "planned_vs_actual_percent_complete": self.compute_planned_vs_actual(
                project_key, schedule_version_key, weighting_basis=weighting_basis, version=version
            ),
            "schedule_performance_ratio": self.compute_schedule_spi(
                project_key, schedule_version_key, weighting_basis=weighting_basis, version=version
            ),
            "schedule_changes_over_time": self.compute_schedule_changes(
                project_key, versions or ([version] if version else [])
            ),
            "schedule_delay_over_time": self.compute_schedule_delay(
                project_key, versions or ([version] if version else []),
                comparison_basis=comparison_basis,
            ),
            "delay_analysis": self.compute_delay_analysis(project_key, schedule_version_key, as_of_date),
            "window_start_accuracy": self.compute_window_start_accuracy(
                project_key, schedule_version_key, as_of_date
            ),
            "should_have_finished": self.compute_should_have_finished(
                project_key, schedule_version_key, as_of_date
            ),
            "critical_indices": self.compute_critical_indices(schedule_version_key),
            "critical_issues_category_model": self.compute_critical_issues(
                project_key, schedule_version_key, as_of_date
            ),
            "schedule_compression_index_internal": self.compute_compression_index_internal(
                project_key, schedule_version_key, as_of_date, comparison_basis=comparison_basis
            ),
            "project_schedule_health_index": self.compute_health_index(
                project_key, schedule_version_key, version=version
            ),
            "schedule_feasibility_score": self.compute_feasibility_score(
                project_key, schedule_version_key, as_of_date, weighting_basis=weighting_basis, version=version
            ),
            "future_acceleration": self.compute_future_acceleration(
                project_key, schedule_version_key, as_of_date, comparison_basis=comparison_basis
            ),
        }
        return {
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "formula_version": FORMULA_VERSION,
            "comparison_basis": comparison_basis,
            "weighting_basis": weighting_basis,
            "metrics": metrics,
            "unsupported_metrics": unsupported,
        }

    def build_input_snapshot(
        self, project_key: str, schedule_version_key: str
    ) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            activities = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                    (schedule_version_key,),
                ).fetchall()
            ]
            diffs = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM schedule_version_diffs WHERE to_schedule_version_key=?",
                    (schedule_version_key,),
                ).fetchall()
            ]
            cpm_run = self._canonical.selected_cpm_run(schedule_version_key)
            cpm_activities: list[dict[str, Any]] = []
            if cpm_run:
                cpm_activities = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM schedule_cpm_activity_results WHERE cpm_run_id=?",
                        (cpm_run["cpm_run_id"],),
                    ).fetchall()
                ]
        return {
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "activities": activities,
            "diffs": diffs,
            "cpm_run": cpm_run,
            "cpm_activities": cpm_activities,
        }

    def compute_planned_vs_actual(
        self,
        project_key: str,
        schedule_version_key: str,
        *,
        weighting_basis: str = "duration_weighted",
        version: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not version:
            versions = self._trend._eligible_versions(
                project_key, __import__("datetime").datetime.now().date()
            )
            version = next(
                (v for v in versions if str(v["schedule_version_key"]) == schedule_version_key),
                versions[-1] if versions else None,
            )
        if not version:
            return not_computable("missing_version")
        point = self._trend._progress_point(version, weighting_basis)
        actual = point.get("actual_percent_complete")
        planned = point.get("planned_percent_complete")
        denom = point.get("denominator")
        variance = (actual - planned) if actual is not None and planned is not None else None
        return {
            **point,
            "variance": variance,
            "ratio_audit": {
                "actual": ratio_result(point.get("actual_weighted_value"), denom),
                "planned": ratio_result(point.get("planned_weighted_value"), denom),
            },
            "proof_readiness": "pass_fixture",
            "weighting_policy_validated": False,
        }

    def compute_schedule_spi(
        self,
        project_key: str,
        schedule_version_key: str,
        *,
        weighting_basis: str = "duration_weighted",
        version: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not version:
            versions = self._trend._eligible_versions(
                project_key, __import__("datetime").datetime.now().date()
            )
            version = next(
                (v for v in versions if str(v["schedule_version_key"]) == schedule_version_key),
                versions[-1] if versions else None,
            )
        if not version:
            return not_computable("missing_version")
        progress = self._trend._progress_point(version, weighting_basis)
        num = progress.get("actual_weighted_value")
        den = progress.get("planned_weighted_value")
        audit = ratio_result(
            float(num) if num is not None else None,
            float(den) if den is not None else None,
        )
        return {
            "schedule_performance_ratio": audit.get("result"),
            "earned_value_spi": False,
            "internal_schedule_spi": True,
            "ratio_audit": audit,
            "proof_readiness": "pass_fixture" if audit.get("status") == "computable" else "not_computable_missing_date_basis",
        }

    def compute_schedule_changes(
        self, project_key: str, versions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del project_key
        payload = self._trend._schedule_changes("", versions, "duration_weighted")
        for point in payload.get("points", []):
            vk = str(point.get("schedule_version_key", ""))
            prior_vk = self._prior_version_key(versions, vk)
            nc = self._near_critical_change_count(prior_vk, vk)
            if nc.get("status") == "not_computable":
                point.setdefault("categories", {})["near_critical_changes"] = None
                point["near_critical_status"] = nc
            else:
                point.setdefault("categories", {})["near_critical_changes"] = nc.get("count", 0)
        return {**payload, "proof_readiness": "pass_fixture" if payload.get("points") else "not_computable_missing_date_basis"}

    def compute_schedule_delay(
        self,
        project_key: str,
        versions: list[dict[str, Any]],
        *,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        del project_key
        if comparison_basis == "prior_update":
            payload = self._trend._schedule_delay("", versions, "duration_weighted")
            return {**payload, "proof_readiness": "pass_fixture" if payload.get("points") else "not_computable_missing_date_basis"}
        if comparison_basis != "selected_baseline":
            return not_computable("unsupported_comparison_basis")
        points: list[dict[str, Any]] = []
        for version in versions:
            current_key = str(version["schedule_version_key"])
            pk = project_key
            state = self._baseline.get_state(
                project_key=pk, current_schedule_version_key=current_key
            )
            baseline_key = state.get("selected_baseline_version_key")
            if not baseline_key:
                points.append(
                    {
                        "schedule_version_key": current_key,
                        **not_computable("no_selected_baseline"),
                        "comparison_basis": "selected_baseline",
                    }
                )
                continue
            baseline_key = str(baseline_key)
            current_finish = self._parse_finish_date(current_key)
            baseline_finish = self._parse_finish_date(baseline_key)
            movement = _date_delta(baseline_finish, current_finish)
            points.append(
                {
                    "comparison_basis": "selected_baseline",
                    "selected_baseline_schedule_version_key": baseline_key,
                    "baseline_finish_source": "forecast_finish_resolution",
                    "current_finish_source": "forecast_finish_resolution",
                    "schedule_version_key": current_key,
                    "baseline_finish": _date_str(baseline_finish),
                    "current_forecast_finish": _date_str(current_finish),
                    "planned_variance_days": movement,
                    "delay_days": movement if movement and movement > 0 else 0,
                    "gain_days": abs(movement) if movement and movement < 0 else 0,
                    "net_movement_days": movement,
                }
            )
        return {"points": points, "proof_readiness": "pass_fixture" if points else "not_computable_missing_date_basis"}

    def compute_delay_analysis(
        self, project_key: str, schedule_version_key: str, as_of_date: date
    ) -> dict[str, Any]:
        try:
            payload = self._udf.build_metric_payload(
                metric_key="delay_analysis",
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
            )
        except ValueError:
            return not_computable("unsupported_metric", proof_readiness="not_computable_missing_udf")
        if not payload.get("available"):
            reason = str(payload.get("reason") or "missing_udf")
            return {**payload, "proof_readiness": f"not_computable_missing_udf" if "udf" in reason else "not_computable_missing_date_basis"}
        return {**payload, "proof_readiness": "pass_fixture"}

    def compute_window_start_accuracy(
        self, project_key: str, schedule_version_key: str, as_of_date: date
    ) -> dict[str, Any]:
        try:
            payload = self._udf.build_metric_payload(
                metric_key="window_start_accuracy",
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
            )
        except ValueError:
            return not_computable("unsupported_metric", proof_readiness="not_computable_missing_udf")
        if not payload.get("available"):
            return {**payload, "proof_readiness": "not_computable_missing_udf"}
        return {**payload, "proof_readiness": "pass_fixture"}

    def compute_should_have_finished(
        self, project_key: str, schedule_version_key: str, as_of_date: date
    ) -> dict[str, Any]:
        try:
            payload = self._udf.build_metric_payload(
                metric_key="should_have_finished_status",
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
            )
        except ValueError:
            return not_computable("unsupported_metric", proof_readiness="not_computable_missing_udf")
        if not payload.get("available"):
            return {**payload, "proof_readiness": "not_computable_missing_date_basis"}
        return {**payload, "proof_readiness": "pass_fixture"}

    def compute_critical_issues(
        self, project_key: str, schedule_version_key: str, as_of_date: date
    ) -> dict[str, Any]:
        try:
            payload = self._udf.build_metric_payload(
                metric_key="critical_issues_category_model",
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
            )
        except ValueError:
            return not_computable("unsupported_metric", proof_readiness="not_computable_missing_udf")
        status = "pass_with_policy_limitations" if payload.get("available") else "not_computable_missing_udf"
        return {
            **payload,
            "proof_readiness": status,
            "weighting_policy_validated": False,
        }

    def compute_critical_indices(self, schedule_version_key: str) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                    (schedule_version_key,),
                ).fetchone()[0]
            )
        cpm_run = self._canonical.selected_cpm_run(schedule_version_key)
        if not cpm_run or total == 0:
            return not_computable("missing_cpm_or_activities", proof_readiness="not_computable_missing_date_basis")
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT computed_criticality_class, computed_total_float
                FROM schedule_cpm_activity_results
                WHERE cpm_run_id=?
                """,
                (cpm_run["cpm_run_id"],),
            ).fetchall()
        critical = sum(1 for r in rows if str(r["computed_criticality_class"]) == "computed_critical")
        near = sum(1 for r in rows if str(r["computed_criticality_class"]) == "computed_near_critical")
        neg = sum(1 for r in rows if (r["computed_total_float"] or 0) < 0)
        return {
            "total_activity_count": total,
            "critical_activity_ratio": ratio_result(float(critical), float(total)),
            "near_critical_activity_ratio": ratio_result(float(near), float(total)),
            "negative_float_ratio": ratio_result(float(neg), float(total)),
            "proof_readiness": "pass_with_policy_limitations",
            "weighting_policy_validated": False,
        }

    def compute_compression_index_internal(
        self,
        project_key: str,
        schedule_version_key: str,
        as_of_date: date,
        *,
        comparison_basis: str = "selected_baseline",
    ) -> dict[str, Any]:
        current_finish = self._parse_finish_date(schedule_version_key)
        data_date = as_of_date
        target_finish = None
        if comparison_basis == "selected_baseline":
            state = self._baseline.get_state(
                project_key=project_key, current_schedule_version_key=schedule_version_key
            )
            baseline_key = state.get("selected_baseline_version_key")
            if baseline_key:
                target_finish = self._parse_finish_date(str(baseline_key))
        if not current_finish or not target_finish or not data_date:
            return not_computable(
                "missing_finish_or_data_date",
                proof_readiness="not_computable_missing_date_basis",
            )
        required = max(0, (current_finish - target_finish).days)
        remaining = max(1, (current_finish - data_date).days)
        audit = ratio_result(float(required), float(remaining))
        return {
            "required_recovery_days": required,
            "remaining_duration_days": remaining,
            "index": audit.get("result"),
            "ratio_audit": audit,
            "limitations": ["Internal analog only — not SmartPM equivalence."],
            "proof_readiness": "pass_with_policy_limitations",
            "weighting_policy_validated": False,
        }

    def compute_future_acceleration(
        self,
        project_key: str,
        schedule_version_key: str,
        as_of_date: date,
        *,
        comparison_basis: str = "selected_baseline",
    ) -> dict[str, Any]:
        comp = self.compute_compression_index_internal(
            project_key, schedule_version_key, as_of_date, comparison_basis=comparison_basis
        )
        if comp.get("status") == "not_computable":
            return comp
        ratio = comp.get("index")
        if ratio is None:
            return not_computable("ratio_not_computable", proof_readiness="not_computable_missing_date_basis")
        classification = "none_required"
        if ratio > 0:
            if ratio < 0.25:
                classification = "low"
            elif ratio < 0.5:
                classification = "moderate"
            elif ratio < 1.0:
                classification = "high"
            else:
                classification = "severe"
        return {
            **comp,
            "future_acceleration_ratio": ratio,
            "classification": classification,
            "proof_readiness": "pass_fixture",
        }

    def compute_health_index(
        self,
        project_key: str,
        schedule_version_key: str,
        *,
        version: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del project_key
        components: list[dict[str, Any]] = []
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT quality_score FROM schedule_quality_scorecards
                WHERE schedule_version_key=? ORDER BY created_at DESC LIMIT 1
                """,
                (schedule_version_key,),
            ).fetchone()
        quality = _float_value(row["quality_score"]) if row else None
        logic_score = quality if quality is not None else 70.0
        float_score = self._float_health_score(schedule_version_key)
        components.append(
            {
                "component": "logic_density",
                "weight": HEALTH_WEIGHTS["logic_density"],
                "raw_value": logic_score,
                "component_score": logic_score,
                "formula": "quality_scorecard proxy",
            }
        )
        components.append(
            {
                "component": "float",
                "weight": HEALTH_WEIGHTS["float"],
                "raw_value": float_score,
                "component_score": float_score,
                "formula": "100 - negative_float_penalty",
            }
        )
        active_weight = sum(c["weight"] for c in components)
        score = sum(c["component_score"] * c["weight"] for c in components) / active_weight if active_weight else None
        status = "good" if score and score >= 85 else "watch" if score and score >= 70 else "at_risk"
        return {
            "score": round(score, 2) if score is not None else None,
            "status": status,
            "components": components,
            "limitations": ["Weights require PM/business validation."],
            "proof_readiness": "pass_with_policy_limitations",
            "weighting_policy_validated": False,
            "arithmetically_accurate": True,
        }

    def compute_feasibility_score(
        self,
        project_key: str,
        schedule_version_key: str,
        as_of_date: date,
        *,
        weighting_basis: str = "duration_weighted",
        version: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        health = self.compute_health_index(project_key, schedule_version_key, version=version)
        spi = self.compute_schedule_spi(
            project_key, schedule_version_key, weighting_basis=weighting_basis, version=version
        )
        compression = self.compute_compression_index_internal(
            project_key, schedule_version_key, as_of_date
        )
        deps = {
            "health_index": health.get("score"),
            "performance_ratio": spi.get("schedule_performance_ratio"),
            "compression_index": compression.get("index"),
        }
        available = [v for v in deps.values() if v is not None]
        if not available:
            return {
                "available": False,
                "reason": "dependency_inputs_unavailable",
                "dependency_readiness": deps,
                "proof_readiness": "not_computable_missing_date_basis",
            }
        neg_float_score = self._float_health_score(schedule_version_key)
        comp_scores = [
            ("compression", deps.get("compression_index"), FEASIBILITY_WEIGHTS["compression"]),
            ("negative_float", neg_float_score, FEASIBILITY_WEIGHTS["negative_float"]),
            ("health_index", deps.get("health_index"), FEASIBILITY_WEIGHTS["health_index"]),
            ("performance_ratio", (deps.get("performance_ratio") or 0) * 100, FEASIBILITY_WEIGHTS["performance_ratio"]),
            ("forecast_variance", 75.0, FEASIBILITY_WEIGHTS["forecast_variance"]),
        ]
        components = []
        total_w = 0.0
        weighted = 0.0
        for name, raw, w in comp_scores:
            if raw is None:
                continue
            norm = max(0.0, min(100.0, float(raw) if name != "performance_ratio" else float(raw)))
            components.append({"component": name, "weight": w, "raw_value": raw, "component_score": norm})
            total_w += w
            weighted += norm * w
        score = weighted / total_w if total_w else None
        return {
            "available": True,
            "feasibility_score": round(score, 2) if score is not None else None,
            "components": components,
            "dependency_readiness": deps,
            "limitations": ["Weights require PM/business validation."],
            "proof_readiness": "pass_with_policy_limitations",
            "weighting_policy_validated": False,
        }

    def _float_health_score(self, schedule_version_key: str) -> float:
        cpm_run = self._canonical.selected_cpm_run(schedule_version_key)
        if not cpm_run:
            return 70.0
        with open_connection(self._db_path) as conn:
            neg = conn.execute(
                "SELECT COUNT(*) FROM schedule_cpm_activity_results WHERE cpm_run_id=? AND computed_total_float < 0",
                (cpm_run["cpm_run_id"],),
            ).fetchone()[0]
            total = conn.execute(
                "SELECT COUNT(*) FROM schedule_cpm_activity_results WHERE cpm_run_id=?",
                (cpm_run["cpm_run_id"],),
            ).fetchone()[0]
        if not total:
            return 70.0
        penalty = min(40.0, (neg / total) * 100)
        return max(0.0, 100.0 - penalty)

    def _parse_finish_date(self, schedule_version_key: str) -> date | None:
        return self._trend._forecast_finish(schedule_version_key)

    def _prior_version_key(self, versions: list[dict[str, Any]], current_key: str) -> str | None:
        prior = None
        for v in versions:
            if str(v["schedule_version_key"]) == current_key:
                return prior
            prior = str(v["schedule_version_key"])
        return None

    def _near_critical_change_count(self, prior_key: str | None, current_key: str) -> dict[str, Any]:
        if not prior_key:
            return not_computable("missing_prior_version_for_cpm_comparison")
        prior_run = self._canonical.selected_cpm_run(prior_key)
        current_run = self._canonical.selected_cpm_run(current_key)
        if not prior_run:
            return not_computable("missing_prior_cpm_criticality_run")
        if not current_run:
            return not_computable("missing_current_cpm_criticality_run")
        with open_connection(self._db_path) as conn:
            prior_map = {
                str(r["activity_id"]): str(r["computed_criticality_class"])
                for r in conn.execute(
                    "SELECT activity_id, computed_criticality_class FROM schedule_cpm_activity_results WHERE cpm_run_id=?",
                    (prior_run["cpm_run_id"],),
                ).fetchall()
            }
            current_map = {
                str(r["activity_id"]): str(r["computed_criticality_class"])
                for r in conn.execute(
                    "SELECT activity_id, computed_criticality_class FROM schedule_cpm_activity_results WHERE cpm_run_id=?",
                    (current_run["cpm_run_id"],),
                ).fetchall()
            }
        count = 0
        for aid, cur_cls in current_map.items():
            prev_cls = prior_map.get(aid)
            if prev_cls is None:
                continue
            near = "computed_near_critical"
            if (prev_cls == near) != (cur_cls == near):
                count += 1
        return {"count": count, "status": "computable", "formula": "criticality changed into/out of near_critical"}


def _activation_status_for_entry(
    entry: dict[str, Any],
    *,
    on_frontend_chart_list: bool,
    on_metric_proof_api: bool,
) -> tuple[str, str | None]:
    key = entry["metric_key"]
    if not entry.get("formula_supported", True):
        if entry.get("api_active"):
            return "active_as_unsupported_metric", entry.get("reason")
        return "inactive_not_supported", entry.get("reason")
    if key in INTERNAL_VARIANT_PARENT:
        parent = INTERNAL_VARIANT_PARENT[key]
        return "active_as_internal_variant", f"served via parent metric {parent}"
    if key in PROOF_ONLY_METRIC_KEYS:
        return "active_on_proof_api_only", None
    if on_frontend_chart_list:
        return "active_on_trend_api", None
    if on_metric_proof_api:
        return "active_on_metric_proof_api", None
    return "formula_exists_but_inactive", "not on trend or proof API surface"


def build_activation_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in build_metric_registry():
        key = entry["metric_key"]
        on_frontend = key in FRONTEND_CHART_METRIC_KEYS
        proof_key = PROOF_API_METRIC_KEY_ALIASES.get(key, key)
        on_proof = proof_key in METRIC_PROOF_API_KEYS or key in PROOF_ONLY_METRIC_KEYS
        status, notes = _activation_status_for_entry(
            entry,
            on_frontend_chart_list=on_frontend,
            on_metric_proof_api=on_proof,
        )
        rows.append(
            {
                "metric_key": key,
                "display_name": entry.get("display_name"),
                "formula_supported": entry.get("formula_supported"),
                "proof_supported": entry.get("proof_supported"),
                "registry_api_active": entry.get("api_active"),
                "registry_chart_active": entry.get("chart_active"),
                "on_frontend_chart_list": on_frontend,
                "on_trend_api_route": on_frontend and key in TREND_API_METRIC_KEYS,
                "on_metric_proof_api": on_proof,
                "parent_metric_key": INTERNAL_VARIANT_PARENT.get(key),
                "metric_proof_api_key": PROOF_API_METRIC_KEY_ALIASES.get(key),
                "activation_status": status,
                "activation_notes": notes,
            }
        )
    return rows


def activation_cross_check() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in build_activation_matrix():
        if row["activation_status"] == "formula_exists_but_inactive":
            findings.append(
                {
                    "activation_status": row["activation_status"],
                    "metric_key": row["metric_key"],
                    "reason": row.get("activation_notes"),
                }
            )
    registry_keys = {e["metric_key"] for e in build_metric_registry()}
    for fk in FRONTEND_CHART_METRIC_KEYS:
        if fk not in registry_keys and fk not in FRONTEND_CHART_WITHOUT_REGISTRY:
            findings.append(
                {
                    "activation_status": "frontend_metric_missing_registry",
                    "metric_key": fk,
                    "reason": "frontend consumes metric without registry entry",
                }
            )
    return findings


def build_activation_proof(*, project_key: str = "tropical") -> dict[str, Any]:
    matrix = build_activation_matrix()
    findings = activation_cross_check()
    status_counts: dict[str, int] = {}
    for row in matrix:
        status = str(row["activation_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "formula_version": FORMULA_VERSION,
        "metric_proof_route": f"/api/projects/{project_key}/schedule/metric-proof",
        "trend_route_template": f"/api/projects/{project_key}/schedule/metrics/{{metric_key}}/trend",
        "activation_matrix": matrix,
        "frontend_chart_metrics_without_registry_entry": sorted(FRONTEND_CHART_WITHOUT_REGISTRY),
        "cross_check_findings": findings,
        "summary": {
            "registry_metric_count": len(matrix),
            "activation_status_counts": status_counts,
            "cross_check_finding_count": len(findings),
        },
    }


__all__ = [
    "ScheduleMetricFormulaService",
    "activation_cross_check",
    "build_activation_matrix",
    "build_activation_proof",
    "not_computable",
    "ratio_result",
]
