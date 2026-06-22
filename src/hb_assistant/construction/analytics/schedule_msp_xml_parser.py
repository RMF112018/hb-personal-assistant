"""Microsoft Project 2007 XML schedule parser."""

from __future__ import annotations

import hashlib
import io
import json
import xml.etree.ElementTree as ET
from typing import Any

from .schedule_file_parser import ParsedScheduleBundle, ScheduleImportError
from .schedule_source_posture import apply_source_posture

PARSER_NAME = "schedule_msp_xml_parser"
PARSER_VERSION = "1.0.0"
MSP_NS = "http://schemas.microsoft.com/project/2007"


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    t = (el.text or "").strip()
    return t or None


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _float_or_none(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes_to_days(minutes: float | None, *, minutes_per_day: float = 480.0) -> str | None:
    if minutes is None:
        return None
    return str(round(minutes / minutes_per_day, 4))


def parse_msp_xml_bytes(data: bytes) -> ParsedScheduleBundle:
    if not data:
        raise ScheduleImportError("schedule_import_invalid", message="empty msp xml payload")
    try:
        root = ET.parse(io.BytesIO(data)).getroot()
    except ET.ParseError as exc:
        raise ScheduleImportError("schedule_import_invalid", message="invalid msp xml") from exc

    if _local(root.tag) != "Project":
        raise ScheduleImportError("unsupported_schedule_format", message="not an MSP Project root")

    schedule_name = _text(root.find(f"{{{MSP_NS}}}Name")) or _text(root.find(f"{{{MSP_NS}}}Title"))
    schedule_id = _text(root.find(f"{{{MSP_NS}}}UID")) or schedule_name or "msp-import"
    data_date = _text(root.find(f"{{{MSP_NS}}}StatusDate"))
    planned_start = _text(root.find(f"{{{MSP_NS}}}StartDate"))
    scheduled_finish = _text(root.find(f"{{{MSP_NS}}}FinishDate"))

    calendars = []
    cals_el = root.find(f"{{{MSP_NS}}}Calendars")
    if cals_el is not None:
        for cal in cals_el.findall(f"{{{MSP_NS}}}Calendar"):
            uid = _text(cal.find(f"{{{MSP_NS}}}UID"))
            if uid:
                calendars.append(
                    {
                        "calendar_id": uid,
                        "calendar_name": _text(cal.find(f"{{{MSP_NS}}}Name")),
                        "hours_per_day": "8",
                    }
                )

    tasks_by_uid: dict[str, dict[str, Any]] = {}
    activities: list[dict[str, Any]] = []
    tasks_el = root.find(f"{{{MSP_NS}}}Tasks")
    if tasks_el is not None:
        for task in tasks_el.findall(f"{{{MSP_NS}}}Task"):
            uid = _text(task.find(f"{{{MSP_NS}}}UID"))
            if not uid or _text(task.find(f"{{{MSP_NS}}}Summary")) == "1":
                continue
            act_id = _text(task.find(f"{{{MSP_NS}}}ID")) or uid
            total_slack = _float_or_none(_text(task.find(f"{{{MSP_NS}}}TotalSlack")))
            free_slack = _float_or_none(_text(task.find(f"{{{MSP_NS}}}FreeSlack")))
            critical_raw = _text(task.find(f"{{{MSP_NS}}}Critical"))
            critical = critical_raw == "1"
            baseline_start = _text(task.find(f"{{{MSP_NS}}}BaselineStart"))
            baseline_finish = _text(task.find(f"{{{MSP_NS}}}BaselineFinish"))
            baseline_dur = _text(task.find(f"{{{MSP_NS}}}BaselineDuration"))
            act = {
                "activity_id": str(act_id),
                "source_activity_object_id": uid,
                "activity_name": _text(task.find(f"{{{MSP_NS}}}Name")),
                "wbs_code": _text(task.find(f"{{{MSP_NS}}}WBS")),
                "activity_type": "TT_Mile" if _text(task.find(f"{{{MSP_NS}}}Milestone")) == "1" else "TT_Task",
                "activity_status": _text(task.find(f"{{{MSP_NS}}}Status")),
                "planned_start": _text(task.find(f"{{{MSP_NS}}}Start")),
                "planned_finish": _text(task.find(f"{{{MSP_NS}}}Finish")),
                "start_date": _text(task.find(f"{{{MSP_NS}}}Start")),
                "finish_date": _text(task.find(f"{{{MSP_NS}}}Finish")),
                "actual_start": _text(task.find(f"{{{MSP_NS}}}ActualStart")),
                "actual_finish": _text(task.find(f"{{{MSP_NS}}}ActualFinish")),
                "early_start": _text(task.find(f"{{{MSP_NS}}}EarlyStart")),
                "early_finish": _text(task.find(f"{{{MSP_NS}}}EarlyFinish")),
                "late_start": _text(task.find(f"{{{MSP_NS}}}LateStart")),
                "late_finish": _text(task.find(f"{{{MSP_NS}}}LateFinish")),
                "total_float": str(total_slack) if total_slack is not None else None,
                "free_float": str(free_slack) if free_slack is not None else None,
                "explicit_total_float_hours": str(total_slack / 60.0) if total_slack is not None else None,
                "explicit_total_float_days": _minutes_to_days(total_slack),
                "explicit_free_float_hours": str(free_slack / 60.0) if free_slack is not None else None,
                "explicit_free_float_days": _minutes_to_days(free_slack),
                "source_critical_flag": 1 if critical else 0,
                "is_critical": critical,
                "calendar_id": _text(task.find(f"{{{MSP_NS}}}CalendarUID")),
                "percent_complete": _text(task.find(f"{{{MSP_NS}}}PercentComplete")),
                "duration_original": _text(task.find(f"{{{MSP_NS}}}Duration")),
                "is_milestone": _text(task.find(f"{{{MSP_NS}}}Milestone")) == "1",
                "baseline_start": baseline_start,
                "baseline_finish": baseline_finish,
                "baseline_duration": baseline_dur,
            }
            act["source_row_hash"] = _row_hash(act)
            activities.append(act)
            tasks_by_uid[uid] = act

    relationships = []
    if tasks_el is not None:
        for task in tasks_el.findall(f"{{{MSP_NS}}}Task"):
            succ_uid = _text(task.find(f"{{{MSP_NS}}}UID"))
            if not succ_uid:
                continue
            succ = tasks_by_uid.get(succ_uid)
            if not succ:
                continue
            for pred in task.findall(f"{{{MSP_NS}}}PredecessorLink"):
                pred_uid = _text(pred.find(f"{{{MSP_NS}}}PredecessorUID"))
                if not pred_uid:
                    continue
                pred_act = tasks_by_uid.get(pred_uid)
                if not pred_act:
                    continue
                rel_type = _text(pred.find(f"{{{MSP_NS}}}Type")) or "1"
                type_map = {"0": "FF", "1": "FS", "2": "SF", "3": "SS"}
                lag = _text(pred.find(f"{{{MSP_NS}}}LinkLag")) or "0"
                relationships.append(
                    {
                        "predecessor_activity_id": pred_act["activity_id"],
                        "successor_activity_id": succ["activity_id"],
                        "relationship_type": type_map.get(rel_type, "FS"),
                        "lag_value": lag,
                        "lag_unit": "minute_tenth",
                    }
                )

    baseline_source = "msp_baseline" if any(a.get("baseline_start") for a in activities) else "missing"
    capabilities = apply_source_posture(
        activities, source_format="ms_project_xml", schedule_options={"baseline_source": baseline_source}
    )

    bundle = ParsedScheduleBundle(
        source_capabilities=capabilities,
        schedule_id=str(schedule_id),
        schedule_name=schedule_name,
        data_date=data_date,
        planned_start=planned_start,
        scheduled_finish=scheduled_finish,
        activities=activities,
        relationships=relationships,
        calendars=calendars,
        schedule_options={
            "baseline_source": baseline_source,
            "source_capabilities": capabilities,
            "schedule_options_json": {"namespace": MSP_NS},
        },
    )
    if not activities:
        bundle.validation_findings.append(
            {"severity": "error", "code": "no_activities", "message": "msp xml contained no tasks"}
        )
    return bundle