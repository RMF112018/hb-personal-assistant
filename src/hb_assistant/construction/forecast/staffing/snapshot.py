"""Per-run staffing snapshot persistence (Phase 6).

Captures the exact resolved staffing configuration used for a DB-native forecast run so historical
outputs stay reproducible after later config/template edits. Best-effort, called after a successful
persist; never blocks the forecast.
"""

from __future__ import annotations

import json
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from ._common import assert_schema, new_id, utc_now


def write_staffing_snapshot(
    db_path: str,
    *,
    project_key: str,
    request_id: str | None,
    output_id: str | None,
    staffing: dict[str, Any],
) -> str:
    """Write one snapshot header + one row per resolved config row. Returns the snapshot id."""
    now = utc_now()
    snapshot_id = new_id()
    effective = staffing.get("effective") or []
    assumptions = staffing.get("assumptions") or {}
    holiday_calendar_id = assumptions.get("holiday_calendar_id")
    with open_connection(db_path) as conn:
        assert_schema(conn)
        with transaction(conn):
            conn.execute(
                "INSERT INTO forecast_project_staffing_snapshots "
                "(staffing_snapshot_id, request_id, output_id, project_key, source_hash, "
                "template_versions_json, project_assumptions_json, holiday_calendar_id, "
                "validation_status, validation_errors_json, created_utc, raw_json) "
                "VALUES (?, ?, ?, ?, NULL, '[]', ?, ?, 'valid', '[]', ?, '{}')",
                (snapshot_id, request_id, output_id, project_key,
                 json.dumps({k: assumptions.get(k) for k in (
                     "hours_per_business_day", "business_days_per_week", "full_time_hours_per_week",
                     "holiday_calendar_id")}, sort_keys=True),
                 holiday_calendar_id, now),
            )
            for row in effective:
                conn.execute(
                    "INSERT INTO forecast_project_staffing_snapshot_rows "
                    "(snapshot_row_id, staffing_snapshot_id, staffing_config_id, template_id, "
                    "template_version_id, project_key, row_identity_key, role_title, person_name, "
                    "person_name_normalized, employment_type, cost_code, category, rate_unit, rate, "
                    "start_date, finish_date, created_utc, raw_json) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)",
                    (new_id(), snapshot_id, row.get("staffing_config_id"), row.get("template_id"),
                     project_key, row.get("staffing_config_id"), row.get("role_title"),
                     row.get("person_name"), row.get("person_name_normalized"),
                     row.get("employment_type"), row.get("cost_code"), row.get("rate_unit"),
                     row.get("lab_rate"), row.get("start_date"), row.get("finish_date"), now,
                     json.dumps(row, sort_keys=True, default=str)),
                )
    return snapshot_id
