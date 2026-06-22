"""Source-format capability tagging for schedule imports."""

from __future__ import annotations

from typing import Any


def _truthy_y(value: Any) -> bool:
    return str(value or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def apply_source_posture(
    activities: list[dict[str, Any]],
    *,
    source_format: str,
    schedule_options: dict[str, Any] | None = None,
    source_critical_basis: str | None = None,
) -> dict[str, Any]:
    """Set float_source / critical_path_source on each activity; return capability summary."""
    fmt = str(source_format or "")
    opts = schedule_options or {}
    explicit_float = 0
    driving_path = 0
    critical_flag = 0
    derived_float = 0

    for act in activities:
        if fmt == "primavera_xer":
            tf_h = act.get("explicit_total_float_hours")
            if tf_h is not None and str(tf_h).strip() != "":
                act["float_source"] = "xer_explicit"
                explicit_float += 1
            else:
                act["float_source"] = "missing"
            if act.get("source_critical_flag"):
                critical_flag += 1
            if _truthy_y(act.get("source_driving_path_flag")):
                driving_path += 1
            if not act.get("critical_path_source"):
                if act.get("derived_float_basis"):
                    act["float_source"] = "p6_derived_finish"
                    act["critical_path_source"] = "p6_derived_float_only"
                    derived_float += 1
                else:
                    act["critical_path_source"] = "missing"
        elif fmt == "ms_project_xml":
            if act.get("explicit_total_float_hours") is not None:
                act["float_source"] = "msp_explicit"
                explicit_float += 1
            else:
                act["float_source"] = "missing"
            if act.get("source_critical_flag"):
                act["critical_path_source"] = "msp_critical_flag"
                critical_flag += 1
            else:
                act["critical_path_source"] = "missing"
        else:
            if act.get("derived_float_basis"):
                act["float_source"] = "p6_derived_finish"
                act["critical_path_source"] = "p6_derived_float_only"
                derived_float += 1
            elif act.get("total_float") is not None:
                act["float_source"] = "missing"
                act["critical_path_source"] = "missing"
            else:
                act["float_source"] = "missing"
                act["critical_path_source"] = "missing"

    return {
        "source_format": fmt,
        "explicit_float_count": explicit_float,
        "driving_path_count": driving_path,
        "critical_flag_count": critical_flag,
        "source_critical_activity_count": critical_flag,
        "derived_float_count": derived_float,
        "source_critical_basis": source_critical_basis or opts.get("source_critical_basis"),
        "cpm_recalculation": "not_implemented",
        "schedule_options_present": bool(opts),
    }