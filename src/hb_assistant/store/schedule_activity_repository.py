"""Repository for canonical schedule activity and related subgraph tables."""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .connection import get_connection, open_connection, transaction

_ACTIVITY_COLS = (
    "project_key",
    "procore_project_id",
    "schedule_table_id",
    "schedule_id",
    "schedule_version_key",
    "import_id",
    "source_type",
    "source_format",
    "activity_id",
    "source_activity_object_id",
    "parent_activity_id",
    "wbs_id",
    "wbs_code",
    "wbs_path",
    "activity_name",
    "activity_type",
    "activity_status",
    "planned_start",
    "planned_finish",
    "start_date",
    "finish_date",
    "early_start",
    "early_finish",
    "late_start",
    "late_finish",
    "actual_start",
    "actual_finish",
    "remaining_start",
    "remaining_finish",
    "remaining_early_start",
    "remaining_early_finish",
    "remaining_late_start",
    "remaining_late_finish",
    "derived_total_float_hours",
    "derived_total_float_days",
    "derived_float_basis",
    "derived_is_critical_by_float_threshold",
    "explicit_total_float_hours",
    "explicit_total_float_days",
    "explicit_free_float_hours",
    "explicit_free_float_days",
    "float_source",
    "source_critical_flag",
    "source_driving_path_flag",
    "source_longest_path_flag",
    "float_path",
    "float_path_order",
    "critical_path_number",
    "critical_path_source",
    "target_start",
    "target_finish",
    "target_duration",
    "baseline_start",
    "baseline_finish",
    "baseline_duration",
    "duration_original",
    "duration_remaining",
    "duration_actual",
    "duration_unit",
    "percent_complete",
    "physical_percent_complete",
    "duration_percent_complete",
    "calendar_id",
    "calendar_name",
    "constraint_type",
    "constraint_date",
    "deadline_date",
    "deadline_variance",
    "total_float",
    "free_float",
    "is_critical",
    "is_longest_path",
    "is_milestone",
    "assigned_company_id",
    "assigned_company_name_redacted",
    "crew_size",
    "notes_summary_hash",
    "cost_account_id",
    "cost_code",
    "cost_code_raw",
    "cost_loaded_amount",
    "cost_loaded_quantity",
    "cost_loaded_unit_cost",
    "cost_loaded_source_type",
    "cost_loaded_confidence",
    "raw_json_redacted",
    "raw_source_fields_json",
    "source_row_hash",
)


class ScheduleActivityRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def upsert_schedule_version_row(
        self, row: dict[str, Any], *, conn: sqlite3.Connection | None = None
    ) -> str:
        """Insert or update a synthetic procore_ep_schedules row; return record_key."""
        record_key = row["record_key"]
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        update_cols = [c for c in cols if c != "record_key"]
        update_clause = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
        sql = f"""
            INSERT INTO procore_ep_schedules ({names})
            VALUES ({placeholders})
            ON CONFLICT(record_key) DO UPDATE SET {update_clause}
        """
        params = tuple(row[c] for c in cols)
        if conn is not None:
            conn.execute(sql, params)
        else:
            with open_connection(self._db_path) as active:
                with transaction(active):
                    active.execute(sql, params)
        return record_key

    def find_schedule_table_id(
        self, *, project_key: str, schedule_id: str, endpoint_key: str = "schedules"
    ) -> str | None:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT record_key FROM procore_ep_schedules
                WHERE project_key=? AND record_id=? AND endpoint_key=?
                ORDER BY is_current DESC, updated_utc DESC LIMIT 1
                """,
                (project_key, schedule_id, endpoint_key),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None

    def bulk_upsert_activities(
        self, rows: Iterable[dict[str, Any]], *, conn: sqlite3.Connection | None = None
    ) -> int:
        items = list(rows)
        if not items:
            return 0
        cols = [c for c in _ACTIVITY_COLS if c in items[0]]
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        update_clause = ", ".join(
            f"{c}=excluded.{c}" for c in cols if c not in ("schedule_version_key", "activity_id", "import_id")
        )
        sql = f"""
            INSERT INTO procore_ep_schedule_activities ({names})
            VALUES ({placeholders})
            ON CONFLICT(schedule_version_key, activity_id, import_id)
            DO UPDATE SET {update_clause}, updated_at=CURRENT_TIMESTAMP
        """
        batch = [tuple(r.get(c) for c in cols) for r in items]
        if conn is not None:
            conn.executemany(sql, batch)
        else:
            with open_connection(self._db_path) as active:
                with transaction(active):
                    active.executemany(sql, batch)
        return len(items)

    def bulk_insert_table(
        self,
        table: str,
        rows: Iterable[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        items = list(rows)
        if not items:
            return 0
        cols = list(items[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        insert_sql = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
        batch = [tuple(r[c] for c in cols) for r in items]
        if conn is not None:
            conn.executemany(insert_sql, batch)
        else:
            with open_connection(self._db_path) as active:
                with transaction(active):
                    active.executemany(insert_sql, batch)
        return len(items)

    def delete_version_subgraph(
        self,
        *,
        schedule_version_key: str,
        import_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        tables = (
            "procore_ep_schedule_udf_values",
            "procore_ep_schedule_activity_code_assignments",
            "procore_ep_schedule_calendars",
            "procore_ep_schedule_wbs_nodes",
            "procore_ep_schedule_relationships",
            "procore_ep_schedule_activities",
        )
        if conn is not None:
            for table in tables:
                conn.execute(
                    f"DELETE FROM {table} WHERE schedule_version_key=? AND import_id=?",
                    (schedule_version_key, import_id),
                )
            return
        with open_connection(self._db_path) as active:
            with transaction(active):
                for table in tables:
                    active.execute(
                        f"DELETE FROM {table} WHERE schedule_version_key=? AND import_id=?",
                        (schedule_version_key, import_id),
                    )

    def list_versions(self, project_key: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as conn:
            sql = """
                SELECT i.import_id, i.project_key, i.schedule_version_key, i.source_type,
                       i.source_format, i.import_status, i.activity_count, i.relationship_count,
                       i.cost_loaded_status, i.created_at, i.source_filename_redacted,
                       COUNT(DISTINCT a.activity_id) AS activity_count_live,
                       COUNT(DISTINCT r.id) AS relationship_count_live
                FROM schedule_file_imports i
                LEFT JOIN procore_ep_schedule_activities a
                  ON a.import_id = i.import_id
                LEFT JOIN procore_ep_schedule_relationships r
                  ON r.import_id = i.import_id
                WHERE i.import_status='committed'
            """
            params: tuple[Any, ...] = ()
            if project_key:
                sql += " AND i.project_key=?"
                params = (project_key,)
            sql += " GROUP BY i.import_id ORDER BY i.created_at DESC"
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_version_summary(self, schedule_version_key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM schedule_file_imports
                WHERE schedule_version_key=? AND import_status='committed'
                ORDER BY created_at DESC LIMIT 1
                """,
                (schedule_version_key,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_activities(
        self, schedule_version_key: str, *, limit: int = 500, offset: int = 0
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT activity_id, activity_name, wbs_code, wbs_path, schedule_table_id,
                       planned_start, planned_finish, start_date, finish_date,
                       actual_start, actual_finish, remaining_start, remaining_finish,
                       remaining_early_start, remaining_early_finish,
                       remaining_late_start, remaining_late_finish,
                       duration_original, duration_remaining, duration_actual, duration_unit,
                       activity_status, activity_type,
                       calendar_id, constraint_type, is_critical, is_milestone, is_longest_path,
                       total_float, derived_total_float_hours, derived_total_float_days,
                       derived_float_basis, derived_is_critical_by_float_threshold,
                       explicit_total_float_hours, explicit_total_float_days,
                       explicit_free_float_hours, explicit_free_float_days,
                       float_source, source_critical_flag, source_driving_path_flag,
                       source_longest_path_flag, critical_path_source,
                       cost_code, percent_complete, physical_percent_complete,
                       duration_percent_complete, cost_loaded_amount, cost_loaded_source_type,
                       target_start, target_finish, baseline_start, baseline_finish,
                       raw_source_fields_json
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                ORDER BY activity_id
                LIMIT ? OFFSET ?
                """,
                (schedule_version_key, limit, offset),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_relationships(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT id AS relationship_row_id, source_relationship_object_id,
                       predecessor_activity_id, successor_activity_id,
                       relationship_type, lag_value, lag_unit
                FROM procore_ep_schedule_relationships
                WHERE schedule_version_key=?
                """,
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_wbs_nodes(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT wbs_id, parent_wbs_id, wbs_code, wbs_name, wbs_path, sequence_order
                FROM procore_ep_schedule_wbs_nodes
                WHERE schedule_version_key=?
                ORDER BY wbs_id
                """,
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_calendars(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT calendar_id, calendar_name, calendar_type, hours_per_day,
                       days_per_week, is_default
                FROM procore_ep_schedule_calendars
                WHERE schedule_version_key=?
                ORDER BY calendar_id
                """,
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_activity_codes(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT activity_id, code_type, code_value, code_description
                FROM procore_ep_schedule_activity_code_assignments
                WHERE schedule_version_key=?
                ORDER BY activity_id, code_type, code_value
                """,
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_udf_values(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT activity_id, udf_type_name, udf_data_type, udf_value
                FROM procore_ep_schedule_udf_values
                WHERE schedule_version_key=?
                ORDER BY activity_id, udf_type_name
                """,
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_projects_with_schedules(self) -> list[str]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT DISTINCT project_key FROM schedule_file_imports WHERE import_status='committed'"
            )
            return [str(r[0]) for r in cur.fetchall()]

    def count_activities(self, schedule_version_key: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                (schedule_version_key,),
            )
            return int(cur.fetchone()[0])

    def count_relationships(self, schedule_version_key: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?",
                (schedule_version_key,),
            )
            return int(cur.fetchone()[0])
