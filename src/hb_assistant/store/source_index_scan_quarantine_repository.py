"""Repository for the V125 durable poison-file quarantine (see source_index_scan_quarantine_tables).

Mutation methods are CONNECTION-COMPOSABLE: the scan loop passes its open ``conn`` (and
``in_transaction=True``) so the atomic threshold transition — attempt finalize + quarantine upsert + failure
classification — commits in the SAME transaction as the generation cursor advance. A crash therefore rolls
back both, never leaving a cursor advanced without a quarantine record (or vice-versa).

All stored data is sanitized: ``rel_path`` is root-relative, ``error_code`` is a structured classification
(never a raw exception string), and no absolute host path is written.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

from .connection import get_connection, transaction
from .source_index_scan_quarantine_tables import (
    QUARANTINE_ERROR_CODES,
    RESOLUTION_CONFIRMED_ABSENT,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED,
    STATUS_QUARANTINED,
    STATUS_RESOLVED,
)

_RETRYING = "retrying"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceIndexScanQuarantineRepository:
    """Durable per-(root, path) poison-file quarantine. Root-level blocker; survives generation pruning."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @contextmanager
    def _conn(
        self, conn: sqlite3.Connection | None, in_transaction: bool
    ) -> Iterator[sqlite3.Connection]:
        """Use the caller's connection (composable, atomic with their transaction) or open+commit our own."""
        if conn is not None:
            yield conn
            return
        c = get_connection(self.db_path)
        try:
            with transaction(c):
                yield c
        finally:
            c.close()

    # ---- mutation (scan-loop, composable) ---------------------------------------------------------
    def record_failure(
        self,
        *,
        root_key: str,
        rel_path: str,
        source_id: str | None,
        generation_id: str | None,
        failure_stage: str,
        error_code: str,
        threshold: int,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
        now: str | None = None,
    ) -> dict[str, Any]:
        """Finalize one per-file failure for (root, rel_path). Increments the durable attempt count and, when
        it reaches ``threshold``, promotes the record to a BLOCKING quarantine.

        Returns ``{"action": "hold"|"quarantine", "attempt_count": int, "quarantine_id": str}``:
        ``hold`` — below threshold, the caller keeps the cursor before the file and retries next pass;
        ``quarantine`` — at/above threshold, the caller advances the cursor past the file and continues.
        The write is part of the caller's transaction (atomic with their cursor advance)."""
        if error_code not in QUARANTINE_ERROR_CODES:
            error_code = "metadata_upsert_failed"
        ts = now or _now()
        thr = max(1, int(threshold))
        with self._conn(conn, in_transaction) as c:
            row = c.execute(
                "SELECT quarantine_id, attempt_count FROM source_index_scan_quarantine "
                "WHERE source_root_key=? AND rel_path=? AND resolution_state=?",
                (root_key, rel_path, RESOLUTION_UNRESOLVED),
            ).fetchone()
            if row is None:
                qid = uuid.uuid4().hex
                attempt = 1
                status = STATUS_QUARANTINED if attempt >= thr else _RETRYING
                c.execute(
                    "INSERT INTO source_index_scan_quarantine ("
                    "quarantine_id, source_root_key, generation_id, origin_generation_id, source_id, "
                    "rel_path, failure_stage, error_code, attempt_count, first_seen_at, last_seen_at, "
                    "last_attempt_at, status, resolution_state) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (qid, root_key, generation_id, generation_id, source_id, rel_path, failure_stage,
                     error_code, attempt, ts, ts, ts, status, RESOLUTION_UNRESOLVED),
                )
            else:
                qid = row["quarantine_id"] if isinstance(row, sqlite3.Row) else row[0]
                prev = row["attempt_count"] if isinstance(row, sqlite3.Row) else row[1]
                attempt = int(prev) + 1
                status = STATUS_QUARANTINED if attempt >= thr else _RETRYING
                c.execute(
                    "UPDATE source_index_scan_quarantine SET attempt_count=?, last_seen_at=?, "
                    "last_attempt_at=?, error_code=?, failure_stage=?, status=?, "
                    "generation_id=COALESCE(?, generation_id) WHERE quarantine_id=?",
                    (attempt, ts, ts, error_code, failure_stage, status, generation_id, qid),
                )
            action = "quarantine" if attempt >= thr else "hold"
        return {"action": action, "attempt_count": attempt, "quarantine_id": qid}

    def resolve_observed(
        self,
        *,
        root_key: str,
        rel_path: str,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
        now: str | None = None,
    ) -> bool:
        """A previously-troubled path was successfully observed this pass: resolve its unresolved record so a
        genuinely transient failure never accumulates toward the threshold. Returns True if a row was cleared."""
        ts = now or _now()
        with self._conn(conn, in_transaction) as c:
            cur = c.execute(
                "UPDATE source_index_scan_quarantine SET status=?, resolution_state=?, resolved_at=?, "
                "last_successful_observation_at=? WHERE source_root_key=? AND rel_path=? AND resolution_state=?",
                (STATUS_RESOLVED, RESOLUTION_RESOLVED, ts, ts, root_key, rel_path, RESOLUTION_UNRESOLVED),
            )
            return cur.rowcount > 0

    def resolve(
        self,
        *,
        quarantine_id: str,
        resolution_state: str,
        last_successful_observation_at: str | None = None,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
        now: str | None = None,
    ) -> bool:
        """Operator-driven resolution of one quarantine (``resolved`` or ``confirmed_absent``). The caller is
        responsible for the trustworthiness contract before passing ``confirmed_absent``."""
        if resolution_state not in (RESOLUTION_RESOLVED, RESOLUTION_CONFIRMED_ABSENT):
            raise ValueError(f"invalid resolution_state: {resolution_state!r}")
        ts = now or _now()
        with self._conn(conn, in_transaction) as c:
            cur = c.execute(
                "UPDATE source_index_scan_quarantine SET status=?, resolution_state=?, resolved_at=?, "
                "last_successful_observation_at=COALESCE(?, last_successful_observation_at) "
                "WHERE quarantine_id=? AND resolution_state=?",
                (STATUS_RESOLVED, resolution_state, ts, last_successful_observation_at, quarantine_id,
                 RESOLUTION_UNRESOLVED),
            )
            return cur.rowcount > 0

    def null_generation_ids(
        self,
        generation_ids: Iterable[str],
        *,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
    ) -> int:
        """Retention support: NULL ``generation_id`` for records whose originating generation was pruned,
        while retaining ``origin_generation_id`` for audit. Unresolved records survive (no cascade delete)."""
        ids = [g for g in generation_ids if g]
        if not ids:
            return 0
        with self._conn(conn, in_transaction) as c:
            marks = ",".join("?" for _ in ids)
            cur = c.execute(
                f"UPDATE source_index_scan_quarantine SET generation_id=NULL "
                f"WHERE generation_id IN ({marks})",
                ids,
            )
            return cur.rowcount

    # ---- reads (trust / gating / status) ----------------------------------------------------------
    def blocking_count(self, root_key: str, *, conn: sqlite3.Connection | None = None) -> int:
        """Count of records that BLOCK the root (status=quarantined AND resolution_state=unresolved).
        Below-threshold ``retrying`` records do NOT block. Fail-closed callers treat >0 as unsafe."""
        c = conn or get_connection(self.db_path)
        try:
            return int(
                c.execute(
                    "SELECT COUNT(*) FROM source_index_scan_quarantine "
                    "WHERE source_root_key=? AND status=? AND resolution_state=?",
                    (root_key, STATUS_QUARANTINED, RESOLUTION_UNRESOLVED),
                ).fetchone()[0]
            )
        finally:
            if conn is None:
                c.close()

    def has_blocking(self, root_key: str, *, conn: sqlite3.Connection | None = None) -> bool:
        return self.blocking_count(root_key, conn=conn) > 0

    def blocking_paths(self, root_key: str, *, conn: sqlite3.Connection | None = None) -> set[str]:
        """rel_paths that are actively quarantined (skip them immediately on a fresh walk)."""
        c = conn or get_connection(self.db_path)
        try:
            return {
                r[0]
                for r in c.execute(
                    "SELECT rel_path FROM source_index_scan_quarantine "
                    "WHERE source_root_key=? AND status=? AND resolution_state=?",
                    (root_key, STATUS_QUARANTINED, RESOLUTION_UNRESOLVED),
                ).fetchall()
            }
        finally:
            if conn is None:
                c.close()

    def troubled_paths(self, root_key: str, *, conn: sqlite3.Connection | None = None) -> set[str]:
        """rel_paths with ANY unresolved record (retrying or quarantined) — the small set to reconcile on a
        successful observation so transient failures never accumulate."""
        c = conn or get_connection(self.db_path)
        try:
            return {
                r[0]
                for r in c.execute(
                    "SELECT rel_path FROM source_index_scan_quarantine "
                    "WHERE source_root_key=? AND resolution_state=?",
                    (root_key, RESOLUTION_UNRESOLVED),
                ).fetchall()
            }
        finally:
            if conn is None:
                c.close()

    def blocking_counts_by_root(
        self, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, int]:
        """Batch: {root_key: blocking_count} for every root with a blocking quarantine (health projection)."""
        c = conn or get_connection(self.db_path)
        try:
            return {
                r[0]: int(r[1])
                for r in c.execute(
                    "SELECT source_root_key, COUNT(*) FROM source_index_scan_quarantine "
                    "WHERE status=? AND resolution_state=? GROUP BY source_root_key",
                    (STATUS_QUARANTINED, RESOLUTION_UNRESOLVED),
                ).fetchall()
            }
        finally:
            if conn is None:
                c.close()

    def list_quarantine(
        self,
        root_key: str | None = None,
        *,
        resolution_state: str | None = RESOLUTION_UNRESOLVED,
        limit: int = 100,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Sanitized read-only listing (rel_path only; no absolute paths / exception text)."""
        c = conn or get_connection(self.db_path)
        try:
            clauses, params = [], []
            if root_key is not None:
                clauses.append("source_root_key=?")
                params.append(root_key)
            if resolution_state is not None:
                clauses.append("resolution_state=?")
                params.append(resolution_state)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            params.append(max(1, int(limit)))
            rows = c.execute(
                "SELECT quarantine_id, source_root_key, rel_path, error_code, failure_stage, "
                "attempt_count, status, resolution_state, first_seen_at, last_seen_at, last_attempt_at, "
                "resolved_at, generation_id, origin_generation_id, last_successful_observation_at "
                f"FROM source_index_scan_quarantine {where} "
                "ORDER BY last_seen_at DESC, rowid DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            if conn is None:
                c.close()

    def get(
        self, quarantine_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        c = conn or get_connection(self.db_path)
        try:
            row = c.execute(
                "SELECT quarantine_id, source_root_key, rel_path, error_code, failure_stage, "
                "attempt_count, status, resolution_state, first_seen_at, last_seen_at, last_attempt_at, "
                "resolved_at, generation_id, origin_generation_id, last_successful_observation_at "
                "FROM source_index_scan_quarantine WHERE quarantine_id=?",
                (quarantine_id,),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            if conn is None:
                c.close()
