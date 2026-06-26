"""Primavera P6 XER schedule parser."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .schedule_critical_path_analytics import classify_xer_critical_activities
from .schedule_file_parser import ParsedScheduleBundle, ScheduleImportError
from .schedule_float_derivation import apply_derived_float_to_activities
from .schedule_source_posture import apply_source_posture
from .schedule_xer_reader import decode_xer_bytes, read_xer_tables

PARSER_NAME = "schedule_xer_parser"
PARSER_VERSION = "1.0.0"

_PRED_TYPE_MAP = {
    "PR_FS": "FS",
    "PR_FF": "FF",
    "PR_SS": "SS",
    "PR_SF": "SF",
    "FS": "FS",
    "FF": "FF",
    "SS": "SS",
    "SF": "SF",
}


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _truthy_y(value: Any) -> bool:
    return str(value or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def _float_or_none(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hours_to_days(hours: float | None, *, hours_per_day: float) -> str | None:
    if hours is None:
        return None
    if hours_per_day <= 0:
        hours_per_day = 8.0
    return str(round(hours / hours_per_day, 4))


def _xer_schedule_options(project: dict[str, str], sched: dict[str, str]) -> dict[str, Any]:
    float_type = sched.get("sched_float_type") or ""
    mapped_float = {
        "FT_FF": "Finish Float = Late Finish - Early Finish",
        "FT_TF": "Total Float",
        "FT_FF_RC": "Finish Float = Late Finish - Early Finish",
    }.get(float_type, float_type or None)
    use_end = sched.get("sched_use_project_end_date_for_float")
    return {
        "compute_total_float_type": mapped_float,
        "critical_activity_path_type": project.get("critical_path_type"),
        "critical_activity_float_threshold": _float_or_none(project.get("critical_drtn_hr_cnt")),
        "calculate_float_based_on_finish_date": 1 if _truthy_y(use_end) else 0,
        "enable_multiple_longest_path_calc": sched.get("enable_multiple_longest_path_calc"),
        "use_total_float_multiple_longest_paths": sched.get("use_total_float_multiple_longest_paths"),
        "xer_sched_float_type": float_type,
    }


def _calendar_hours(calendars: list[dict[str, str]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for cal in calendars:
        cid = cal.get("clndr_id")
        if not cid:
            continue
        hrs = _float_or_none(cal.get("day_hr_cnt")) or 8.0
        out[str(cid)] = hrs
    return out


def parse_xer_bytes(data: bytes) -> ParsedScheduleBundle:
    if not data:
        raise ScheduleImportError("schedule_import_invalid", message="empty xer payload")
    tables = read_xer_tables(decode_xer_bytes(data))
    coverage = _parser_coverage(tables)
    projects = tables.get("PROJECT") or []
    if not projects:
        raise ScheduleImportError("schedule_import_invalid", message="xer missing PROJECT table")
    project = projects[0]
    sched_rows = tables.get("SCHEDOPTIONS") or []
    sched = sched_rows[0] if sched_rows else {}
    schedule_options = _xer_schedule_options(project, sched)

    calendars_raw = tables.get("CALENDAR") or []
    calendars = []
    for c in calendars_raw:
        if not c.get("clndr_id"):
            continue
        hours_per_day = _float_or_none(c.get("day_hr_cnt")) or 8.0
        hours_per_week = _float_or_none(c.get("week_hr_cnt")) or 40.0
        days_per_week = hours_per_week / hours_per_day if hours_per_day else 5.0
        calendars.append(
            {
                "calendar_id": c.get("clndr_id"),
                "calendar_name": c.get("clndr_name"),
                "hours_per_day": str(hours_per_day),
                "days_per_week": str(days_per_week),
            }
        )
    cal_hours = _calendar_hours(calendars_raw)

    wbs_nodes = []
    for w in tables.get("PROJWBS") or []:
        if not w.get("wbs_id"):
            continue
        wbs_nodes.append(
            {
                "wbs_id": w.get("wbs_id"),
                "parent_wbs_id": w.get("parent_wbs_id"),
                "wbs_code": w.get("wbs_short_name"),
                "wbs_name": w.get("wbs_name"),
            }
        )

    task_by_id: dict[str, dict[str, str]] = {}
    activities: list[dict[str, Any]] = []
    for task in tables.get("TASK") or []:
        task_id = task.get("task_id")
        task_code = (task.get("task_code") or "").strip()
        if not task_id or not task_code:
            continue
        task_by_id[str(task_id)] = task
        cal_id = task.get("clndr_id")
        hpd = cal_hours.get(str(cal_id or ""), 8.0)
        tf_h = _float_or_none(task.get("total_float_hr_cnt"))
        ff_h = _float_or_none(task.get("free_float_hr_cnt"))
        driving = _truthy_y(task.get("driving_path_flag"))
        status_code = str(task.get("status_code") or "")
        act_start_raw = task.get("act_start_date")
        act_end_raw = task.get("act_end_date")
        act = {
            "activity_id": task_code,
            "source_activity_object_id": str(task_id),
            "activity_name": task.get("task_name"),
            "activity_type": task.get("task_type"),
            "activity_status": status_code or None,
            "wbs_id": task.get("wbs_id"),
            "calendar_id": cal_id,
            "planned_start": task.get("early_start_date") or task.get("target_start_date"),
            "planned_finish": task.get("early_end_date") or task.get("target_end_date"),
            "start_date": act_start_raw or task.get("restart_date"),
            "finish_date": act_end_raw or task.get("reend_date"),
            "actual_start": act_start_raw or None,
            "actual_finish": act_end_raw or None,
            "early_start": task.get("early_start_date"),
            "early_finish": task.get("early_end_date"),
            "late_start": task.get("late_start_date"),
            "late_finish": task.get("late_end_date"),
            "remaining_early_start": task.get("rem_early_start_date"),
            "remaining_early_finish": task.get("rem_early_end_date"),
            "remaining_late_start": task.get("rem_late_start_date"),
            "remaining_late_finish": task.get("rem_late_end_date"),
            "target_start": task.get("target_start_date"),
            "target_finish": task.get("target_end_date"),
            "target_duration": task.get("target_drtn_hr_cnt"),
            "constraint_type": task.get("cstr_type"),
            "constraint_date": task.get("cstr_date"),
            "total_float": str(tf_h) if tf_h is not None else None,
            "free_float": str(ff_h) if ff_h is not None else None,
            "explicit_total_float_hours": str(tf_h) if tf_h is not None else None,
            "explicit_total_float_days": _hours_to_days(tf_h, hours_per_day=hpd),
            "explicit_free_float_hours": str(ff_h) if ff_h is not None else None,
            "explicit_free_float_days": _hours_to_days(ff_h, hours_per_day=hpd),
            "source_driving_path_flag": 1 if driving else 0,
            "source_longest_path_flag": 1 if driving else 0,
            "is_longest_path": driving,
            "float_path": task.get("float_path"),
            "float_path_order": task.get("float_path_order"),
            "critical_path_number": task.get("crt_path_num"),
            "percent_complete": task.get("phys_complete_pct"),
            "duration_original": task.get("target_drtn_hr_cnt"),
            "duration_remaining": task.get("remain_drtn_hr_cnt"),
            "duration_unit": "hour",
            "is_milestone": str(task.get("task_type") or "").endswith("Mile"),
        }
        act["source_row_hash"] = _row_hash(act)
        activities.append(act)

    relationships = []
    for pred in tables.get("TASKPRED") or []:
        succ_id = pred.get("task_id")
        pred_id = pred.get("pred_task_id")
        if not succ_id or not pred_id:
            continue
        succ = task_by_id.get(str(succ_id), {})
        pre = task_by_id.get(str(pred_id), {})
        succ_code = succ.get("task_code")
        pred_code = pre.get("task_code")
        if not succ_code or not pred_code:
            continue
        raw_type = pred.get("pred_type") or "PR_FS"
        relationships.append(
            {
                "predecessor_activity_id": pred_code,
                "successor_activity_id": succ_code,
                "relationship_type": _PRED_TYPE_MAP.get(raw_type, raw_type),
                "lag_value": pred.get("lag_hr_cnt") or "0",
                "lag_unit": "hour",
                "source_relationship_object_id": pred.get("task_pred_id"),
            }
        )

    actv_type_by_id = {
        str(row.get("actv_code_type_id")): row.get("actv_code_type")
        for row in tables.get("ACTVTYPE") or []
        if row.get("actv_code_type_id")
    }
    actv_code_by_id = {
        str(row.get("actv_code_id")): row.get("actv_code_name") or row.get("short_name")
        for row in tables.get("ACTVCODE") or []
        if row.get("actv_code_id")
    }
    code_assignments = []
    for row in tables.get("TASKACTV") or []:
        activity_id = task_by_id.get(str(row.get("task_id") or ""), {}).get("task_code")
        if not activity_id:
            continue
        type_id = str(row.get("actv_code_type_id") or "")
        value_id = str(row.get("actv_code_id") or "")
        code_assignments.append(
            {
                "activity_id": activity_id,
                "code_type": actv_type_by_id.get(type_id) or type_id or None,
                "code_value": actv_code_by_id.get(value_id) or value_id or None,
                "source_object_id": value_id or None,
            }
        )

    udf_type_by_id: dict[str, dict[str, str | None]] = {}
    for row in tables.get("UDFTYPE") or []:
        type_id = str(row.get("udf_type_id") or "")
        if not type_id:
            continue
        udf_type_by_id[type_id] = {
            "name": row.get("udf_type_name") or row.get("udf_type_label"),
            "data_type": row.get("logical_data_type"),
        }
    udf_values = []
    for row in tables.get("UDFVALUE") or []:
        if not row.get("fk_id") or not row.get("udf_type_id"):
            continue
        activity_id = task_by_id.get(str(row.get("fk_id") or ""), {}).get("task_code")
        if not activity_id:
            continue
        type_id = str(row.get("udf_type_id"))
        meta = udf_type_by_id.get(type_id, {})
        udf_values.append(
            {
                "activity_id": activity_id,
                "udf_type_name": meta.get("name") or type_id,
                "udf_data_type": meta.get("data_type"),
                "udf_value": row.get("udf_text") or row.get("udf_number") or row.get("udf_date"),
                "source_object_id": type_id,
            }
        )

    baseline_source = "missing"
    if _truthy_y(project.get("use_project_baseline_flag")) and project.get("sum_base_proj_id"):
        baseline_source = "xer_project"

    apply_derived_float_to_activities(
        activities,
        options=schedule_options,
        calendars=calendars,
    )
    source_critical_basis = classify_xer_critical_activities(
        activities,
        critical_path_type=project.get("critical_path_type"),
        threshold_hours=project.get("critical_drtn_hr_cnt"),
    )
    capabilities = apply_source_posture(
        activities,
        source_format="primavera_xer",
        schedule_options=schedule_options,
        source_critical_basis=source_critical_basis,
    )

    source_metadata = {
        k: project.get(k)
        for k in (
            "proj_id",
            "proj_short_name",
            "proj_name",
            "plan_start_date",
            "plan_end_date",
            "last_recalc_date",
            "critical_path_type",
            "critical_drtn_hr_cnt",
        )
        if project.get(k)
    }
    bundle = ParsedScheduleBundle(
        source_capabilities=capabilities,
        schedule_id=str(project.get("proj_id") or project.get("proj_short_name") or "xer-import"),
        schedule_name=project.get("proj_short_name") or project.get("proj_id"),
        source_project_id=str(project.get("proj_id") or "") or None,
        source_project_name=project.get("proj_name"),
        source_project_short_name=project.get("proj_short_name"),
        source_project_metadata_json=json.dumps(source_metadata, sort_keys=True, default=str)
        if source_metadata
        else None,
        data_date=project.get("last_recalc_date") or project.get("add_date"),
        planned_start=project.get("plan_start_date"),
        scheduled_finish=project.get("plan_end_date") or project.get("scd_end_date"),
        activities=activities,
        relationships=relationships,
        wbs_nodes=wbs_nodes,
        calendars=calendars,
        code_assignments=[c for c in code_assignments if c.get("activity_id")],
        udf_values=udf_values,
        schedule_options={
            **schedule_options,
            "critical_path_type": project.get("critical_path_type"),
            "critical_float_threshold": project.get("critical_drtn_hr_cnt"),
            "baseline_source": baseline_source,
            "parser_coverage": coverage,
            "source_capabilities": capabilities,
            "schedule_options_json": {
                "project": {k: project.get(k) for k in (
                    "critical_path_type",
                    "critical_drtn_hr_cnt",
                    "use_project_baseline_flag",
                    "sum_base_proj_id",
                )},
                "schedoptions": {k: sched.get(k) for k in (
                    "sched_float_type",
                    "sched_use_project_end_date_for_float",
                    "enable_multiple_longest_path_calc",
                    "use_total_float_multiple_longest_paths",
                )},
            },
        },
    )
    if not activities:
        bundle.validation_findings.append(
            {"severity": "error", "code": "no_activities", "message": "xer contained no TASK rows"}
        )
    return bundle


def _parser_coverage(tables: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    fields_present: dict[str, int] = {}
    for table_name, rows in tables.items():
        for row in rows:
            for field, value in row.items():
                if str(value or "").strip():
                    key = f"{table_name}.{field}"
                    fields_present[key] = fields_present.get(key, 0) + 1
    project = (tables.get("PROJECT") or [{}])[0]
    return {
        "tables_present": {name: len(rows) for name, rows in tables.items()},
        "fields_present": fields_present,
        "baseline_reference": {
            "use_project_baseline_flag": project.get("use_project_baseline_flag"),
            "sum_base_proj_id": project.get("sum_base_proj_id"),
            "orig_proj_id": project.get("orig_proj_id"),
            "source_proj_id": project.get("source_proj_id"),
            "baseline_project_rows_exported": False,
        },
    }
