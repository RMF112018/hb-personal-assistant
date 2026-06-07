"""SQLite connection management with required PRAGMAs and transaction helper.

Per 07 spec: foreign_keys=ON, journal_mode=WAL, busy_timeout.
All access goes through get_connection() + transaction() context.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from hb_assistant.config.path_policy import PathPolicy

from .errors import StoreReadinessError


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite DB and apply required PRAGMAs.

    Caller must ensure directories via PathPolicy.ensure_dirs() before first use.
    """
    pp = PathPolicy()
    path = Path(db_path) if db_path is not None else pp.get_db_path()

    if db_path is None:
        # Default (ambient) DB: full app-support dir + readiness checks.
        pp.ensure_dirs(create_sensitive=False)  # db/ is 755, non-sensitive
        ready = pp.ensure_db_ready(return_report=True)
    else:
        # Explicit db_path (e.g. an isolated dev DB): NEVER touch the ambient/default DB.
        # Ensure only the supplied path's own directory and check it directly.
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        ready = {
            "ok": parent.exists() and parent.is_dir() and os.access(parent, os.W_OK),
            "status": "ok",
            "db_path": str(path),
            "db_parent": str(parent),
            "checks": {
                "app_support_exists": True,
                "db_parent_exists": parent.exists(),
                "db_parent_is_dir": parent.is_dir() if parent.exists() else False,
                "db_parent_writable": os.access(parent, os.W_OK) if parent.exists() else False,
                "sqlite_openable": False,
                "wal_mode": None,
            },
            "repair_guidance": [
                f'mkdir -p "{parent}"',
                f'chmod u+rwx "{parent}"',
            ],
            "error": None,
        }
        if not parent.exists():
            ready["status"] = "blocked_db_unavailable"
            ready["error"] = "db_parent_missing"
        elif not parent.is_dir():
            ready["status"] = "blocked_db_unavailable"
            ready["error"] = "db_parent_not_directory"
        elif not os.access(parent, os.W_OK):
            ready["status"] = "blocked_db_unavailable"
            ready["error"] = "db_parent_not_writable"

    if not ready.get("ok", False):
        raise StoreReadinessError(
            status="blocked_db_unavailable",
            message=f"Database unavailable at {path}",
            db_path=str(path),
            report=ready,
        )

    try:
        conn = sqlite3.connect(str(path), timeout=30)
    except sqlite3.OperationalError as e:
        report = ready if isinstance(ready, dict) else {}
        report["ok"] = False
        report["status"] = "blocked_db_unavailable"
        report["error"] = f"sqlite_operational_error: {e}"
        raise StoreReadinessError(
            status="blocked_db_unavailable",
            message=f"Database unavailable at {path}: {e}",
            db_path=str(path),
            report=report,
        ) from e

    conn.row_factory = sqlite3.Row

    # Required per 07 + schema
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA busy_timeout = 5000")

    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Context manager for a transaction with automatic commit/rollback."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
