"""Primavera P6 APIBusinessObjects PMXML/XML parser (stdlib xml.etree only).

Handles exports like GMA.xml, TWNU07.xml, CARETTABL.xml from Primavera P6 Professional
(APIBusinessObjects root, Activity/Relationship/WBS/Calendar/ActivityCode* entities).
Uses iterparse for large schedules (10MB+).
"""

from __future__ import annotations

import hashlib
import io
import json
import xml.etree.ElementTree as ET
from typing import Any

from .schedule_file_parser import ParsedScheduleBundle, ScheduleImportError
from .schedule_float_derivation import (
    apply_derived_float_to_activities,
    merge_schedule_options,
    parse_schedule_options,
)

PARSER_NAME = "schedule_xml_parser"
PARSER_VERSION = "1.2.0"

_ACTIVITY_TAGS = frozenset({"Activity", "activity", "TASK"})
_RELATIONSHIP_TAGS = frozenset({"Relationship", "relationship", "TaskPred", "TaskPredecessor"})
_WBS_TAGS = frozenset({"WBS", "wbs", "ProjWBS", "ProjectWBS"})
_CALENDAR_TAGS = frozenset({"Calendar", "calendar"})

_MILESTONE_TYPES = frozenset(
    {"Start Milestone", "Finish Milestone", "Start Milestone w/ Duration", "Finish Milestone w/ Duration"}
)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    t = (el.text or "").strip()
    return t or None


def _field_map(el: ET.Element) -> dict[str, str]:
    return {name: val for name, val in ((_local(c.tag), _text(c)) for c in el) if val is not None}


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "y", "yes"}


def _cost_total(fields: dict[str, str]) -> tuple[str | None, str]:
    """Return (amount, source_type) from P6 cost columns when present."""
    pairs = (
        ("AtCompletionLaborCost", "activity_cost"),
        ("AtCompletionNonLaborCost", "activity_cost"),
        ("AtCompletionExpenseCost", "expense"),
        ("PlannedLaborCost", "activity_cost"),
        ("PlannedNonLaborCost", "activity_cost"),
        ("RemainingLaborCost", "activity_cost"),
        ("RemainingNonLaborCost", "activity_cost"),
        ("ActualLaborCost", "activity_cost"),
        ("ActualNonLaborCost", "activity_cost"),
    )
    best: tuple[str | None, str] = (None, "none")
    total = 0.0
    used = False
    for key, source in pairs:
        raw = fields.get(key)
        if not raw:
            continue
        try:
            val = float(raw)
        except ValueError:
            continue
        if val != 0.0:
            total += val
            used = True
            best = (str(val), source)
    if used and total > 0:
        return (f"{total:.4f}".rstrip("0").rstrip("."), "activity_cost")
    return best


def _parse_activity_codes(
    el: ET.Element,
    *,
    code_types: dict[str, str],
    code_values: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for child in el:
        if _local(child.tag) != "Code":
            continue
        type_oid = _text(child.find("TypeObjectId")) or _text(
            next((c for c in child if _local(c.tag) == "TypeObjectId"), None)
        )
        value_oid = _text(child.find("ValueObjectId")) or _text(
            next((c for c in child if _local(c.tag) == "ValueObjectId"), None)
        )
        if not type_oid or not value_oid:
            continue
        meta = code_values.get(value_oid, {})
        out.append(
            {
                "code_type": code_types.get(type_oid, type_oid),
                "code_value": meta.get("value") or value_oid,
                "code_description": meta.get("desc"),
                "source_object_id": value_oid,
            }
        )
    return out


def _activity_row(
    fields: dict[str, str],
    *,
    nested_codes: list[dict[str, str]],
    wbs_by_oid: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    human_id = fields.get("Id") or fields.get("ActivityId") or fields.get("activity_id")
    object_id = fields.get("ObjectId")
    if not human_id and object_id:
        human_id = object_id
    if not human_id:
        return None

    wbs_oid = fields.get("WBSObjectId")
    wbs_meta = wbs_by_oid.get(wbs_oid or "", {})

    cost_amount, cost_source = _cost_total(fields)
    row: dict[str, Any] = {
        "activity_id": human_id,
        "source_activity_object_id": object_id or human_id,
        "activity_name": fields.get("Name") or fields.get("activity_name"),
        "activity_type": fields.get("Type") or fields.get("activity_type"),
        "activity_status": fields.get("Status") or fields.get("status"),
        "planned_start": fields.get("PlannedStartDate"),
        "planned_finish": fields.get("PlannedFinishDate"),
        "start_date": fields.get("StartDate") or fields.get("start_date"),
        "finish_date": fields.get("FinishDate") or fields.get("finish_date"),
        "early_start": fields.get("ExternalEarlyStartDate") or fields.get("EarlyStartDate"),
        "early_finish": fields.get("ExternalEarlyFinishDate") or fields.get("EarlyFinishDate"),
        "late_start": fields.get("LateStartDate"),
        "late_finish": fields.get("LateFinishDate"),
        "actual_start": fields.get("ActualStartDate"),
        "actual_finish": fields.get("ActualFinishDate"),
        "remaining_early_start": fields.get("RemainingEarlyStartDate"),
        "remaining_early_finish": fields.get("RemainingEarlyFinishDate"),
        "remaining_late_start": fields.get("RemainingLateStartDate"),
        "remaining_late_finish": fields.get("RemainingLateFinishDate"),
        "remaining_start": fields.get("RemainingEarlyStartDate"),
        "remaining_finish": fields.get("RemainingEarlyFinishDate"),
        "duration_original": fields.get("PlannedDuration")
        or fields.get("AtCompletionDuration")
        or fields.get("OriginalDuration")
        or fields.get("duration"),
        "duration_remaining": fields.get("RemainingDuration"),
        "duration_actual": fields.get("ActualDuration"),
        "duration_unit": fields.get("DurationType") or fields.get("duration_unit") or "hour",
        "percent_complete": fields.get("PercentComplete") or fields.get("percent_complete"),
        "physical_percent_complete": fields.get("PhysicalPercentComplete"),
        "duration_percent_complete": fields.get("DurationPercentComplete"),
        "wbs_id": wbs_oid or fields.get("wbs_id"),
        "wbs_code": wbs_meta.get("wbs_code") or fields.get("WBSCode") or fields.get("wbs_code"),
        "wbs_path": wbs_meta.get("wbs_path"),
        "calendar_id": fields.get("CalendarObjectId") or fields.get("calendar_id"),
        "constraint_type": fields.get("PrimaryConstraintType") or fields.get("ConstraintType"),
        "constraint_date": fields.get("PrimaryConstraintDate") or fields.get("ConstraintDate"),
        "deadline_date": fields.get("DeadlineDate") or fields.get("deadline_date"),
        "total_float": fields.get("TotalFloat"),
        "free_float": fields.get("FreeFloat"),
        "is_critical": 1 if _truthy(fields.get("IsCritical") or fields.get("Critical")) else 0,
        "is_longest_path": 1 if _truthy(fields.get("IsLongestPath")) else 0,
        "is_milestone": 1
        if (fields.get("Type") in _MILESTONE_TYPES or _truthy(fields.get("Milestone")))
        else 0,
        "cost_code": fields.get("CostAccountId") or fields.get("cost_code"),
        "cost_loaded_amount": cost_amount,
        "cost_loaded_source_type": cost_source,
        "estimated_weight": fields.get("EstimatedWeight"),
        "nested_codes": nested_codes,
    }

    for code in nested_codes:
        ctype = (code.get("code_type") or "").lower()
        if "cost" in ctype and not row.get("cost_code"):
            row["cost_code"] = code.get("code_value")

    return row


def parse_pmxml_bytes(data: bytes | io.BufferedIOBase) -> ParsedScheduleBundle:
    if isinstance(data, bytes):
        stream: io.BytesIO | io.BufferedIOBase = io.BytesIO(data)
    else:
        stream = data
        if hasattr(stream, "seek"):
            stream.seek(0)

    bundle = ParsedScheduleBundle(schedule_id="imported-schedule", schedule_name=None)
    code_types: dict[str, str] = {}
    code_values: dict[str, dict[str, str]] = {}
    wbs_by_oid: dict[str, dict[str, str]] = {}
    object_to_activity_id: dict[str, str] = {}
    raw_relationships: list[dict[str, str]] = []
    project_seen = False

    try:
        for _event, el in ET.iterparse(stream, events=("end",)):
            tag = _local(el.tag)

            if tag == "ActivityCodeType":
                fields = _field_map(el)
                oid = fields.get("ObjectId")
                if oid:
                    code_types[oid] = fields.get("Name") or oid

            elif tag == "ActivityCode":
                fields = _field_map(el)
                oid = fields.get("ObjectId")
                if oid:
                    code_values[oid] = {
                        "value": fields.get("CodeValue") or "",
                        "desc": fields.get("Description") or "",
                        "type_oid": fields.get("CodeTypeObjectId") or "",
                    }

            elif tag == "ScheduleOptions":
                bundle.schedule_options = merge_schedule_options(
                    bundle.schedule_options, parse_schedule_options(_field_map(el))
                )

            elif tag == "Project" and not project_seen:
                fields = _field_map(el)
                project_seen = True
                bundle.schedule_options = merge_schedule_options(
                    bundle.schedule_options,
                    parse_schedule_options(
                        {
                            k: fields[k]
                            for k in (
                                "ComputeTotalFloatType",
                                "CriticalActivityPathType",
                                "CriticalActivityFloatThreshold",
                                "CalculateFloatBasedOnFinishDate",
                            )
                            if k in fields
                        }
                    ),
                )
                bundle.schedule_name = fields.get("Name") or bundle.schedule_name
                bundle.data_date = fields.get("DataDate") or bundle.data_date
                bundle.planned_start = fields.get("PlannedStartDate") or fields.get("AnticipatedStartDate")
                bundle.scheduled_finish = (
                    fields.get("ScheduledFinishDate")
                    or fields.get("FinishDate")
                    or fields.get("AnticipatedFinishDate")
                )
                sid = fields.get("Id") or fields.get("ObjectId")
                if sid:
                    bundle.schedule_id = sid
                    bundle.procore_project_id = fields.get("ObjectId") or sid

            elif tag in _WBS_TAGS:
                fields = _field_map(el)
                wbs_id = fields.get("ObjectId") or fields.get("WBSId")
                if wbs_id:
                    parent = fields.get("ParentObjectId")
                    code = fields.get("Code")
                    path = f"{parent}/{code}" if parent and code else code
                    node = {
                        "wbs_id": wbs_id,
                        "parent_wbs_id": parent,
                        "wbs_code": code,
                        "wbs_name": fields.get("Name"),
                        "wbs_path": path,
                        "sequence_order": int(fields["SequenceNumber"])
                        if fields.get("SequenceNumber", "").isdigit()
                        else None,
                        "source_object_id": wbs_id,
                        "raw_json_redacted": json.dumps(
                            {
                                k: fields[k]
                                for k in ("OriginalBudget", "Status", "AnticipatedStartDate", "AnticipatedFinishDate")
                                if k in fields
                            },
                            sort_keys=True,
                        )
                        if any(k in fields for k in ("OriginalBudget", "Status"))
                        else None,
                    }
                    wbs_by_oid[wbs_id] = node
                    bundle.wbs_nodes.append(node)

            elif tag in _CALENDAR_TAGS:
                fields = _field_map(el)
                cal_id = fields.get("ObjectId") or fields.get("calendar_id")
                if cal_id:
                    bundle.calendars.append(
                        {
                            "calendar_id": cal_id,
                            "calendar_name": fields.get("Name"),
                            "calendar_type": fields.get("Type"),
                            "hours_per_day": fields.get("HoursPerDay") or fields.get("StandardWorkHours"),
                            "days_per_week": fields.get("DaysPerWeek"),
                            "is_default": 1 if _truthy(fields.get("IsDefault")) else 0,
                        }
                    )

            elif tag in _ACTIVITY_TAGS:
                fields = _field_map(el)
                nested_codes = _parse_activity_codes(el, code_types=code_types, code_values=code_values)
                row = _activity_row(fields, nested_codes=nested_codes, wbs_by_oid=wbs_by_oid)
                if row is None:
                    bundle.validation_findings.append(
                        {"code": "missing_activity_id", "message": "Activity row missing identifier"}
                    )
                else:
                    if row.get("cost_loaded_amount"):
                        bundle.cost_loaded_hints.append(
                            {
                                "activity_id": row["activity_id"],
                                "field": row.get("cost_loaded_source_type") or "cost",
                                "value": row["cost_loaded_amount"],
                            }
                        )
                    oid = fields.get("ObjectId")
                    if oid:
                        object_to_activity_id[oid] = row["activity_id"]
                    for code in nested_codes:
                        bundle.code_assignments.append(
                            {
                                "activity_id": row["activity_id"],
                                "code_type": code.get("code_type"),
                                "code_value": code.get("code_value"),
                                "code_description": code.get("code_description"),
                                "source_object_id": code.get("source_object_id"),
                            }
                        )
                    row.pop("nested_codes", None)
                    row["source_row_hash"] = _row_hash(row)
                    bundle.activities.append(row)
                el.clear()

            elif tag in _RELATIONSHIP_TAGS:
                fields = _field_map(el)
                pred = fields.get("PredecessorActivityObjectId") or fields.get("PredecessorActivityId")
                succ = fields.get("SuccessorActivityObjectId") or fields.get("SuccessorActivityId")
                if pred and succ:
                    raw_relationships.append(
                        {
                            "predecessor_activity_id": pred,
                            "successor_activity_id": succ,
                            "relationship_type": fields.get("Type") or "FS",
                            "lag_value": fields.get("Lag"),
                            "lag_unit": fields.get("LagUnit") or "hour",
                            "source_relationship_object_id": fields.get("ObjectId"),
                            "comments": fields.get("Comments"),
                        }
                    )
                el.clear()

            elif tag == "UDFValue":
                fields = _field_map(el)
                act_oid = fields.get("ActivityObjectId")
                act_id = object_to_activity_id.get(act_oid or "", act_oid)
                if act_id:
                    bundle.udf_values.append(
                        {
                            "activity_id": act_id,
                            "udf_type_name": fields.get("UDFTypeObjectId"),
                            "udf_data_type": fields.get("DataType"),
                            "udf_value": fields.get("Text") or fields.get("Value"),
                            "source_object_id": fields.get("ObjectId"),
                        }
                    )
                el.clear()

    except ET.ParseError as exc:
        raise ScheduleImportError(
            "schedule_parse_failed",
            message="invalid XML schedule file",
        ) from exc

    for raw in raw_relationships:
        pred = object_to_activity_id.get(raw["predecessor_activity_id"], raw["predecessor_activity_id"])
        succ = object_to_activity_id.get(raw["successor_activity_id"], raw["successor_activity_id"])
        rel = {
            "predecessor_activity_id": pred,
            "successor_activity_id": succ,
            "relationship_type": raw["relationship_type"],
            "lag_value": raw["lag_value"],
            "lag_unit": raw["lag_unit"],
            "source_relationship_object_id": raw.get("source_relationship_object_id"),
        }
        rel["source_row_hash"] = _row_hash(rel)
        bundle.relationships.append(rel)

    if not bundle.activities:
        bundle.validation_findings.append(
            {"code": "no_activities", "message": "No schedule activities detected in XML"}
        )

    apply_derived_float_to_activities(
        bundle.activities,
        options=bundle.schedule_options,
        calendars=bundle.calendars,
    )
    for act in bundle.activities:
        act["source_row_hash"] = _row_hash({k: act[k] for k in act if k != "source_row_hash"})

    return bundle