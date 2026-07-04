"""Sanitized SQLite DB posture collection for startup logs and admin status."""

from __future__ import annotations

import logging
import os
import sqlite3
import stat
from pathlib import Path
from typing import Any

from hb_assistant.config.db_storage_guard import classify_db_storage
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def schema_object_counts(db_path: str | Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        table_row = conn.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchone()
        view_row = conn.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type = 'view' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchone()
        table_count = int(table_row[0]) if table_row else 0
        view_count = int(view_row[0]) if view_row else 0
        return {
            "table_count": table_count,
            "view_count": view_count,
            "schema_object_count": table_count + view_count,
        }
    finally:
        conn.close()


def _pragma_value(conn: sqlite3.Connection, name: str) -> Any:
    try:
        row = conn.execute(f"PRAGMA {name}").fetchone()
        return row[0] if row else None
    except Exception:
        return None


def collect_db_posture(
    db_path: str | Path,
    *,
    background_worker_mode: str = "enabled",
    startup_migration_performed: bool = False,
) -> dict[str, Any]:
    path = Path(db_path)
    storage_class = classify_db_storage(path)
    posture: dict[str, Any] = {
        "resolved_db_path": str(path.resolve()) if path.exists() else str(path),
        "db_storage_class": storage_class,
        "schema_expected": LATEST_SCHEMA_VERSION,
        "background_worker_mode": background_worker_mode,
        "startup_migration_performed": startup_migration_performed,
        "process_uid": os.getuid(),
        "process_gid": os.getgid(),
    }

    if path.is_file():
        st = path.stat()
        posture.update(
            {
                "db_file_mode": stat.S_IMODE(st.st_mode),
                "db_file_uid": st.st_uid,
                "db_file_gid": st.st_gid,
                "db_file_size": st.st_size,
            }
        )
        wal_path = Path(f"{path}-wal")
        posture["wal_size"] = wal_path.stat().st_size if wal_path.is_file() else 0
        posture["schema_version"] = int(SQLiteMigrator(db_path=str(path)).current_version())
        posture["schema_ready"] = posture["schema_version"] >= LATEST_SCHEMA_VERSION
        posture.update(schema_object_counts(path))

        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            posture["journal_mode"] = _pragma_value(conn, "journal_mode")
            posture["busy_timeout"] = _pragma_value(conn, "busy_timeout")
            posture["foreign_keys"] = _pragma_value(conn, "foreign_keys")
            posture["wal_autocheckpoint"] = _pragma_value(conn, "wal_autocheckpoint")
        finally:
            conn.close()
    else:
        posture.update(
            {
                "schema_version": 0,
                "schema_ready": False,
                "journal_mode": None,
                "busy_timeout": None,
                "foreign_keys": None,
                "wal_autocheckpoint": None,
            }
        )

    return posture


def public_health_posture(
    db_path: str | Path,
    *,
    background_worker_mode: str = "enabled",
    startup_migration_performed: bool = False,
) -> dict[str, Any]:
    """PM-safe subset for ``/health`` — no filesystem paths or uid/gid/mode."""
    full = collect_db_posture(
        db_path,
        background_worker_mode=background_worker_mode,
        startup_migration_performed=startup_migration_performed,
    )
    return {
        "schema_ready": full.get("schema_ready", False),
        "schema_version": full.get("schema_version", 0),
        "db_storage_class": full.get("db_storage_class", "blocked"),
        "background_worker_mode": background_worker_mode,
        "startup_migration_performed": startup_migration_performed,
    }


def log_db_posture_at_startup(
    logger: logging.Logger,
    db_path: str | Path,
    *,
    background_worker_mode: str = "enabled",
    startup_migration_performed: bool = False,
) -> dict[str, Any]:
    posture = collect_db_posture(
        db_path,
        background_worker_mode=background_worker_mode,
        startup_migration_performed=startup_migration_performed,
    )
    logger.info("db_posture_at_startup %s", posture)
    return posture
