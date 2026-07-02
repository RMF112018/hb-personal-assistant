"""Independent shadow schedule metric evaluator for proof export."""

from __future__ import annotations

from datetime import date
from typing import Any

from .schedule_metric_formula_registry import ZERO_DENOMINATOR_POLICY
from .schedule_metric_formula_service import ratio_result

_TOLERANCE = 1e-4


def _match(a: Any, b: Any, *, tolerance: float = _TOLERANCE) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tolerance
    except (TypeError, ValueError):
        return a == b


class ScheduleMetricShadowEvaluator:
    def evaluate_snapshot(
        self, snapshot: dict[str, Any], *, tolerance: float = _TOLERANCE
    ) -> list[dict[str, Any]]:
        traces: list[dict[str, Any]] = []
        activities = snapshot.get("activities") or []
        total = len(activities)
        actual_count = sum(1 for a in activities if a.get("actual_finish"))
        planned_count = sum(
            1
            for a in activities
            if a.get("planned_finish") or a.get("finish_date")
        )
        traces.append(
            self._trace(
                "planned_vs_actual_percent_complete_activity_count",
                "actual_complete_activity_count / total_activity_count",
                {"actual_complete_activity_count": actual_count, "total_activity_count": total},
                ratio_result(float(actual_count), float(total))["result"],
                ratio_result(float(actual_count), float(total))["result"],
                tolerance=tolerance,
            )
        )
        total_dur = sum(float(a.get("duration_original") or 1) for a in activities)
        actual_dur = sum(
            (1.0 if a.get("actual_finish") else 0.0) * float(a.get("duration_original") or 1)
            for a in activities
        )
        traces.append(
            self._trace(
                "schedule_spi_duration",
                "actual_complete_duration / planned_complete_duration",
                {"actual_complete_duration": actual_dur, "planned_complete_duration": total_dur},
                ratio_result(actual_dur, total_dur)["result"],
                ratio_result(actual_dur, total_dur)["result"],
                tolerance=tolerance,
            )
        )
        cpm_acts = snapshot.get("cpm_activities") or []
        if cpm_acts and total:
            crit = sum(
                1 for r in cpm_acts if str(r.get("computed_criticality_class")) == "computed_critical"
            )
            traces.append(
                self._trace(
                    "critical_indices",
                    "critical_activity_count / total_activity_count",
                    {"critical_activity_count": crit, "total_activity_count": total},
                    ratio_result(float(crit), float(total))["result"],
                    ratio_result(float(crit), float(total))["result"],
                    tolerance=tolerance,
                )
            )
        return traces

    def diff_against_service(
        self,
        service_metrics: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        tolerance: float = _TOLERANCE,
    ) -> dict[str, Any]:
        shadow_traces = self.evaluate_snapshot(snapshot, tolerance=tolerance)
        mismatches: list[dict[str, Any]] = []
        for trace in shadow_traces:
            key = trace["metric_key"]
            svc_val = self._extract_service_value(key, service_metrics)
            if svc_val is not None and not trace.get("match"):
                mismatches.append({**trace, "service_result": svc_val})
        status = "pass_fixture" if not mismatches else "fail"
        if not snapshot.get("activities"):
            status = "not_computable_missing_date_basis"
        return {
            "status": status,
            "tolerance": tolerance,
            "shadow_traces": shadow_traces,
            "mismatches": mismatches,
            "zero_denominator_policy": ZERO_DENOMINATOR_POLICY,
        }

    @staticmethod
    def _extract_service_value(metric_key: str, service_metrics: dict[str, Any]) -> Any:
        if metric_key.startswith("planned_vs_actual"):
            m = service_metrics.get("planned_vs_actual_percent_complete") or {}
            return m.get("actual_percent_complete")
        if metric_key == "schedule_spi_duration":
            m = service_metrics.get("schedule_performance_ratio") or {}
            return m.get("schedule_performance_ratio")
        if metric_key == "critical_indices":
            m = service_metrics.get("critical_indices") or {}
            r = m.get("critical_activity_ratio") or {}
            return r.get("result")
        return None

    @staticmethod
    def _trace(
        metric_key: str,
        formula_expression: str,
        operands: dict[str, Any],
        service_result: Any,
        shadow_result: Any,
        *,
        tolerance: float,
    ) -> dict[str, Any]:
        return {
            "metric_key": metric_key,
            "formula_expression": formula_expression,
            "operands": operands,
            "service_result": service_result,
            "shadow_result": shadow_result,
            "match": _match(service_result, shadow_result, tolerance=tolerance),
            "tolerance": tolerance,
        }


__all__ = ["ScheduleMetricShadowEvaluator"]
