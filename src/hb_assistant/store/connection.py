"""SQLite connection management with required PRAGMAs and transaction helper.

Per 07 spec: foreign_keys=ON, journal_mode=WAL, busy_timeout.
All access goes through get_connection() + transaction() context.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from hb_assistant.config.path_policy import PathPolicy


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite DB and apply required PRAGMAs.

    Caller must ensure directories via PathPolicy.ensure_dirs() before first use.
    """
    pp = PathPolicy()
    path = db_path or pp.get_db_path()
    pp.ensure_dirs(create_sensitive=False)  # db/ is 755, non-sensitive

    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row

    # Required per 07 + schema
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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
