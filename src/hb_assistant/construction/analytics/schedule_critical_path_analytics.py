"""Source-export critical path analytics for XER and related schedule formats."""

from __future__ import annotations

import json
from typing import Any

from .schedule_quality_normalization import is_logic_excluded_activity

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
MSP_SLACK_ZERO_TOLERANCE_DAYS = 0.0001
MAX_SOURCE_EXPORT_SAMPLES = 10


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


def _raw_source_fields(activity: dict[str, Any]) -> dict[str, Any]:
    for key in ("raw_source_fields_json", "raw_json_redacted"):
        raw = activity.get(key)
        if not raw:
            continue
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _msp_critical_present(activity: dict[str, Any], raw: dict[str, Any]) -> bool:
    if "source_critical_flag_present" in activity:
        return _truthy_flag(activity.get("source_critical_flag_present"))
    if "source_critical_flag_present" in raw:
        return _truthy_flag(raw.get("source_critical_flag_present"))
    if raw.get("source_critical_raw") is not None:
        return True
    if activity.get("critical_path_source") == SOURCE_CRITICAL_BASIS_MSP:
        return True
    if activity.get("source_critical_flag") in (0, 1, False, True):
        return True
    return activity.get("is_critical") in (0, 1, False, True)


def _msp_critical_value(activity: dict[str, Any], raw: dict[str, Any]) -> bool:
    if raw.get("source_critical_raw") is not None:
        return _truthy_flag(raw.get("source_critical_raw"))
    if activity.get("source_critical_flag") is not None:
        return _truthy_flag(activity.get("source_critical_flag"))
    return _truthy_flag(activity.get("is_critical"))


def _msp_total_slack_days(activity: dict[str, Any]) -> float | None:
    days = _float_or_none(activity.get("explicit_total_float_days"))
    if days is not None:
        return days
    hours = _float_or_none(activity.get("explicit_total_float_hours"))
    if hours is not None:
        return hours / 8.0
    return None


def compute_msp_critical_slack_analytics(
    activities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate MSP source Critical/Slack consistency as export evidence only."""
    total_activities = len(activities)
    eligible_activities = 0
    excluded_count = 0
    exclusion_reasons: dict[str, int] = {}
    critical_true_count = 0
    critical_false_count = 0
    critical_missing_count = 0
    total_slack_present_count = 0
    total_slack_missing_count = 0
    free_slack_present_count = 0
    free_slack_missing_count = 0
    eligible_evidence_count = 0
    consistent_count = 0
    inconsistency_count = 0
    critical_true_nonpositive_slack_count = 0
    critical_true_positive_slack_count = 0
    critical_false_negative_slack_count = 0
    samples: list[dict[str, Any]] = []

    for activity in activities:
        excluded, reason = is_logic_excluded_activity(activity)
        if excluded:
            excluded_count += 1
            key = reason or "excluded"
            exclusion_reasons[key] = exclusion_reasons.get(key, 0) + 1
            continue
        eligible_activities += 1
        raw = _raw_source_fields(activity)
        critical_present = _msp_critical_present(activity, raw)
        critical_value = _msp_critical_value(activity, raw) if critical_present else None
        total_slack_days = _msp_total_slack_days(activity)
        total_slack_present = total_slack_days is not None
        free_slack_present = _float_or_none(activity.get("explicit_free_float_days")) is not None

        if critical_present and critical_value:
            critical_true_count += 1
        elif critical_present:
            critical_false_count += 1
        else:
            critical_missing_count += 1
        if total_slack_present:
            total_slack_present_count += 1
        else:
            total_slack_missing_count += 1
        if free_slack_present:
            free_slack_present_count += 1
        else:
            free_slack_missing_count += 1

        if not (critical_present or total_slack_present):
            continue
        eligible_evidence_count += 1

        consistency_status = "indeterminate_missing_critical_or_total_slack"
        if critical_present and total_slack_days is not None:
            if critical_value:
                if total_slack_days <= MSP_SLACK_ZERO_TOLERANCE_DAYS:
                    consistent_count += 1
                    critical_true_nonpositive_slack_count += 1
                    consistency_status = "consistent"
                else:
                    inconsistency_count += 1
                    critical_true_positive_slack_count += 1
                    consistency_status = "critical_true_positive_slack"
            elif total_slack_days < -MSP_SLACK_ZERO_TOLERANCE_DAYS:
                inconsistency_count += 1
                critical_false_negative_slack_count += 1
                consistency_status = "critical_false_negative_slack"
            else:
                consistent_count += 1
                consistency_status = "consistent"

        if consistency_status != "consistent" and len(samples) < MAX_SOURCE_EXPORT_SAMPLES:
            samples.append(
                {
                    "activity_id": activity.get("activity_id"),
                    "activity_name": activity.get("activity_name"),
                    "critical_present": critical_present,
                    "critical_value": critical_value,
                    "total_slack_days": total_slack_days,
                    "consistency_status": consistency_status,
                }
            )

    consistency_ratio = (
        round(consistent_count / eligible_evidence_count, 4)
        if eligible_evidence_count
        else None
    )
    evidence = {
        "source_format": "ms_project_xml",
        "source_critical_basis": SOURCE_CRITICAL_BASIS_MSP,
        "source_field_names": {
            "critical": "Critical",
            "total_slack": "TotalSlack",
            "free_slack": "FreeSlack",
            "total_slack_days": "explicit_total_float_days",
            "free_slack_days": "explicit_free_float_days",
        },
        "total_activity_count": total_activities,
        "eligible_activity_count": eligible_activities,
        "excluded_activity_count": excluded_count,
        "exclusion_reasons": exclusion_reasons,
        "eligible_evidence_activity_count": eligible_evidence_count,
        "critical_true_count": critical_true_count,
        "critical_false_count": critical_false_count,
        "critical_missing_count": critical_missing_count,
        "total_slack_present_count": total_slack_present_count,
        "total_slack_missing_count": total_slack_missing_count,
        "free_slack_present_count": free_slack_present_count,
        "free_slack_missing_count": free_slack_missing_count,
        "critical_true_nonpositive_slack_count": critical_true_nonpositive_slack_count,
        "critical_true_positive_slack_count": critical_true_positive_slack_count,
        "critical_false_negative_slack_count": critical_false_negative_slack_count,
        "consistent_critical_slack_count": consistent_count,
        "inconsistent_critical_slack_count": inconsistency_count,
        "consistency_ratio": consistency_ratio,
        "near_zero_tolerance_days": MSP_SLACK_ZERO_TOLERANCE_DAYS,
        "inconsistency_samples": samples,
        "source_export_only": True,
        "not_a_dcma_critical_path_test": True,
        "cpm_recalculation_performed": False,
        "cpm_recalculation": "not_implemented",
        "dcma_critical_path_test": "not_measurable_requires_recalculation",
        "caveat": (
            "MSP Critical and slack values are source-export evidence only; "
            "they do not prove the DCMA Critical Path Test without CPM recalculation."
        ),
    }
    return {
        **evidence,
        "source_critical_path_evidence_json": json.dumps(evidence, sort_keys=True, default=str),
        "status": "measured_from_msp_critical_flag"
        if eligible_evidence_count
        else METRIC_STATUS_MISSING_SOURCE_CRITICAL,
    }


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
