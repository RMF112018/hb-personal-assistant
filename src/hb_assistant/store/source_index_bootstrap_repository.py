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


def insert_pass_row(
    c: sqlite3.Connection,
    *,
    run_id: str,
    root_key: str,
    mode: str,
    generation_id: str,
    now: str,
) -> None:
    """Connection-aware V119 pass-row insert (V120).

    Inserts one ``source_index_bootstrap_runs`` row linked to a longer-lived scan generation, on a
    caller-supplied connection WITHOUT opening its own transaction — so it can participate in the
    ``SourceIndexScanGenerationsRepository.begin_generation_pass`` ``BEGIN IMMEDIATE`` transaction as a
    single atomic pass-start. This is the ONLY generation-linked start path; there is deliberately no
    second public ``start_bootstrap_run`` for generation passes (generation lifecycle ownership lives
    solely in ``SourceIndexScanGenerationsRepository``). The partial-unique "one active run per root"
    index still applies, so a stale/abandoned prior run must already be cleared by the caller.
    """
    c.execute(
        "INSERT INTO source_index_bootstrap_runs "
        "(run_id, root_key, mode, status, started_at, heartbeat_at, generation_id) "
        "VALUES (?,?,?,'running',?,?,?)",
        (run_id, root_key, mode, now, now, generation_id),
    )

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

    # ----- bootstrap RUN records (V118): durable progress / heartbeat / lifecycle ----------------
    _RUN_COUNTER_COLUMNS: frozenset[str] = frozenset(
        {
            "files_walked",
            "metadata_upserted",
            "files_unchanged",
            "content_attempted",
            "content_succeeded",
            "content_failed",
            "errors_count",
        }
    )

    def start_bootstrap_run(
        self,
        run_id: str,
        root_key: str,
        mode: str = "bootstrap",
        *,
        stale_seconds: float = 120.0,
        conn: sqlite3.Connection | None = None,
    ) -> str | None:
        """Atomically claim the single active-run slot for ``root_key``.

        Returns ``run_id`` on success, or ``None`` if another LIVE run already holds the root (the
        partial-unique index rejects the insert). Before claiming, a prior ``running`` row whose
        heartbeat is older than ``stale_seconds`` (SIGKILL/OOM) is reaped to ``abandoned``, and the most
        recent ``partial`` run is linked (``resumed_from_run_id`` / ``superseded_by_run_id``) WITHOUT
        overwriting its terminal status, so run history is preserved.
        """
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_index_bootstrap_runs SET status='abandoned', finished_at=? "
                "WHERE root_key=? AND status='running' AND "
                "(julianday(?) - julianday(COALESCE(heartbeat_at, started_at))) * 86400 > ?",
                (now, root_key, now, float(stale_seconds)),
            )
            prior = c.execute(
                "SELECT run_id FROM source_index_bootstrap_runs WHERE root_key=? AND status='partial' "
                "AND superseded_by_run_id IS NULL ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (root_key,),
            ).fetchone()
            resumed_from = prior[0] if prior else None
            try:
                c.execute(
                    "INSERT INTO source_index_bootstrap_runs "
                    "(run_id, root_key, mode, status, started_at, heartbeat_at, resumed_from_run_id) "
                    "VALUES (?,?,?,'running',?,?,?)",
                    (run_id, root_key, mode, now, now, resumed_from),
                )
            except sqlite3.IntegrityError:
                # A live (non-stale) run already holds this root. Caller treats this as retryable.
                return None
            if resumed_from is not None:
                c.execute(
                    "UPDATE source_index_bootstrap_runs SET superseded_by_run_id=? WHERE run_id=?",
                    (run_id, resumed_from),
                )
        return run_id

    def heartbeat_bootstrap_run(
        self,
        run_id: str,
        *,
        phase: str | None = None,
        current_rel_prefix: str | None = None,
        stop_requested: bool | None = None,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> None:
        """Advance heartbeat + progress counters for an active run (no-op once terminal).

        Only whitelisted counter columns are accepted. Callers MUST wrap this in best-effort handling —
        a telemetry write must never abort the scan (observability is failure-isolated)."""
        unknown = set(counters) - self._RUN_COUNTER_COLUMNS
        if unknown:
            raise ValueError(f"unknown run counter columns: {sorted(unknown)}")
        sets = ["heartbeat_at=?"]
        vals: list[Any] = [_now()]
        if phase is not None:
            sets.append("phase=?")
            vals.append(phase)
        if current_rel_prefix is not None:
            sets.append("current_rel_prefix=?")
            vals.append(current_rel_prefix)
        if stop_requested is not None:
            sets.append("stop_requested=?")
            vals.append(1 if stop_requested else 0)
        for col, val in counters.items():
            sets.append(f"{col}=?")
            vals.append(int(val))
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                f"UPDATE source_index_bootstrap_runs SET {', '.join(sets)} "
                "WHERE run_id=? AND status='running'",
                (*vals, run_id),
            )

    def finish_bootstrap_run(
        self,
        run_id: str,
        *,
        status: str,
        bounded_reason: str | None = None,
        last_error_code: str | None = None,
        completed_metadata_walk: bool = False,
        reconciliation_completed: bool = False,
        current_rel_prefix: str | None = None,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> None:
        """Close a run to a terminal ``status`` with final counters (unconditional by run_id)."""
        unknown = set(counters) - self._RUN_COUNTER_COLUMNS
        if unknown:
            raise ValueError(f"unknown run counter columns: {sorted(unknown)}")
        sets = [
            "status=?",
            "finished_at=?",
            "heartbeat_at=?",
            "bounded_reason=?",
            "last_error_code=?",
            "completed_metadata_walk=?",
            "reconciliation_completed=?",
        ]
        now = _now()
        vals: list[Any] = [
            status, now, now, bounded_reason, last_error_code,
            1 if completed_metadata_walk else 0, 1 if reconciliation_completed else 0,
        ]
        if current_rel_prefix is not None:
            sets.append("current_rel_prefix=?")
            vals.append(current_rel_prefix)
        for col, val in counters.items():
            sets.append(f"{col}=?")
            vals.append(int(val))
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                f"UPDATE source_index_bootstrap_runs SET {', '.join(sets)} WHERE run_id=?",
                (*vals, run_id),
            )

    def interrupt_bootstrap_run(
        self, run_id: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        """Backstop: mark a still-``running`` run ``interrupted`` (no-op if already terminal)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_index_bootstrap_runs SET status='interrupted', finished_at=? "
                "WHERE run_id=? AND status='running'",
                (_now(), run_id),
            )

    def reap_stale_bootstrap_runs(
        self, root_key: str | None = None, *, stale_seconds: float = 120.0,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Mark stale ``running`` rows (heartbeat older than ``stale_seconds``) ``abandoned``. Returns count."""
        now = _now()
        clause = "" if root_key is None else "root_key=? AND "
        params: tuple[Any, ...] = (
            (now, now, float(stale_seconds)) if root_key is None
            else (now, root_key, now, float(stale_seconds))
        )
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE source_index_bootstrap_runs SET status='abandoned', finished_at=? "
                f"WHERE {clause}status='running' AND "
                "(julianday(?) - julianday(COALESCE(heartbeat_at, started_at))) * 86400 > ?",
                params,
            )
            return cur.rowcount or 0

    def get_bootstrap_run(
        self, run_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM source_index_bootstrap_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def list_bootstrap_runs(
        self, root_key: str | None = None, *, limit: int = 50,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            if root_key is None:
                rows = c.execute(
                    "SELECT * FROM source_index_bootstrap_runs ORDER BY created_at DESC, rowid DESC "
                    "LIMIT ?", (int(limit),)
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM source_index_bootstrap_runs WHERE root_key=? "
                    "ORDER BY created_at DESC, rowid DESC LIMIT ?", (root_key, int(limit))
                ).fetchall()
        return [dict(r) for r in rows]
