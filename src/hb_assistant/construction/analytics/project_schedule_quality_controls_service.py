"""PM-safe schedule quality controls read model for Project Schedule Controls."""

from __future__ import annotations

import json
from typing import Any, Literal

from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository

from .project_schedule_analytics_trust_service import default_capability_limitations
from .schedule_quality_profiles import DCMA_METRIC_SPECS

QualityTrustStatus = Literal["ready", "degraded", "blocked", "unavailable"]
QualityRunStatus = Literal["complete", "pending", "running", "failed", "unavailable"]
GroupStatus = QualityTrustStatus

_GROUP_METRIC_CODES: dict[str, list[str]] = {
    "logic_integrity": ["dcma_logic"],
    "constraint_quality": ["dcma_hard_constraints"],
    "float_quality": ["dcma_high_float", "dcma_negative_float"],
    "duration_quality": ["dcma_high_duration"],
    "date_quality": ["dcma_invalid_dates"],
    "critical_path_readiness": [
        "dcma_critical_path_test",
        "source_critical_path_available",
        "source_msp_critical_slack_available",
    ],
    "cost_resource_readiness": ["dcma_resources_cost_loading"],
    "baseline_readiness": ["dcma_missed_tasks"],
}

_FAIL_STATUSES = frozenset({"failed_threshold"})
_WARN_STATUSES = frozenset(
    {
        "warning_threshold",
        "measured_from_derived_finish_float",
        "partially_measurable_critical_float_available",
        "measured_from_source_export_proxy",
    }
)
_PASS_STATUSES = frozenset(
    {
        "passed_threshold",
        "measured",
        "measured_from_xer_driving_path",
        "measured_from_msp_critical_flag",
        "measured_from_explicit_source_float",
        "available_app_cpm_recalculated",
    }
)
_NOT_MEASURABLE = frozenset(
    {
        "not_measurable_missing_data",
        "not_measurable_requires_recalculation",
        "not_measurable_missing_longest_path_data",
        "not_applicable",
    }
)

_PM_FORBIDDEN_KEYS = frozenset(
    {
        "schedule_version_key",
        "schedule_identity_key",
        "import_id",
        "package_id",
        "cpm_run_id",
        "evaluation_run_id",
        "source_export_proxy",
        "source_record_id",
        "activity_id",
        "file_sha256",
        "file_path",
        "failure_message",
    }
)

_LOGIC_EVIDENCE_LABELS: dict[str, str] = {
    "open_start_count": "Open starts",
    "open_finish_count": "Open finishes",
    "duplicate_relationship_count": "Duplicate relationships",
    "self_relationship_count": "Self relationships",
    "invalid_relationship_reference_count": "Invalid relationship references",
}

_METRIC_PM_ACTIONS: dict[str, str] = {
    "dcma_logic": "Review logic integrity counts and confirm whether open ends or duplicate ties need schedule cleanup.",
    "dcma_hard_constraints": "Review hard-constrained activities and confirm constraints reflect the current plan.",
    "dcma_high_float": "Review high-float activities for logic gaps or unnecessary float.",
    "dcma_negative_float": "Review negative-float activities for recovery planning follow-up.",
    "dcma_high_duration": "Review long-duration activities for decomposition or duration reasonableness.",
    "dcma_invalid_dates": "Review invalid or inconsistent dates before relying on forecast dates.",
    "dcma_resources_cost_loading": "Confirm whether cost or resource loading is expected for this schedule update.",
    "dcma_critical_path_test": "Confirm critical-path readiness before relying on driving-path analytics.",
    "dcma_missed_tasks": "Confirm baseline comparison readiness before using missed-task metrics.",
}


def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _metric_by_code(metrics: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(m.get("metric_code") or ""): m for m in metrics if m.get("metric_code")}


def _resolved_metric_status(status: str | None) -> str:
    normalized = str(status or "unknown")
    if normalized in _FAIL_STATUSES:
        return "fail"
    if normalized in _WARN_STATUSES:
        return "warn"
    if normalized in _PASS_STATUSES:
        return "pass"
    if normalized in _NOT_MEASURABLE:
        return "not_measurable"
    return "unknown"


def _group_status_from_metrics(metric_cards: list[dict[str, Any]]) -> GroupStatus:
    if not metric_cards:
        return "unavailable"
    statuses = [str(m.get("resolved_status") or "unknown") for m in metric_cards]
    if any(s == "fail" for s in statuses):
        return "degraded"
    if any(s == "warn" for s in statuses):
        return "degraded"
    measurable = [s for s in statuses if s != "not_measurable"]
    if not measurable:
        return "unavailable"
    if all(s == "pass" for s in measurable):
        return "ready"
    return "degraded"


def _cap_quality_trust(
    quality_status: QualityTrustStatus,
    *,
    analytics_trust_status: str | None,
    identity_gate: str | None,
) -> QualityTrustStatus:
    if identity_gate == "blocked" or analytics_trust_status == "blocked":
        return "blocked"
    if identity_gate == "degraded" or analytics_trust_status == "degraded":
        if quality_status == "ready":
            return "degraded"
    return quality_status


def _normalize_run_status(run: dict[str, Any] | None) -> QualityRunStatus:
    if not run:
        return "unavailable"
    status = str(run.get("status") or "pending")
    if status == "completed":
        return "complete"
    if status in {"pending", "running", "failed"}:
        return status  # type: ignore[return-value]
    return "unavailable"


def _quality_trust_from_run(
    run_status: QualityRunStatus,
    *,
    scorecard: dict[str, Any] | None,
    metrics: list[dict[str, Any]],
) -> QualityTrustStatus:
    if run_status in {"unavailable", "pending", "running"}:
        return "unavailable" if run_status == "unavailable" else "degraded"
    if run_status == "failed":
        return "blocked"
    grade = str((scorecard or {}).get("quality_grade") or "")
    if grade in {"F", "insufficient_data"}:
        return "degraded"
    if any(_resolved_metric_status(str(m.get("status"))) == "fail" for m in metrics):
        return "degraded"
    if run_status == "complete":
        return "ready"
    return "degraded"


def _metric_card(metric: dict[str, Any]) -> dict[str, Any]:
    code = str(metric.get("metric_code") or "")
    spec = DCMA_METRIC_SPECS.get(code, {})
    evidence = _parse_json(metric.get("evidence_json"))
    resolved = _resolved_metric_status(str(metric.get("status")))
    counts: list[dict[str, Any]] = []
    for key, label in _LOGIC_EVIDENCE_LABELS.items():
        if key in evidence:
            counts.append({"label": label, "count": int(evidence.get(key) or 0)})
    numerator = metric.get("numerator")
    denominator = metric.get("denominator")
    if numerator is not None and denominator is not None and not counts:
        counts.append(
            {
                "label": "Affected items",
                "count": int(numerator or 0),
                "denominator": int(denominator or 0),
            }
        )
    return {
        "metric_code": code,
        "label": str(spec.get("metric_name") or code.replace("_", " ").title()),
        "resolved_status": resolved,
        "status_label": str(metric.get("status") or "unknown").replace("_", " "),
        "value": metric.get("value"),
        "counts": counts,
        "not_measurable_reason": metric.get("not_measurable_reason"),
        "recommended_pm_action": _METRIC_PM_ACTIONS.get(code),
    }


def _finding_summary(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "finding_code": str(finding.get("finding_code") or "finding"),
        "severity": str(finding.get("severity") or "advisory"),
        "summary": str(finding.get("finding_summary") or "Schedule quality finding requires review."),
        "category": finding.get("category"),
    }


def _readiness_group(
    *,
    group_key: str,
    label: str,
    downstream: dict[str, Any],
    field: str,
    readiness_label: str,
) -> dict[str, Any]:
    value = downstream.get(field)
    posture = "unavailable"
    summary = f"{readiness_label} is not available for this schedule update."
    if value in {"available", "available_cpm_recalculated", "ready", "ready_with_quality_penalty"}:
        posture = "ready"
        summary = f"{readiness_label} is available for PM review at the current context."
    elif value in {"partially_available", "completed_with_limitations"}:
        posture = "degraded"
        summary = f"{readiness_label} is partially available; review limitations before relying on it."
    elif value in {"blocked", "not_ready", "not_implemented"}:
        posture = "degraded" if value != "not_implemented" else "unavailable"
        summary = f"{readiness_label} is not ready for this schedule update."
    evidence = downstream.get("critical_path_readiness_evidence") if field == "critical_path_analytics" else {}
    metrics = []
    if evidence:
        metrics.append(
            {
                "metric_code": "critical_path_readiness",
                "label": readiness_label,
                "resolved_status": "pass" if posture == "ready" else "warn" if posture == "degraded" else "not_measurable",
                "status_label": str(value or "unknown"),
                "counts": [],
                "recommended_pm_action": "Review critical-path readiness evidence before disposition.",
            }
        )
    return {
        "group_key": group_key,
        "label": label,
        "status": posture,
        "summary": summary,
        "metrics": metrics,
    }


class ProjectScheduleQualityControlsService:
    def __init__(self, *, db_path: str) -> None:
        self._repo = ScheduleQualityRepository(db_path=db_path)

    def build_quality_controls(
        self,
        schedule_version_key: str,
        *,
        analytics_trust: dict[str, Any] | None = None,
        identity_trust: dict[str, Any] | None = None,
        cpm_observability: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trust = analytics_trust or {}
        identity = identity_trust or trust.get("identity_trust") or {}
        identity_gate = str(identity.get("identity_gate") or trust.get("identity_gate") or "ready")
        analytics_status = str(trust.get("analytics_trust_status") or "ready")

        run = self._repo.get_latest_run(schedule_version_key)
        run_status = _normalize_run_status(run)
        scorecard = self._repo.get_latest_scorecard(schedule_version_key) if run else None
        metrics = (
            self._repo.list_metrics(str(run["evaluation_run_id"]))
            if run and run.get("status") == "completed"
            else []
        )
        findings = self._repo.list_findings(schedule_version_key, limit=50)
        metrics_by_code = _metric_by_code(metrics)
        downstream = _parse_json(scorecard.get("downstream_readiness_json") if scorecard else None)

        quality_trust = _quality_trust_from_run(run_status, scorecard=scorecard, metrics=metrics)
        quality_trust = _cap_quality_trust(
            quality_trust,
            analytics_trust_status=analytics_status,
            identity_gate=identity_gate,
        )

        control_groups: list[dict[str, Any]] = []
        for group_key, codes in _GROUP_METRIC_CODES.items():
            cards = [_metric_card(metrics_by_code[c]) for c in codes if c in metrics_by_code]
            if not cards and group_key == "logic_integrity":
                orphan_count = sum(
                    1 for f in findings if str(f.get("finding_code")) == "orphan_relationship"
                )
                if orphan_count:
                    cards.append(
                        {
                            "metric_code": "orphan_relationship",
                            "label": "Orphan relationships",
                            "resolved_status": "warn",
                            "status_label": "persisted findings",
                            "counts": [{"label": "Orphan relationships", "count": orphan_count}],
                            "recommended_pm_action": "Review dangling relationship references.",
                        }
                    )
            label = group_key.replace("_", " ").title().replace("Cpm", "CPM")
            status = _group_status_from_metrics(cards)
            summary = self._group_summary(group_key, cards, findings)
            control_groups.append(
                {
                    "group_key": group_key,
                    "label": label,
                    "status": status,
                    "summary": summary,
                    "metrics": [{k: v for k, v in c.items() if k != "metric_code"} for c in cards],
                }
            )

        cp_readiness = _readiness_group(
            group_key="critical_path_readiness",
            label="Critical path readiness",
            downstream=downstream,
            field="critical_path_analytics",
            readiness_label="Critical path analytics",
        )
        if not any(g["group_key"] == "critical_path_readiness" for g in control_groups):
            control_groups.append(cp_readiness)
        else:
            for group in control_groups:
                if group["group_key"] == "critical_path_readiness":
                    if group["status"] == "unavailable" and cp_readiness["status"] != "unavailable":
                        group["status"] = cp_readiness["status"]
                        group["summary"] = cp_readiness["summary"]

        cost_group = _readiness_group(
            group_key="cost_resource_readiness",
            label="Cost and resource readiness",
            downstream=downstream,
            field="true_cost_loaded_analytics",
            readiness_label="Cost/resource loading analytics",
        )
        for group in control_groups:
            if group["group_key"] == "cost_resource_readiness":
                if group["status"] == "unavailable":
                    group["status"] = cost_group["status"]
                    group["summary"] = cost_group["summary"]

        baseline_group = _readiness_group(
            group_key="baseline_readiness",
            label="Baseline readiness",
            downstream=downstream,
            field="baseline_analytics",
            readiness_label="Baseline comparison analytics",
        )
        for group in control_groups:
            if group["group_key"] == "baseline_readiness":
                if group["status"] == "unavailable":
                    group["status"] = baseline_group["status"]
                    group["summary"] = baseline_group["summary"]

        capability_limitations = list(trust.get("capability_limitations") or [])
        for item in default_capability_limitations():
            if item not in capability_limitations:
                capability_limitations.append(item)
        for metric in metrics:
            if _resolved_metric_status(str(metric.get("status"))) == "not_measurable":
                code = str(metric.get("metric_code") or "")
                spec = DCMA_METRIC_SPECS.get(code, {})
                name = spec.get("metric_name") or code
                reason = metric.get("not_measurable_reason") or "not available in this release"
                line = f"{name}: {reason}."
                if line not in capability_limitations:
                    capability_limitations.append(line)
        if str(downstream.get("cpm_recalculation") or "") == "not_implemented":
            line = "Full in-app CPM recalculation is not implemented; source export float may be used where available."
            if line not in capability_limitations:
                capability_limitations.append(line)

        limitation_group = {
            "group_key": "capability_limitations",
            "label": "Capability limitations",
            "status": "ready",
            "summary": "Known measurement limits for this release. These are not schedule defects.",
            "metrics": [],
            "limitations": capability_limitations[:12],
        }
        control_groups.append(limitation_group)

        top_findings = [_finding_summary(f) for f in findings[:8]]
        recommended = self._recommended_actions(control_groups, quality_trust, identity_gate)

        overall_score = scorecard.get("quality_score") if scorecard else None
        metrics_failed = sum(1 for m in metrics if _resolved_metric_status(str(m.get("status"))) == "fail")
        metrics_available = sum(
            1 for m in metrics if _resolved_metric_status(str(m.get("status"))) != "not_measurable"
        )

        return {
            "quality_trust_status": quality_trust,
            "quality_run_status": run_status,
            "scorecard": {
                "overall_status": quality_trust,
                "overall_score": overall_score,
                "quality_grade": scorecard.get("quality_grade") if scorecard else None,
                "metrics_available": metrics_available,
                "metrics_failed": metrics_failed,
                "completion_posture": scorecard.get("completion_posture") if scorecard else None,
            },
            "control_groups": control_groups,
            "top_findings": top_findings,
            "capability_limitations": capability_limitations[:12],
            "recommended_pm_actions": recommended,
            "cpm_observability_summary": self._cpm_obs_summary(cpm_observability),
        }

    @staticmethod
    def _group_summary(
        group_key: str,
        cards: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> str:
        if not cards:
            return "No quality metrics are available for this group in the current evaluation."
        fails = sum(1 for c in cards if c.get("resolved_status") == "fail")
        warns = sum(1 for c in cards if c.get("resolved_status") == "warn")
        if fails:
            return f"{fails} measured check(s) exceeded fail thresholds in this group."
        if warns:
            return f"{warns} measured check(s) are in warning range for this group."
        related_findings = [
            f
            for f in findings
            if str(f.get("category") or "").startswith("dcma") or group_key.startswith(str(f.get("finding_type") or ""))
        ]
        if related_findings:
            return f"{len(related_findings)} persisted finding(s) support review in this group."
        return "Measured checks in this group are within thresholds for the current evaluation."

    @staticmethod
    def _recommended_actions(
        groups: list[dict[str, Any]],
        quality_trust: QualityTrustStatus,
        identity_gate: str,
    ) -> list[str]:
        actions: list[str] = []
        if identity_gate == "blocked":
            actions.append("Resolve schedule identity trust before relying on quality controls.")
        if quality_trust in {"unavailable", "degraded", "blocked"}:
            actions.append("Confirm the latest schedule quality evaluation completed successfully.")
        for group in groups:
            if group.get("group_key") == "capability_limitations":
                continue
            if group.get("status") in {"degraded", "blocked"}:
                for metric in group.get("metrics") or []:
                    action = metric.get("recommended_pm_action")
                    if action and action not in actions:
                        actions.append(str(action))
        return actions[:8]

    @staticmethod
    def _cpm_obs_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        status = str(row.get("status") or "unknown")
        return {
            "headline": (
                "CPM recompute succeeded for the selected schedule version."
                if status == "success"
                else "CPM recompute did not complete cleanly for the selected schedule version."
            ),
            "status_summary": status,
            "warning_count": int(row.get("warning_count") or 0),
            "error_count": int(row.get("error_count") or 0),
        }


def pm_quality_controls_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip operator-only keys from quality controls for default PM surfaces."""
    out = json.loads(json.dumps(payload))
    return _strip_forbidden(out)


def _strip_forbidden(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _PM_FORBIDDEN_KEYS:
                continue
            cleaned[key] = _strip_forbidden(item)
        return cleaned
    if isinstance(value, list):
        return [_strip_forbidden(item) for item in value]
    return value
