"""Reader/writer for the V117 source-index bootstrap + reconciliation tables.

Kept deliberately separate from ``SourceIndexRepository`` (the V93 content-index writer): bootstrap
readiness and reconciliation receipts are a distinct concern and never touch the FTS-synced content
tables. The structure-drift *signal* is a k/v row in the existing ``source_intelligence_state`` table
(the same additive-k/v convention that table already uses for watcher lease / drain timestamps), so no
schema was added for it — reconciliation flags drift, health reads it.

No absolute host paths are stored: ``root_key`` is the opaque file-index ``source_root_key``.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

_STATE_DRIFT_PREFIX = "structure_drift:"

# Columns a caller may set via upsert_bootstrap_state (root_key + created/updated are managed here).
_BOOTSTRAP_COLUMNS: frozenset[str] = frozenset(
    {
        "file_index_bootstrapped",
        "file_index_last_bootstrap_at",
        "file_index_last_success_at",
        "file_index_status",
        "structure_index_bootstrapped",
        "structure_index_last_bootstrap_at",
        "structure_index_last_success_at",
        "structure_index_status",
        "watcher_ready",
        "last_health_check_at",
        "last_error",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceIndexBootstrapRepository:
    """Durable per-root bootstrap readiness state + reconciliation-run receipts."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- bootstrap readiness state ---------------------------------------------------------
    def upsert_bootstrap_state(
        self, root_key: str, *, conn: sqlite3.Connection | None = None, **fields: Any
    ) -> None:
        """Insert the row if missing, then set only the provided columns (untouched columns are
        preserved — so a ``--file-index-only`` bootstrap never clobbers structure state)."""
        unknown = set(fields) - _BOOTSTRAP_COLUMNS
        if unknown:
            raise ValueError(f"unknown bootstrap_state columns: {sorted(unknown)}")
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT OR IGNORE INTO source_index_bootstrap_state (root_key) VALUES (?)",
                (root_key,),
            )
            if fields:
                assignments = ", ".join(f"{col}=?" for col in fields)
                values = list(fields.values())
                c.execute(
                    f"UPDATE source_index_bootstrap_state SET {assignments}, updated_at=? "
                    "WHERE root_key=?",
                    (*values, _now(), root_key),
                )

    def get_bootstrap_state(
        self, root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM source_index_bootstrap_state WHERE root_key=?", (root_key,)
            ).fetchone()
        return dict(row) if row is not None else None

    def list_bootstrap_state(
        self, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM source_index_bootstrap_state ORDER BY root_key"
            ).fetchall()
        return [dict(r) for r in rows]

    # ----- reconciliation-run receipts -------------------------------------------------------
    def start_reconciliation_run(
        self, run_id: str, root_key: str, scan_type: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_index_reconciliation_runs "
                "(run_id, root_key, scan_type, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                (run_id, root_key, scan_type, _now()),
            )

    def finish_reconciliation_run(
        self,
        run_id: str,
        *,
        status: str = "completed",
        files_seen: int = 0,
        folders_seen: int = 0,
        changes_detected: int = 0,
        events_enqueued: int = 0,
        errors_count: int = 0,
        last_error: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_index_reconciliation_runs SET status=?, finished_at=?, files_seen=?, "
                "folders_seen=?, changes_detected=?, events_enqueued=?, errors_count=?, last_error=? "
                "WHERE run_id=?",
                (
                    status,
                    _now(),
                    int(files_seen),
                    int(folders_seen),
                    int(changes_detected),
                    int(events_enqueued),
                    int(errors_count),
                    last_error,
                    run_id,
                ),
            )

    def last_reconciliation(
        self, root_key: str | None = None, *, scan_type: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        clauses: list[str] = []
        params: list[Any] = []
        if root_key is not None:
            clauses.append("root_key=?")
            params.append(root_key)
        if scan_type is not None:
            clauses.append("scan_type=?")
            params.append(scan_type)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM source_index_reconciliation_runs" + where
                + " ORDER BY created_at DESC, rowid DESC LIMIT 1",
                params,
            ).fetchone()
        return dict(row) if row is not None else None

    # ----- structure-drift signal (k/v in source_intelligence_state; no schema change) --------
    def set_structure_drift(
        self, root_key: str, *, detected: bool, refresh_recommended: bool,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Record that reconciliation observed directory-architecture drift for a root. This is a
        signal ONLY — this branch does not auto-rebuild structure (the dirty-bridge is deferred)."""
        value = "1" if detected else "0"
        rec = "1" if refresh_recommended else "0"
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            for suffix, val in ((root_key, value), (f"{root_key}:refresh", rec)):
                c.execute(
                    "INSERT INTO source_intelligence_state (state_key, state_value, updated_at) "
                    "VALUES (?, ?, ?) ON CONFLICT(state_key) DO UPDATE SET "
                    "state_value=excluded.state_value, updated_at=excluded.updated_at",
                    (f"{_STATE_DRIFT_PREFIX}{suffix}", val, _now()),
                )

    def get_structure_drift(
        self, root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, bool]:
        with borrow_connection(conn, self.db_path) as c:
            rows = {
                r[0]: r[1]
                for r in c.execute(
                    "SELECT state_key, state_value FROM source_intelligence_state "
                    "WHERE state_key IN (?, ?)",
                    (f"{_STATE_DRIFT_PREFIX}{root_key}", f"{_STATE_DRIFT_PREFIX}{root_key}:refresh"),
                ).fetchall()
            }
        return {
            "directory_change_detected": rows.get(f"{_STATE_DRIFT_PREFIX}{root_key}") == "1",
            "structure_refresh_recommended": rows.get(f"{_STATE_DRIFT_PREFIX}{root_key}:refresh")
            == "1",
        }
