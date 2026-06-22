"""Source-export critical path analytics for XER and related schedule formats."""

from __future__ import annotations

import json
from typing import Any

SOURCE_CRITICAL_BASIS_XER_DRIVING = "xer_driving_path_flag"
SOURCE_CRITICAL_BASIS_XER_TOTFLOAT = "xer_total_float_threshold"
SOURCE_CRITICAL_BASIS_MSP = "msp_critical_flag"
SOURCE_CRITICAL_BASIS_P6_DERIVED = "p6_derived_float_only"
SOURCE_CRITICAL_BASIS_MISSING = "missing"

XER_DRIVING_PATH_TYPES: frozenset[str] = frozenset({"CT_DrivPath", "CP_DrivPath", "CP_Drtn"})
XER_TOTFLOAT_PATH_TYPES: frozenset[str] = frozenset({"CT_TotFloat", "CP_TotFloat"})

METRIC_STATUS_AVAILABLE_XER_DRIVING = "available_xer_driving_path"
METRIC_STATUS_AVAILABLE_XER_TOTFLOAT = "available_xer_total_float_threshold"
METRIC_STATUS_PARTIAL_XER_FLOAT = "partial_xer_float_coverage"
METRIC_STATUS_MISSING_SOURCE_CRITICAL = "missing_source_critical_data"


def _truthy_flag(value: Any) -> bool:
    if value in (1, True):
        return True
    return str(value or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def _float_or_none(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_xer_critical_basis(critical_path_type: str | None) -> str:
    cpt = str(critical_path_type or "").strip()
    if cpt in XER_DRIVING_PATH_TYPES:
        return SOURCE_CRITICAL_BASIS_XER_DRIVING
    if cpt in XER_TOTFLOAT_PATH_TYPES:
        return SOURCE_CRITICAL_BASIS_XER_TOTFLOAT
    return SOURCE_CRITICAL_BASIS_MISSING


def classify_xer_critical_activities(
    activities: list[dict[str, Any]],
    *,
    critical_path_type: str | None,
    threshold_hours: Any,
) -> str:
    """Tag source_critical_flag / critical_path_source from XER export basis."""
    basis = resolve_xer_critical_basis(critical_path_type)
    threshold = _float_or_none(threshold_hours)
    if threshold is None:
        threshold = 0.0

    for act in activities:
        act.setdefault("source_critical_flag", 0)
        driving = _truthy_flag(act.get("source_driving_path_flag"))
        tf_h = _float_or_none(act.get("explicit_total_float_hours"))

        if basis == SOURCE_CRITICAL_BASIS_XER_DRIVING:
            if driving:
                act["source_critical_flag"] = 1
                act["critical_path_source"] = SOURCE_CRITICAL_BASIS_XER_DRIVING
            else:
                act["source_critical_flag"] = 0
                if act.get("critical_path_source") == SOURCE_CRITICAL_BASIS_XER_DRIVING:
                    act["critical_path_source"] = SOURCE_CRITICAL_BASIS_MISSING
        elif basis == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT:
            if tf_h is not None and tf_h <= threshold + 0.0001:
                act["source_critical_flag"] = 1
                act["critical_path_source"] = SOURCE_CRITICAL_BASIS_XER_TOTFLOAT
            else:
                act["source_critical_flag"] = 0
                if driving:
                    act["critical_path_source"] = SOURCE_CRITICAL_BASIS_XER_DRIVING
                elif act.get("critical_path_source") == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT:
                    act["critical_path_source"] = SOURCE_CRITICAL_BASIS_MISSING
        else:
            act["source_critical_flag"] = 0
            if driving:
                act["critical_path_source"] = SOURCE_CRITICAL_BASIS_XER_DRIVING

    return basis


def compute_source_critical_path_analytics(
    import_meta: dict[str, Any] | None,
    activities: list[dict[str, Any]],
    *,
    schedule_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate source critical path analytics from import meta + activities."""
    meta = import_meta or {}
    opts = schedule_options or {}
    critical_path_type = (
        meta.get("critical_path_type")
        or opts.get("critical_path_type")
        or opts.get("critical_activity_path_type")
    )
    threshold_raw = (
        meta.get("critical_float_threshold")
        or opts.get("critical_float_threshold")
        or opts.get("critical_activity_float_threshold")
    )
    threshold_hours = _float_or_none(threshold_raw)
    if threshold_hours is None:
        threshold_hours = 0.0

    basis = resolve_xer_critical_basis(str(critical_path_type or ""))
    activity_count = len(activities)
    explicit_float_count = 0
    total_float_le_zero_count = 0
    driving_path_count = 0
    driving_path_with_float_count = 0
    driving_path_with_nonpositive_float_count = 0
    source_critical_activity_count = 0

    for act in activities:
        tf_h = _float_or_none(act.get("explicit_total_float_hours"))
        driving = _truthy_flag(act.get("source_driving_path_flag"))

        if tf_h is not None:
            explicit_float_count += 1
            if tf_h <= threshold_hours + 0.0001:
                total_float_le_zero_count += 1
        if driving:
            driving_path_count += 1
            if tf_h is not None:
                driving_path_with_float_count += 1
                if tf_h <= threshold_hours + 0.0001:
                    driving_path_with_nonpositive_float_count += 1

    if basis == SOURCE_CRITICAL_BASIS_XER_DRIVING:
        source_critical_activity_count = driving_path_count
    elif basis == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT:
        source_critical_activity_count = total_float_le_zero_count
    else:
        source_critical_activity_count = sum(
            1 for act in activities if _truthy_flag(act.get("source_critical_flag"))
        )

    if basis == SOURCE_CRITICAL_BASIS_XER_DRIVING:
        coverage_count = driving_path_with_float_count
        coverage_denominator = activity_count
        coverage_basis = "all_activities"
        caveat = (
            "Source critical activities are those with XER driving_path_flag=Y when "
            "PROJECT.critical_path_type is CT_DrivPath. This is export metadata, not CPM recalculation."
        )
    elif basis == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT:
        coverage_count = explicit_float_count
        coverage_denominator = activity_count
        coverage_basis = "all_activities"
        caveat = (
            "Source critical activities use total_float_hr_cnt <= critical_drtn_hr_cnt when "
            "PROJECT.critical_path_type is CT_TotFloat. Completed activities may have blank "
            "float fields in XER; driving_path_flag counts are separate export evidence."
        )
    else:
        coverage_count = explicit_float_count
        coverage_denominator = activity_count
        coverage_basis = "all_activities"
        caveat = "No recognized XER critical path type; driving path flags may still be present."

    evidence = {
        "source_critical_basis": basis,
        "source_critical_path_type": critical_path_type,
        "source_critical_float_threshold_hours": threshold_hours,
        "source_critical_activity_count": source_critical_activity_count,
        "source_driving_path_count": driving_path_count,
        "explicit_float_activity_count": explicit_float_count,
        "total_float_le_zero_count": total_float_le_zero_count,
        "driving_path_with_explicit_float_count": driving_path_with_float_count,
        "driving_path_with_nonpositive_float_count": driving_path_with_nonpositive_float_count,
        "source_critical_coverage_count": coverage_count,
        "source_critical_coverage_denominator": coverage_denominator,
        "source_critical_coverage_basis": coverage_basis,
        "activity_count": activity_count,
        "caveat": caveat,
        "cpm_recalculation": "not_implemented",
        "dcma_critical_path_test": "not_measurable_requires_recalculation",
    }

    if basis == SOURCE_CRITICAL_BASIS_XER_DRIVING and source_critical_activity_count > 0:
        status = METRIC_STATUS_AVAILABLE_XER_DRIVING
    elif basis == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT and source_critical_activity_count > 0:
        status = METRIC_STATUS_AVAILABLE_XER_TOTFLOAT
    elif basis == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT and explicit_float_count > 0:
        status = METRIC_STATUS_PARTIAL_XER_FLOAT
    else:
        status = METRIC_STATUS_MISSING_SOURCE_CRITICAL

    return {
        **evidence,
        "source_critical_path_evidence_json": json.dumps(evidence, sort_keys=True, default=str),
        "status": status,
    }


def resolve_analytics_status(analytics: dict[str, Any]) -> str:
    return str(analytics.get("status") or METRIC_STATUS_MISSING_SOURCE_CRITICAL)