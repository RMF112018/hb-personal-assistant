"""Physical-schema verification for V65 schedule derived finish-float columns."""

from __future__ import annotations

import sqlite3

from hb_assistant.store.schedule_float_tables import (
    METRIC_STATUS_CHECK_VALUES,
    V65_ACTIVITY_ALTER_COLUMNS,
    V65_IMPORT_ALTER_COLUMNS,
)

V65_DERIVED_METRIC_STATUSES: tuple[str, ...] = (
    "measured_from_derived_finish_float",
    "partially_measurable_critical_float_available",
    "not_measurable_missing_longest_path_data",
    "not_measurable_requires_recalculation",
)


class SchemaReconcileError(RuntimeError):
    """Raised when a reconcile pass leaves required physical schema incomplete."""


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.OperationalError:
        return set()


def verify_v65_schedule_float_schema(conn: sqlite3.Connection) -> list[str]:
    """Return missing V65 column names (empty list means physical schema is ready)."""
    missing: list[str] = []
    import_cols = _table_columns(conn, "schedule_file_imports")
    activity_cols = _table_columns(conn, "procore_ep_schedule_activities")
    if not import_cols and not activity_cols:
        return []
    for col in V65_IMPORT_ALTER_COLUMNS:
        if import_cols and col not in import_cols:
            missing.append(f"schedule_file_imports.{col}")
    for col in V65_ACTIVITY_ALTER_COLUMNS:
        if activity_cols and col not in activity_cols:
            missing.append(f"procore_ep_schedule_activities.{col}")
    return missing


def verify_v80_schedule_package_equivalence_schema(conn: sqlite3.Connection) -> list[str]:
    """Return missing V80 package-equivalence insert columns."""
    from hb_assistant.store.schedule_import_health_tables import (
        V80_PACKAGE_EQUIVALENCE_FACT_INSERT_COLUMNS,
    )

    columns = _table_columns(conn, "schedule_package_equivalence_facts")
    if not columns:
        return []
    return [
        f"schedule_package_equivalence_facts.{column}"
        for column in V80_PACKAGE_EQUIVALENCE_FACT_INSERT_COLUMNS
        if column not in columns
    ]


def verify_v65_metric_status_check(conn: sqlite3.Connection) -> bool:
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return False
    ddl = str(row[0])
    return all(status in ddl for status in V65_DERIVED_METRIC_STATUSES)


def schedule_v65_physical_report(conn: sqlite3.Connection) -> dict[str, object]:
    missing = verify_v65_schedule_float_schema(conn)
    metric_check_ok = verify_v65_metric_status_check(conn)
    return {
        "schedule_v65_physical_ready": not missing and metric_check_ok,
        "schedule_v65_missing_columns": missing,
        "schedule_v65_metric_status_check_ready": metric_check_ok,
    }


def assert_v65_schedule_float_schema(conn: sqlite3.Connection) -> None:
    missing = verify_v65_schedule_float_schema(conn)
    if missing:
        raise SchemaReconcileError(
            "V65 schedule float columns still missing after reconcile: " + ", ".join(missing)
        )
    if not verify_v65_metric_status_check(conn):
        raise SchemaReconcileError(
            "schedule_quality_metric_results CHECK missing V65 derived-float statuses"
        )


def verify_schedule_import_fk_targets(conn: sqlite3.Connection) -> list[str]:
    from hb_assistant.store.schedule_import_fk_repair import (
        verify_schedule_import_fk_targets as _verify_fk,
    )

    return _verify_fk(conn)


def assert_schedule_import_fk_targets(conn: sqlite3.Connection) -> None:
    issues = verify_schedule_import_fk_targets(conn)
    if issues:
        raise SchemaReconcileError(
            "schedule import FK drift still present after reconcile: " + ", ".join(issues)
        )
