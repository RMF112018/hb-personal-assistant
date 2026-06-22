"""CSV schedule parser with operator-defined column mapping."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any

from .schedule_file_parser import ParsedScheduleBundle, ScheduleImportError

PARSER_NAME = "schedule_csv_parser"
PARSER_VERSION = "1.0.0"

REQUIRED_ROLES = ("activity_id", "activity_name")


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def parse_csv_bytes(
    data: bytes,
    *,
    column_roles: dict[str, str] | None = None,
) -> ParsedScheduleBundle:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ScheduleImportError(
            "schedule_parse_failed",
            message="CSV file has no header row",
        )

    headers = [h.strip() for h in reader.fieldnames if h]
    bundle = ParsedScheduleBundle(
        schedule_id="csv-import",
        schedule_name="CSV Schedule Import",
    )

    if not column_roles:
        bundle.validation_findings.append(
            {"code": "column_mapping_required", "message": "Operator column mapping is required for CSV"}
        )
        return bundle

    role_to_header = {role: hdr for hdr, role in column_roles.items() if role}
    missing = [r for r in REQUIRED_ROLES if r not in role_to_header]
    if missing:
        raise ScheduleImportError(
            "schedule_parse_failed",
            message=f"CSV import requires mapped columns: {', '.join(missing)}",
        )

    for i, raw_row in enumerate(reader):
        row = {k.strip(): (v or "").strip() for k, v in raw_row.items() if k}
        act_id = row.get(role_to_header["activity_id"], "").strip()
        act_name = row.get(role_to_header["activity_name"], "").strip()
        if not act_id:
            bundle.validation_findings.append(
                {"code": "missing_activity_id", "message": f"Row {i + 2} missing activity ID"}
            )
            continue
        if not act_name:
            bundle.validation_findings.append(
                {"code": "missing_activity_name", "message": f"Row {i + 2} missing activity name"}
            )
            continue

        def _get(role: str, src: dict[str, str] = row) -> str | None:
            hdr = role_to_header.get(role)
            if not hdr:
                return None
            v = src.get(hdr, "").strip()
            return v or None

        activity = {
            "activity_id": act_id,
            "source_activity_object_id": act_id,
            "activity_name": act_name,
            "start_date": _get("start"),
            "finish_date": _get("finish"),
            "activity_status": _get("status"),
            "duration_original": _get("duration"),
            "duration_unit": _get("duration_unit") or "day",
            "wbs_code": _get("wbs"),
            "cost_code": _get("cost_code"),
        }
        if activity.get("cost_code"):
            bundle.cost_loaded_hints.append(
                {"activity_id": act_id, "field": "cost_code", "value": activity["cost_code"]}
            )
        activity["source_row_hash"] = _row_hash(activity)
        bundle.activities.append(activity)

    if not bundle.activities:
        bundle.validation_findings.append(
            {"code": "no_activities", "message": "No valid activities parsed from CSV"}
        )
    bundle.validation_findings.append(
        {"code": "headers_detected", "message": f"Detected {len(headers)} columns"}
    )
    return bundle


def detect_csv_headers(data: bytes) -> list[str]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    return [str(h).strip() for h in rows[0]]