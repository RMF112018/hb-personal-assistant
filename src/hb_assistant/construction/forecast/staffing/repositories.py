"""Class-based repositories over the V76 Project Staffing tables (Phase 2a).

Each repository owns its connection via ``open_connection`` + ``transaction`` (from
``store/connection.py``) and exposes redaction-safe reads: ``raw_json`` is persisted where the
schema defines it but is **never** selected into a returned dict. Soft-deactivate (``active_status``
+ ``deactivated_utc``) replaces hard deletes. Ids are uuid12; ``created_utc`` is immutable,
``updated_utc`` refreshes on every write.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from ._common import assert_schema, new_id, upsert, utc_now


def normalize_name(value: str | None) -> str | None:
    """Lowercase + whitespace-collapse an operator-entered person name (None/blank -> None)."""
    if value is None:
        return None
    norm = " ".join(value.split()).lower()
    return norm or None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Holiday calendar (read-only; seeded by the V76 migration)
# ---------------------------------------------------------------------------

_CAL_COLS = (
    "holiday_calendar_id, calendar_key, calendar_name, description, active_status, "
    "created_utc, updated_utc"
)
_CAL_DATE_COLS = (
    "holiday_date_id, holiday_calendar_id, calendar_year, holiday_key, holiday_name, "
    "holiday_date, observed_date, duration_type, closed_from_time, closed_until_time, "
    "staffing_hours_excluded, notes"
)


class HolidayCalendarRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def list_calendars(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            sql = f"SELECT {_CAL_COLS} FROM staffing_holiday_calendars"
            params: tuple[Any, ...] = ()
            if active_only:
                sql += " WHERE active_status = 'active'"
            sql += " ORDER BY calendar_key"
            return _rows(conn, sql, params)

    def get_calendar(self, calendar_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return _one(
                conn,
                f"SELECT {_CAL_COLS} FROM staffing_holiday_calendars WHERE holiday_calendar_id = ?",
                (calendar_id,),
            )

    def calendar_ids(self) -> set[str]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return {
                r[0]
                for r in conn.execute("SELECT holiday_calendar_id FROM staffing_holiday_calendars")
            }

    def get_dates(
        self, calendar_id: str, *, year_range: tuple[int, int] | None = None
    ) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            sql = (
                f"SELECT {_CAL_DATE_COLS} FROM staffing_holiday_calendar_dates "
                "WHERE holiday_calendar_id = ?"
            )
            params: list[Any] = [calendar_id]
            if year_range is not None:
                sql += " AND calendar_year BETWEEN ? AND ?"
                params.extend(year_range)
            sql += " ORDER BY observed_date, holiday_key"
            return _rows(conn, sql, tuple(params))


# ---------------------------------------------------------------------------
# Project staffing assumptions (one row per project; defaults when absent)
# ---------------------------------------------------------------------------

_ASSUMPTION_DEFAULTS = {
    "hours_per_business_day": "8.00",
    "business_days_per_week": "5.00",
    "full_time_hours_per_week": "40.00",
    "holiday_calendar_id": None,
}
_ASSUMPTION_COLS = (
    "project_key, hours_per_business_day, business_days_per_week, full_time_hours_per_week, "
    "holiday_calendar_id, created_utc, updated_utc"
)
_ASSUMPTION_FIELDS = (
    "hours_per_business_day",
    "business_days_per_week",
    "full_time_hours_per_week",
    "holiday_calendar_id",
)


class StaffingAssumptionsRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def get(self, project_key: str) -> dict[str, Any]:
        """Return the stored assumptions, or the project-level defaults (``persisted=False``)."""
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            row = _one(
                conn,
                f"SELECT {_ASSUMPTION_COLS} FROM forecast_project_staffing_assumptions "
                "WHERE project_key = ?",
                (project_key,),
            )
        if row is None:
            return {
                "project_key": project_key,
                **_ASSUMPTION_DEFAULTS,
                "created_utc": None,
                "updated_utc": None,
                "persisted": False,
            }
        row["persisted"] = True
        return row

    def upsert(self, project_key: str, **fields: Any) -> dict[str, Any]:
        now = utc_now()
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            current = _one(
                conn,
                f"SELECT {_ASSUMPTION_COLS} FROM forecast_project_staffing_assumptions "
                "WHERE project_key = ?",
                (project_key,),
            )
            base = {k: _ASSUMPTION_DEFAULTS[k] for k in _ASSUMPTION_FIELDS}
            if current is not None:
                base.update({k: current[k] for k in _ASSUMPTION_FIELDS})
            for key, value in fields.items():
                if key in _ASSUMPTION_FIELDS:
                    base[key] = value
            values = {
                "project_key": project_key,
                **base,
                "created_utc": now,
                "updated_utc": now,
                "raw_json": "{}",
            }
            with transaction(conn):
                upsert(conn, "forecast_project_staffing_assumptions", values, ("project_key",))
        return self.get(project_key)


# ---------------------------------------------------------------------------
# Project staffing config rows
# ---------------------------------------------------------------------------

_CONFIG_COLS = (
    "staffing_config_id, project_key, template_id, role_title, person_name, "
    "person_name_normalized, employment_type, cost_code, cost_code_description, rate_unit, "
    "lab_rate, lbn_rate, mat_rate, start_date, finish_date, active_status, override_fields_json, "
    "validation_status, validation_errors_json, created_by_role, updated_by_role, created_utc, "
    "updated_utc, deactivated_utc"
)
_CONFIG_WRITABLE = (
    "template_id",
    "role_title",
    "person_name",
    "employment_type",
    "cost_code",
    "cost_code_description",
    "rate_unit",
    "lab_rate",
    "lbn_rate",
    "mat_rate",
    "start_date",
    "finish_date",
)
_JSON_LIST_FIELDS = ("override_fields_json", "validation_errors_json")


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    for field in _JSON_LIST_FIELDS:
        if field in row and isinstance(row[field], str):
            try:
                row[field] = json.loads(row[field])
            except (TypeError, ValueError):
                row[field] = []
    return row


class StaffingConfigRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def create(self, row: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        config_id = new_id()
        override_fields = row.get("override_fields", [])
        values = {
            "staffing_config_id": config_id,
            "project_key": row["project_key"],
            "template_id": row.get("template_id"),
            "role_title": row.get("role_title"),
            "person_name": row.get("person_name"),
            "person_name_normalized": normalize_name(row.get("person_name")),
            "employment_type": row.get("employment_type"),
            "cost_code": row.get("cost_code"),
            "cost_code_description": row.get("cost_code_description"),
            "rate_unit": row.get("rate_unit"),
            "lab_rate": row.get("lab_rate"),
            "lbn_rate": row.get("lbn_rate"),
            "mat_rate": row.get("mat_rate"),
            "start_date": row.get("start_date"),
            "finish_date": row.get("finish_date"),
            "active_status": "active",
            "override_fields_json": json.dumps(list(override_fields), sort_keys=True),
            "validation_status": row.get("validation_status", "valid"),
            "validation_errors_json": json.dumps(row.get("validation_errors", [])),
            "created_by_role": row.get("created_by_role"),
            "updated_by_role": row.get("created_by_role"),
            "created_utc": now,
            "updated_utc": now,
            "deactivated_utc": None,
            "raw_json": "{}",
        }
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                upsert(conn, "forecast_project_staffing_config", values, ("staffing_config_id",))
        got = self.get(config_id)
        assert got is not None
        return got

    def get(self, config_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            row = _one(
                conn,
                f"SELECT {_CONFIG_COLS} FROM forecast_project_staffing_config "
                "WHERE staffing_config_id = ?",
                (config_id,),
            )
        return _decode(row) if row is not None else None

    def list(self, project_key: str, *, active_only: bool = True) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            sql = (
                f"SELECT {_CONFIG_COLS} FROM forecast_project_staffing_config WHERE project_key = ?"
            )
            params: list[Any] = [project_key]
            if active_only:
                sql += " AND active_status = 'active'"
            sql += " ORDER BY created_utc, staffing_config_id"
            return [_decode(r) for r in _rows(conn, sql, tuple(params))]

    def patch(
        self, config_id: str, fields: dict[str, Any], *, updated_by_role: str | None = None
    ) -> dict[str, Any] | None:
        sets: dict[str, Any] = {k: v for k, v in fields.items() if k in _CONFIG_WRITABLE}
        if "person_name" in sets:
            sets["person_name_normalized"] = normalize_name(sets["person_name"])
        if "override_fields" in fields:
            sets["override_fields_json"] = json.dumps(
                list(fields["override_fields"]), sort_keys=True
            )
        sets["updated_utc"] = utc_now()
        if updated_by_role is not None:
            sets["updated_by_role"] = updated_by_role
        assignments = ", ".join(f"{c} = ?" for c in sets)
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    f"UPDATE forecast_project_staffing_config SET {assignments} "
                    "WHERE staffing_config_id = ?",
                    (*sets.values(), config_id),
                )
        return self.get(config_id)

    def set_validation(
        self, config_id: str, *, status: str, errors: list[Any]
    ) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    "UPDATE forecast_project_staffing_config SET validation_status = ?, "
                    "validation_errors_json = ?, updated_utc = ? WHERE staffing_config_id = ?",
                    (status, json.dumps(errors), utc_now(), config_id),
                )
        return self.get(config_id)

    def deactivate(self, config_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    "UPDATE forecast_project_staffing_config SET active_status = 'deactivated', "
                    "deactivated_utc = ?, updated_utc = ? WHERE staffing_config_id = ?",
                    (now, now, config_id),
                )
        return self.get(config_id)


# ---------------------------------------------------------------------------
# Absence overrides
# ---------------------------------------------------------------------------

_ABSENCE_COLS = (
    "absence_override_id, project_key, staffing_config_id, person_name, person_name_normalized, "
    "start_date, finish_date, absence_hours, notes, active_status, created_utc, updated_utc, "
    "deactivated_utc"
)
_ABSENCE_WRITABLE = (
    "staffing_config_id",
    "person_name",
    "start_date",
    "finish_date",
    "absence_hours",
    "notes",
)


class AbsenceOverrideRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def create(self, row: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        absence_id = new_id()
        values = {
            "absence_override_id": absence_id,
            "project_key": row["project_key"],
            "staffing_config_id": row.get("staffing_config_id"),
            "person_name": row.get("person_name"),
            "person_name_normalized": normalize_name(row.get("person_name")),
            "start_date": row.get("start_date"),
            "finish_date": row.get("finish_date"),
            "absence_hours": row.get("absence_hours"),
            "notes": row.get("notes"),
            "active_status": "active",
            "created_utc": now,
            "updated_utc": now,
            "deactivated_utc": None,
            "raw_json": "{}",
        }
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                upsert(
                    conn,
                    "forecast_project_staffing_absence_overrides",
                    values,
                    ("absence_override_id",),
                )
        got = self.get(absence_id)
        assert got is not None
        return got

    def get(self, absence_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return _one(
                conn,
                f"SELECT {_ABSENCE_COLS} FROM forecast_project_staffing_absence_overrides "
                "WHERE absence_override_id = ?",
                (absence_id,),
            )

    def list(self, project_key: str, *, active_only: bool = True) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            sql = (
                f"SELECT {_ABSENCE_COLS} FROM forecast_project_staffing_absence_overrides "
                "WHERE project_key = ?"
            )
            if active_only:
                sql += " AND active_status = 'active'"
            sql += " ORDER BY start_date, absence_override_id"
            return _rows(conn, sql, (project_key,))

    def patch(self, absence_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        sets: dict[str, Any] = {k: v for k, v in fields.items() if k in _ABSENCE_WRITABLE}
        if "person_name" in sets:
            sets["person_name_normalized"] = normalize_name(sets["person_name"])
        sets["updated_utc"] = utc_now()
        assignments = ", ".join(f"{c} = ?" for c in sets)
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    f"UPDATE forecast_project_staffing_absence_overrides SET {assignments} "
                    "WHERE absence_override_id = ?",
                    (*sets.values(), absence_id),
                )
        return self.get(absence_id)

    def deactivate(self, absence_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    "UPDATE forecast_project_staffing_absence_overrides "
                    "SET active_status = 'deactivated', deactivated_utc = ?, updated_utc = ? "
                    "WHERE absence_override_id = ?",
                    (now, now, absence_id),
                )
        return self.get(absence_id)


# ---------------------------------------------------------------------------
# Global staffing templates + versions
# ---------------------------------------------------------------------------

_TEMPLATE_COLS = (
    "template_id, template_key, template_name, active_status, current_version_id, "
    "created_by_role, created_utc, updated_utc, deactivated_utc"
)
_VERSION_COLS = (
    "template_version_id, template_id, version_number, cost_code, cost_code_description, "
    "default_role_title, default_employment_type, default_rate_unit, default_lab_rate, "
    "default_lbn_rate, default_mat_rate, created_by_role, created_utc"
)
_VERSION_DEFAULT_FIELDS = (
    "cost_code",
    "cost_code_description",
    "default_role_title",
    "default_employment_type",
    "default_rate_unit",
    "default_lab_rate",
    "default_lbn_rate",
    "default_mat_rate",
)


class StaffingTemplateRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def create_template(
        self, *, template_key: str, template_name: str, created_by_role: str | None = None
    ) -> dict[str, Any]:
        now = utc_now()
        template_id = new_id()
        values = {
            "template_id": template_id,
            "template_key": template_key,
            "template_name": template_name,
            "active_status": "active",
            "current_version_id": None,
            "created_by_role": created_by_role,
            "created_utc": now,
            "updated_utc": now,
            "deactivated_utc": None,
        }
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                upsert(conn, "forecast_staffing_templates", values, ("template_id",))
        got = self.get(template_id)
        assert got is not None
        return got

    def add_version(
        self, template_id: str, *, created_by_role: str | None = None, **defaults: Any
    ) -> dict[str, Any]:
        if "cost_code" not in defaults or defaults.get("cost_code") in (None, ""):
            raise ValueError("template version requires cost_code")
        now = utc_now()
        version_id = new_id()
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                row = conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) FROM "
                    "forecast_staffing_template_versions WHERE template_id = ?",
                    (template_id,),
                ).fetchone()
                next_number = int(row[0]) + 1
                values = {
                    "template_version_id": version_id,
                    "template_id": template_id,
                    "version_number": next_number,
                    **{k: defaults.get(k) for k in _VERSION_DEFAULT_FIELDS},
                    "created_by_role": created_by_role,
                    "created_utc": now,
                    "raw_json": "{}",
                }
                upsert(
                    conn,
                    "forecast_staffing_template_versions",
                    values,
                    ("template_version_id",),
                )
                conn.execute(
                    "UPDATE forecast_staffing_templates SET current_version_id = ?, "
                    "updated_utc = ? WHERE template_id = ?",
                    (version_id, now, template_id),
                )
        got = self.get_version(version_id)
        assert got is not None
        return got

    def get(self, template_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return _one(
                conn,
                f"SELECT {_TEMPLATE_COLS} FROM forecast_staffing_templates WHERE template_id = ?",
                (template_id,),
            )

    def list(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            sql = f"SELECT {_TEMPLATE_COLS} FROM forecast_staffing_templates"
            if active_only:
                sql += " WHERE active_status = 'active'"
            sql += " ORDER BY template_key"
            return _rows(conn, sql, ())

    def list_versions(self, template_id: str) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return _rows(
                conn,
                f"SELECT {_VERSION_COLS} FROM forecast_staffing_template_versions "
                "WHERE template_id = ? ORDER BY version_number",
                (template_id,),
            )

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return _one(
                conn,
                f"SELECT {_VERSION_COLS} FROM forecast_staffing_template_versions "
                "WHERE template_version_id = ?",
                (version_id,),
            )

    def get_current_version(self, template_id: str) -> dict[str, Any] | None:
        template = self.get(template_id)
        if template is None or template.get("current_version_id") is None:
            return None
        return self.get_version(template["current_version_id"])

    def deactivate(self, template_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    "UPDATE forecast_staffing_templates SET active_status = 'deactivated', "
                    "deactivated_utc = ?, updated_utc = ? WHERE template_id = ?",
                    (now, now, template_id),
                )
        return self.get(template_id)


# ---------------------------------------------------------------------------
# Forecast-only staffing cost codes
# ---------------------------------------------------------------------------

_COST_CODE_COLS = (
    "staffing_cost_code_id, project_key, template_id, cost_code, cost_code_description, "
    "source_scope, active_status, created_utc, updated_utc"
)


class StaffingCostCodeRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def create(self, row: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        cost_code_id = new_id()
        values = {
            "staffing_cost_code_id": cost_code_id,
            "project_key": row.get("project_key"),
            "template_id": row.get("template_id"),
            "cost_code": row["cost_code"],
            "cost_code_description": row.get("cost_code_description"),
            "source_scope": row.get("source_scope", "project_staffing"),
            "active_status": "active",
            "created_utc": now,
            "updated_utc": now,
            "raw_json": "{}",
        }
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                upsert(conn, "forecast_staffing_cost_codes", values, ("staffing_cost_code_id",))
        got = self.get(cost_code_id)
        assert got is not None
        return got

    def get(self, cost_code_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            return _one(
                conn,
                f"SELECT {_COST_CODE_COLS} FROM forecast_staffing_cost_codes "
                "WHERE staffing_cost_code_id = ?",
                (cost_code_id,),
            )

    def list(
        self, *, project_key: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            sql = f"SELECT {_COST_CODE_COLS} FROM forecast_staffing_cost_codes"
            clauses: list[str] = []
            params: list[Any] = []
            if project_key is not None:
                clauses.append("project_key = ?")
                params.append(project_key)
            if active_only:
                clauses.append("active_status = 'active'")
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY cost_code, staffing_cost_code_id"
            return _rows(conn, sql, tuple(params))

    def deactivate(self, cost_code_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with open_connection(self._db_path) as conn:
            assert_schema(conn)
            with transaction(conn):
                conn.execute(
                    "UPDATE forecast_staffing_cost_codes SET active_status = 'deactivated', "
                    "updated_utc = ? WHERE staffing_cost_code_id = ?",
                    (now, cost_code_id),
                )
        return self.get(cost_code_id)
