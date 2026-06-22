"""V69 repair for schedule import parent/child FK drift (orphan schedule_file_imports_v66)."""

from __future__ import annotations

import re
import sqlite3
from typing import Iterable

from hb_assistant.store.schedule_tables import V62_STATEMENTS

SCHEDULE_CHILD_TABLES: tuple[str, ...] = (
    "procore_ep_schedule_activities",
    "procore_ep_schedule_relationships",
    "procore_ep_schedule_wbs_nodes",
    "procore_ep_schedule_calendars",
    "procore_ep_schedule_activity_code_assignments",
    "procore_ep_schedule_udf_values",
)

V69_IMPORT_SOURCE_PROJECT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_project_id", "TEXT"),
    ("source_project_name", "TEXT"),
    ("source_project_short_name", "TEXT"),
    ("source_project_metadata_json", "TEXT"),
)

_ORPHAN_PARENT_TABLE = "schedule_file_imports_v66"
_CANONICAL_PARENT_TABLE = "schedule_file_imports"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    try:
        return [(str(r[1]), str(r[2] or "TEXT")) for r in conn.execute(f"PRAGMA table_info({table})")]
    except sqlite3.OperationalError:
        return []


def _import_fk_parent_table(conn: sqlite3.Connection, table: str) -> str | None:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    except sqlite3.OperationalError:
        return None
    for row in rows:
        if str(row[3]) == "import_id":
            return str(row[2]).strip('"')
    return None


def verify_schedule_import_fk_targets(conn: sqlite3.Connection) -> list[str]:
    """Return drift descriptions (empty list means FK targets are canonical)."""
    issues: list[str] = []
    if _table_exists(conn, _ORPHAN_PARENT_TABLE):
        issues.append(f"orphan_parent_table:{_ORPHAN_PARENT_TABLE}")
    for table in SCHEDULE_CHILD_TABLES:
        if not _table_exists(conn, table):
            continue
        parent = _import_fk_parent_table(conn, table)
        if parent and parent != _CANONICAL_PARENT_TABLE:
            issues.append(f"{table}.import_id->{parent}")
    return issues


def _parse_v62_ddl() -> tuple[dict[str, str], dict[str, list[str]]]:
    creates: dict[str, str] = {}
    indexes: dict[str, list[str]] = {t: [] for t in SCHEDULE_CHILD_TABLES}
    for stmt in V62_STATEMENTS:
        text = stmt.strip()
        upper = text.upper()
        if upper.startswith("CREATE TABLE"):
            match = re.search(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", text, re.IGNORECASE)
            if match:
                creates[match.group(1)] = text
        elif upper.startswith("CREATE INDEX"):
            for table in SCHEDULE_CHILD_TABLES:
                if table in text:
                    indexes[table].append(text)
    return creates, indexes


def _merge_orphan_import_parents(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, _ORPHAN_PARENT_TABLE):
        return 0
    if not _table_exists(conn, _CANONICAL_PARENT_TABLE):
        return 0
    old_cols = [c for c, _ in _table_columns(conn, _ORPHAN_PARENT_TABLE)]
    new_cols = {c for c, _ in _table_columns(conn, _CANONICAL_PARENT_TABLE)}
    shared = [c for c in old_cols if c in new_cols]
    if not shared:
        return 0
    cols_sql = ", ".join(shared)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO {_CANONICAL_PARENT_TABLE} ({cols_sql}) "
        f"SELECT {cols_sql} FROM {_ORPHAN_PARENT_TABLE}"
    )
    return int(cur.rowcount)


def _add_missing_columns(
    conn: sqlite3.Connection, *, target: str, source: str
) -> None:
    target_cols = {c for c, _ in _table_columns(conn, target)}
    for col, col_type in _table_columns(conn, source):
        if col in target_cols or col == "id":
            continue
        conn.execute(f"ALTER TABLE {target} ADD COLUMN {col} {col_type}")


def _rebuild_child_table(
    conn: sqlite3.Connection,
    *,
    table: str,
    create_sql: str,
    index_sqls: Iterable[str],
) -> None:
    if not _table_exists(conn, table):
        return
    staging = f"{table}_fk_repair_old"
    conn.execute(f"ALTER TABLE {table} RENAME TO {staging}")
    conn.execute(create_sql)
    _add_missing_columns(conn, target=table, source=staging)
    shared = [
        c
        for c, _ in _table_columns(conn, staging)
        if c in {name for name, _ in _table_columns(conn, table)}
    ]
    if shared:
        cols_sql = ", ".join(shared)
        conn.execute(
            f"INSERT INTO {table} ({cols_sql}) SELECT {cols_sql} FROM {staging}"
        )
    conn.execute(f"DROP TABLE {staging}")
    for idx_sql in index_sqls:
        conn.execute(idx_sql)


def _repair_partial_commits(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, _CANONICAL_PARENT_TABLE):
        return 0
    cur = conn.execute(
        f"""
        UPDATE {_CANONICAL_PARENT_TABLE}
        SET import_status='failed', validation_status='persistence_incomplete'
        WHERE import_status='committed'
          AND NOT EXISTS (
            SELECT 1 FROM procore_ep_schedule_activities a
            WHERE a.import_id = {_CANONICAL_PARENT_TABLE}.import_id
          )
        """
    )
    return int(cur.rowcount)


def _add_v69_import_columns(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, _CANONICAL_PARENT_TABLE):
        return
    existing = {c for c, _ in _table_columns(conn, _CANONICAL_PARENT_TABLE)}
    for col_name, col_type in V69_IMPORT_SOURCE_PROJECT_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE {_CANONICAL_PARENT_TABLE} ADD COLUMN {col_name} {col_type}"
            )
    if _table_exists(conn, _ORPHAN_PARENT_TABLE):
        orphan_cols = {c for c, _ in _table_columns(conn, _ORPHAN_PARENT_TABLE)}
        for col_name, col_type in V69_IMPORT_SOURCE_PROJECT_COLUMNS:
            if col_name not in orphan_cols:
                conn.execute(
                    f"ALTER TABLE {_ORPHAN_PARENT_TABLE} ADD COLUMN {col_name} {col_type}"
                )


def reconcile_schedule_import_fk_drift(conn: sqlite3.Connection) -> dict[str, object]:
    """Repair orphan parent table / stale child FK targets; idempotent."""
    report: dict[str, object] = {
        "issues_before": verify_schedule_import_fk_targets(conn),
        "merged_orphan_imports": 0,
        "rebuilt_tables": [],
        "repaired_partial_commits": 0,
        "dropped_orphan_parent": False,
    }
    _add_v69_import_columns(conn)
    issues = verify_schedule_import_fk_targets(conn)
    if not issues:
        report["issues_after"] = []
        return report

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        report["merged_orphan_imports"] = _merge_orphan_import_parents(conn)
        creates, indexes = _parse_v62_ddl()
        for table in SCHEDULE_CHILD_TABLES:
            parent = _import_fk_parent_table(conn, table) if _table_exists(conn, table) else None
            if parent == _CANONICAL_PARENT_TABLE:
                continue
            create_sql = creates.get(table)
            if not create_sql or not _table_exists(conn, table):
                continue
            _rebuild_child_table(
                conn,
                table=table,
                create_sql=create_sql,
                index_sqls=indexes.get(table, []),
            )
            rebuilt = report["rebuilt_tables"]
            assert isinstance(rebuilt, list)
            rebuilt.append(table)

        from hb_assistant.store.migrator import SQLiteMigrator

        SQLiteMigrator._reconcile_v65_schedule_float_columns(conn)
        SQLiteMigrator._reconcile_v67_schedule_critical_path_columns(conn)

        if _table_exists(conn, _ORPHAN_PARENT_TABLE):
            conn.execute(f"DROP TABLE {_ORPHAN_PARENT_TABLE}")
            report["dropped_orphan_parent"] = True

        report["repaired_partial_commits"] = _repair_partial_commits(conn)
    finally:
        conn.execute("PRAGMA foreign_keys=ON")

    report["issues_after"] = verify_schedule_import_fk_targets(conn)
    return report