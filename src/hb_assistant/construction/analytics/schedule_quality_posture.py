"""Conservative schedule-quality posture helpers."""

from __future__ import annotations

import json
from typing import Any

from .schedule_baseline_quality import compute_baseline_quality_evidence, resolve_status_date
from .schedule_critical_path_analytics import compute_source_critical_path_analytics
from .schedule_float_derivation import supports_finish_float_derivation
from .schedule_quality_normalization import cost_resource_posture

METRIC_STATUS_MEASURED = "measured"
METRIC_STATUS_PASS = "passed_threshold"
METRIC_STATUS_WARN = "warning_threshold"
METRIC_STATUS_FAIL = "failed_threshold"
METRIC_STATUS_DERIVED_FINISH_FLOAT = "measured_from_derived_finish_float"
METRIC_STATUS_EXPLICIT_FLOAT = "measured_from_explicit_source_float"
METRIC_STATUS_SOURCE_EXPORT_PROXY = "measured_from_source_export_proxy"

VALID_THRESHOLD_STATUSES = {
    METRIC_STATUS_PASS,
    METRIC_STATUS_WARN,
    METRIC_STATUS_FAIL,
}
SCORABLE_THRESHOLD_PROXY_STATUSES = {
    METRIC_STATUS_DERIVED_FINISH_FLOAT,
    METRIC_STATUS_EXPLICIT_FLOAT,
    METRIC_STATUS_SOURCE_EXPORT_PROXY,
}


def _evidence_json(metric: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(metric.get("evidence_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _summary(
    category: str,
    *,
    posture: str,
    reason: str | None,
    evidence: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    present: list[str] | None = None,
    caveats: list[str] | None = None,
    source_evidence_class: str | None = None,
    finding_count: int = 0,
) -> dict[str, Any]:
    return {
        "category": category,
        "posture": posture,
        "reason": reason,
        "finding_count": finding_count,
        "evidence": evidence or {},
        "missing_prerequisites": missing or [],
        "present_prerequisites": present or [],
        "caveats": caveats or [],
        "source_evidence_class": source_evidence_class,
    }


def _has_status_date(ctx: Any) -> tuple[bool, dict[str, Any]]:
    evidence = resolve_status_date(
        ctx_data_date=getattr(ctx, "data_date", None),
        import_meta=getattr(ctx, "import_meta", None),
        schedule_version_key=getattr(ctx, "schedule_version_key", None),
    )
    return bool(evidence.get("status_date_parse_success")), evidence


def evaluate_schedule_category(
    ctx: Any,
    category: str,
    *,
    aace: bool = False,
) -> dict[str, Any]:
    activities = list(getattr(ctx, "activities", []) or [])
    relationships = list(getattr(ctx, "relationships", []) or [])
    import_meta = getattr(ctx, "import_meta", None) or {}
    source_format = str(import_meta.get("source_format") or "")

    if aace:
        caveat = "limited source-validation posture only; not a full AACE compliance assessment"
        if category not in {"source_validation", "data_date_integrity", "update_status_integrity"}:
            return _summary(
                category,
                posture="not_measurable",
                reason="AACE category is not implemented in this assessment profile",
                missing=["aace_methodology_implementation"],
                caveats=[caveat],
                source_evidence_class="unsupported",
            )
        base = evaluate_schedule_category(ctx, category)
        if base["posture"] == "pass":
            base["posture"] = "partial"
            base["reason"] = "limited source evidence is present; not full AACE compliance"
        base["caveats"] = [*base.get("caveats", []), caveat]
        return base

    if category == "capturing_all_activities":
        present = []
        missing = []
        if activities:
            present.append("activities_present")
        else:
            missing.append("activities_present")
        if import_meta:
            present.append("import_metadata_present")
        else:
            missing.append("import_metadata_present")
        if not activities:
            return _summary(
                category,
                posture="fail",
                reason="no activities in canonical store",
                evidence={"activity_count": 0, "import_metadata_present": bool(import_meta)},
                missing=missing,
                present=present,
            )
        posture = "pass" if not missing else "partial"
        return _summary(
            category,
            posture=posture,
            reason=None
            if posture == "pass"
            else "activity data present but source evidence is incomplete",
            evidence={
                "activity_count": len(activities),
                "import_metadata_present": bool(import_meta),
            },
            missing=missing,
            present=present,
        )

    if category == "sequencing_all_activities":
        if not activities:
            return _summary(
                category,
                posture="fail",
                reason="no activities available for logic evaluation",
                missing=["activities_present", "relationships_present"],
            )
        if not relationships:
            return _summary(
                category,
                posture="not_measurable",
                reason="no relationships in canonical store",
                evidence={"activity_count": len(activities), "relationship_count": 0},
                missing=["relationships_present"],
                present=["activities_present"],
            )
        return _summary(
            category,
            posture="pass",
            reason=None,
            evidence={"activity_count": len(activities), "relationship_count": len(relationships)},
            present=["activities_present", "relationships_present"],
        )

    if category == "duration_reasonableness":
        has_duration = any(a.get("duration_original") for a in activities)
        return _summary(
            category,
            posture="pass" if has_duration else "not_measurable",
            reason=None if has_duration else "no duration fields",
            evidence={
                "duration_field_count": sum(
                    1 for a in activities if a.get("duration_original")
                )
            },
            present=["duration_fields"] if has_duration else [],
            missing=[] if has_duration else ["duration_fields"],
        )

    if category == "resource_cost_loading":
        schedule_posture = cost_resource_posture(import_meta)
        loaded = sum(1 for a in activities if a.get("cost_loaded_amount") or a.get("resource_id"))
        evidence = {
            "schedule_posture": schedule_posture,
            "resource_or_cost_loaded_activity_count": loaded,
            "activity_count": len(activities),
        }
        if schedule_posture in {"not_cost_loaded", "unknown"}:
            return _summary(
                category,
                posture="not_measurable",
                reason="schedule is not cost- or resource-loaded",
                evidence=evidence,
                missing=["resource_or_cost_loading_evidence"],
                source_evidence_class="missing_source_data",
            )
        return _summary(
            category,
            posture="pass" if loaded else "not_measurable",
            reason=None if loaded else "no resource or cost loading fields",
            evidence=evidence,
            present=["resource_or_cost_loading_evidence"] if loaded else [],
            missing=[] if loaded else ["resource_or_cost_loading_evidence"],
        )

    if category == "horizontal_vertical_traceability":
        if not activities:
            return _summary(
                category,
                posture="not_measurable",
                reason="no activities available for traceability evaluation",
                missing=["activities_present"],
            )
        missing_wbs = sum(1 for a in activities if not a.get("wbs_code"))
        ratio = missing_wbs / len(activities)
        return _summary(
            category,
            posture="warn" if ratio > 0.25 else "pass",
            reason=f"{missing_wbs} activities missing WBS reference" if ratio > 0.25 else None,
            evidence={
                "missing_wbs_reference_count": missing_wbs,
                "activity_count": len(activities),
            },
        )

    if category == "critical_path_validity":
        evidence: dict[str, Any] = {
            "cpm_recalculation_performed": False,
            "critical_path_requires_cpm_recalculation": True,
            "source_export_only_not_cpm": False,
        }
        caveats = ["source-export, proxy, and derived float evidence are not CPM recalculation"]
        if source_format == "primavera_xer":
            analytics = compute_source_critical_path_analytics(
                import_meta,
                activities,
                schedule_options=getattr(ctx, "schedule_options", None),
            )
            source_present = analytics.get("source_critical_basis") != "missing" or int(
                analytics.get("source_driving_path_count") or 0
            ) > 0
            evidence.update(analytics)
            evidence["source_export_only_not_cpm"] = source_present
            return _summary(
                category,
                posture="partial" if source_present else "not_measurable",
                reason=(
                    "source-export critical path evidence is present but "
                    "CPM recalculation is required"
                    if source_present
                    else "no source critical path data and CPM recalculation is required"
                ),
                evidence=evidence,
                missing=["cpm_recalculation"],
                present=["source_export_critical_path_evidence"] if source_present else [],
                caveats=caveats,
                source_evidence_class="source_export_only"
                if source_present
                else "missing_source_data",
            )
        if source_format == "ms_project_xml":
            source_present = any(a.get("source_critical_flag") for a in activities)
            evidence.update(
                {
                    "critical_flag_count": sum(
                        1 for a in activities if a.get("source_critical_flag")
                    ),
                    "source_export_only_not_cpm": source_present,
                }
            )
            return _summary(
                category,
                posture="partial" if source_present else "not_measurable",
                reason=(
                    "MSP critical/slack evidence is present but CPM recalculation is required"
                    if source_present
                    else "no MSP critical/slack evidence and CPM recalculation is required"
                ),
                evidence=evidence,
                missing=["cpm_recalculation"],
                present=["msp_critical_slack_source_evidence"] if source_present else [],
                caveats=caveats,
                source_evidence_class="source_export_only"
                if source_present
                else "missing_source_data",
            )
        derived = any(a.get("derived_float_basis") for a in activities)
        proxy = any(a.get("source_driving_path_flag") for a in activities)
        if derived or proxy:
            evidence.update(
                {
                    "derived_float_activity_count": sum(
                        1 for a in activities if a.get("derived_float_basis")
                    ),
                    "source_driving_path_flag_count": sum(
                        1 for a in activities if a.get("source_driving_path_flag")
                    ),
                    "derived_float_supported": supports_finish_float_derivation(
                        getattr(ctx, "schedule_options", None)
                    ),
                }
            )
            return _summary(
                category,
                posture="partial",
                reason=(
                    "derived/proxy critical-path evidence is present but "
                    "CPM recalculation is required"
                ),
                evidence=evidence,
                missing=["cpm_recalculation"],
                present=["derived_or_proxy_critical_path_evidence"],
                caveats=caveats,
                source_evidence_class="proxy_only" if proxy else "derived_only",
            )
        return _summary(
            category,
            posture="not_measurable",
            reason="no critical path evidence and CPM recalculation is required",
            evidence=evidence,
            missing=["critical_path_source_evidence", "cpm_recalculation"],
            caveats=caveats,
            source_evidence_class="missing_source_data",
        )

    if category == "float_reasonableness":
        has_float = any(a.get("derived_float_basis") for a in activities) or any(
            a.get("total_float") is not None for a in activities
        )
        return _summary(
            category,
            posture="pass" if has_float else "not_measurable",
            reason=None if has_float else "no derived or export float data",
            present=["float_evidence"] if has_float else [],
            missing=[] if has_float else ["float_evidence"],
        )

    if category == "schedule_risk_readiness":
        status_ok, status_evidence = _has_status_date(ctx)
        baseline = compute_baseline_quality_evidence(
            activities=activities,
            ctx_data_date=getattr(ctx, "data_date", None),
            import_meta=import_meta,
            schedule_version_key=getattr(ctx, "schedule_version_key", None),
        )
        present = []
        missing = []
        checks = {
            "activities_present": bool(activities),
            "relationships_present": bool(relationships),
            "parseable_status_date": status_ok,
            "baseline_or_status_evidence": bool(
                baseline.get("true_baseline_finish_dates_available")
            ),
            "measurable_quality_metrics": any(
                a.get("duration_original") for a in activities
            )
            or any(
                a.get("total_float") is not None or a.get("derived_float_basis")
                for a in activities
            ),
            "risk_uncertainty_inputs": False,
        }
        for key, ok in checks.items():
            (present if ok else missing).append(key)
        posture = "partial" if len(present) >= 3 else "warn"
        return _summary(
            category,
            posture=posture,
            reason="risk readiness prerequisites are incomplete",
            evidence={
                "prerequisite_checks": checks,
                "status_date": status_evidence,
                "baseline_finish_count": baseline.get("baseline_finish_count"),
                "target_finish_count": baseline.get("target_finish_count"),
                "planned_finish_count": baseline.get("planned_finish_count"),
                "risk_uncertainty_model_present": False,
            },
            missing=missing,
            present=present,
            caveats=["no schedule risk/uncertainty input model is currently implemented"],
            source_evidence_class="partial",
        )

    if category == "update_status_integrity":
        bad = sum(
            1
            for a in activities
            if (a.get("percent_complete") or 0) and not a.get("actual_start")
        )
        return _summary(
            category,
            posture="warn" if bad else ("pass" if activities else "not_measurable"),
            reason=f"{bad} progressed activities missing actual start" if bad else None,
            evidence={"progress_without_actual_start_count": bad},
            missing=[] if activities else ["activities_present"],
        )

    if category == "baseline_maintenance":
        baseline = compute_baseline_quality_evidence(
            activities=activities,
            ctx_data_date=getattr(ctx, "data_date", None),
            import_meta=import_meta,
            schedule_version_key=getattr(ctx, "schedule_version_key", None),
        )
        has_baseline = bool(baseline.get("true_baseline_finish_dates_available"))
        target_only = bool(baseline.get("only_target_or_planned_dates_available"))
        return _summary(
            category,
            posture="pass" if has_baseline else ("partial" if target_only else "not_measurable"),
            reason=None
            if has_baseline
            else (
                "only target/planned dates are available; true baseline evidence is missing"
                if target_only
                else "missing true baseline finish evidence"
            ),
            evidence=baseline,
            present=["true_baseline_finish"] if has_baseline else [],
            missing=[] if has_baseline else ["true_baseline_finish"],
            caveats=["target/planned dates are non-baseline evidence only"] if target_only else [],
            source_evidence_class="baseline"
            if has_baseline
            else "proxy_only"
            if target_only
            else "missing_source_data",
        )

    if category == "source_validation":
        return _summary(
            category,
            posture="pass" if import_meta else "warn",
            reason=None if import_meta else "missing import metadata",
            evidence={
                "import_metadata_present": bool(import_meta),
                "source_format": source_format or None,
            },
            present=["import_metadata_present"] if import_meta else [],
            missing=[] if import_meta else ["import_metadata_present"],
        )

    if category == "data_date_integrity":
        status_ok, status_evidence = _has_status_date(ctx)
        return _summary(
            category,
            posture="pass" if status_ok else "warn",
            reason=None if status_ok else "data/status date is missing or invalid",
            evidence=status_evidence,
            present=["parseable_status_date"] if status_ok else [],
            missing=[] if status_ok else ["parseable_status_date"],
        )

    if category == "version_over_version_churn":
        prior_diff = getattr(ctx, "prior_diff", None)
        if not prior_diff:
            return _summary(
                category,
                posture="not_measurable",
                reason="no prior version diff available",
                missing=["prior_version_diff"],
            )
        try:
            churn = float(prior_diff.get("logic_churn_rate") or 0)
        except (TypeError, ValueError):
            churn = 0.0
        return _summary(
            category,
            posture="warn" if churn > 0.25 else "pass",
            reason="logic churn elevated versus prior version" if churn > 0.25 else None,
            evidence={"logic_churn_rate": churn},
            present=["prior_version_diff"],
        )

    return _summary(
        category,
        posture="not_measurable",
        reason="category is not implemented",
        missing=["category_implementation"],
        source_evidence_class="unsupported",
    )


def resolve_scorecard_metric_status(metric: dict[str, Any]) -> dict[str, Any]:
    raw_status = str(metric.get("status") or "")
    metric_code = str(metric.get("metric_code") or "")
    metric_family = str(metric.get("metric_family") or "")
    evidence = _evidence_json(metric)
    threshold_status = str(evidence.get("threshold_status") or "")

    if metric_family != "dcma":
        return {
            "metric_code": metric_code,
            "metric_family": metric_family,
            "raw_status": raw_status,
            "resolved_status": None,
            "included": False,
            "exclusion_reason": "non_dcma_advisory_metric",
        }
    if raw_status in VALID_THRESHOLD_STATUSES:
        return {
            "metric_code": metric_code,
            "metric_family": metric_family,
            "raw_status": raw_status,
            "resolved_status": raw_status,
            "included": True,
            "exclusion_reason": None,
        }
    if raw_status in SCORABLE_THRESHOLD_PROXY_STATUSES:
        if threshold_status in VALID_THRESHOLD_STATUSES:
            return {
                "metric_code": metric_code,
                "metric_family": metric_family,
                "raw_status": raw_status,
                "resolved_status": threshold_status,
                "included": True,
                "exclusion_reason": None,
            }
        return {
            "metric_code": metric_code,
            "metric_family": metric_family,
            "raw_status": raw_status,
            "resolved_status": None,
            "included": False,
            "exclusion_reason": "missing_valid_threshold_status",
        }
    return {
        "metric_code": metric_code,
        "metric_family": metric_family,
        "raw_status": raw_status,
        "resolved_status": None,
        "included": False,
        "exclusion_reason": "not_threshold_scorable",
    }


def classify_critical_path_readiness(ctx: Any, metrics: list[dict[str, Any]]) -> dict[str, Any]:
    source_format = str((getattr(ctx, "import_meta", None) or {}).get("source_format") or "")
    source_export = any(m.get("metric_family") == "source_export" for m in metrics)
    derived_or_proxy = any(
        m.get("status")
        in {
            METRIC_STATUS_DERIVED_FINISH_FLOAT,
            METRIC_STATUS_EXPLICIT_FLOAT,
            METRIC_STATUS_SOURCE_EXPORT_PROXY,
        }
        for m in metrics
    ) or any(
        a.get("derived_float_basis") or a.get("source_driving_path_flag")
        for a in getattr(ctx, "activities", []) or []
    )
    if source_export:
        state = "available_source_export_only"
        evidence_class = "source_export_only"
    elif derived_or_proxy:
        state = "available_proxy_or_derived_only"
        evidence_class = "proxy_or_derived_only"
    elif source_format in {"primavera_xer", "ms_project_xml"}:
        state = "not_available_requires_cpm_recalculation"
        evidence_class = "requires_cpm_recalculation"
    else:
        state = "missing_source_data"
        evidence_class = "missing_source_data"
    return {
        "state": state,
        "source_evidence_class": evidence_class,
        "available_cpm_recalculated": False,
        "cpm_recalculation_performed": False,
        "critical_path_requires_cpm_recalculation": True,
        "caveats": [
            "Current critical-path evidence is source-export, proxy, or derived only; "
            "CPM recalculation is not implemented."
        ],
    }
