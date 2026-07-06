"""Sole reader/writer of the V101 enrichment tables (N8C-5).

Writes only to ``assistant_enrichment_jobs`` / ``assistant_enrichment_receipts`` — never a
source/import table, never the vault. Owns the queue lifecycle: idempotent enqueue, ATOMIC
single-owner claim, lease heartbeat/expiry, and terminal completion with a receipt. Enforces enum
and size invariants before touching the DB (the schema CHECKs are the backstop).

Lifecycle: ``queued -> claimed -> running -> {completed | stale | failed}``. ``claimed`` marks a job
leased to one worker; ``running`` marks generation in progress (both hold a lease and are reclaimable
once ``lease_expires_at`` passes). A failed job with attempts remaining returns to ``queued``.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .enrichment_models import (
    ENRICHMENT_APPLIED_STATUSES,
    ENRICHMENT_JOB_TYPES,
    ENRICHMENT_SUBJECT_TYPES,
    ERROR_MAX_CHARS,
    PAYLOAD_MAX_CHARS,
    RESULT_MAX_CHARS,
    SAFETY_FLAGS_MAX_CHARS,
    STATUS_CLAIMED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    STATUS_STALE,
    EnrichmentValidationError,
    bound_text,
    compute_job_id,
    dumps_capped,
)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

# Statuses that hold a live lease and are reclaimable / transition-able by their owner.
_LEASED_STATUSES = (STATUS_CLAIMED, STATUS_RUNNING)
# Terminal statuses a worker may set via complete_job.
_COMPLETE_STATUSES = frozenset({STATUS_COMPLETED, STATUS_STALE, STATUS_SKIPPED})

_JOB_COLUMNS = (
    "job_id", "job_type", "subject_type", "source_id", "note_rel_path", "card_id", "claim_id",
    "status", "priority", "payload_json", "source_digest", "card_digest", "input_digest",
    "lease_owner", "lease_expires_at", "attempt_count", "max_attempts", "last_error",
    "created_at", "updated_at", "claimed_at", "completed_at",
)

_RECEIPT_COLUMNS = (
    "receipt_id", "job_id", "job_type", "worker_id", "runtime", "model_name", "prompt_version",
    "input_digest", "output_digest", "source_digest_at_completion", "card_digest_at_completion",
    "result_json", "applied_status", "safety_flags_json", "error_message", "created_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


def _lease_expiry(now: str | None, lease_seconds: int) -> str:
    return (_parse_iso(now) + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


class EnrichmentRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- enqueue (idempotent) ------------------------------------------------------------
    def queue_job(
        self,
        *,
        job_type: str,
        source_id: str | None = None,
        note_rel_path: str | None = None,
        card_id: str | None = None,
        claim_id: str | None = None,
        subject_type: str = "source",
        priority: int = 100,
        payload: dict[str, Any] | None = None,
        payload_key: str = "",
        source_digest: str | None = None,
        card_digest: str | None = None,
        max_attempts: int = 3,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Idempotently enqueue one job. Returns ``{job_id, created, status}``.

        Same (job_type, source_id, note_rel_path, payload_key) => same ``job_id``: an existing QUEUED
        job is refreshed in place; an in-flight/terminal job is left untouched (no duplicate row, no
        disruption). Provenance is mandatory — at least one of source_id / note_rel_path.
        """
        if job_type not in ENRICHMENT_JOB_TYPES:
            raise EnrichmentValidationError(f"invalid job_type: {job_type}")
        if subject_type not in ENRICHMENT_SUBJECT_TYPES:
            raise EnrichmentValidationError(f"invalid subject_type: {subject_type}")
        if not source_id and not note_rel_path:
            raise EnrichmentValidationError("unsupported_job: source_id or note_rel_path required")
        payload_json = dumps_capped(payload, PAYLOAD_MAX_CHARS) if payload else None
        job_id = compute_job_id(job_type, source_id, note_rel_path, payload_key)
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            existing = c.execute(
                "SELECT status FROM assistant_enrichment_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing is None:
                c.execute(
                    "INSERT INTO assistant_enrichment_jobs "
                    "(job_id, job_type, subject_type, source_id, note_rel_path, card_id, claim_id, "
                    " status, priority, payload_json, source_digest, card_digest, attempt_count, "
                    " max_attempts, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?, 'queued', ?,?,?,?, 0, ?,?,?)",
                    (job_id, job_type, subject_type, source_id, note_rel_path, card_id, claim_id,
                     int(priority), payload_json, source_digest, card_digest, int(max_attempts),
                     now, now),
                )
                return {"job_id": job_id, "created": True, "status": STATUS_QUEUED}
            status = existing[0]
            if status == STATUS_QUEUED:
                # Refresh a still-queued job's inputs in place (no duplicate, no reset of an in-flight job).
                c.execute(
                    "UPDATE assistant_enrichment_jobs SET priority=?, payload_json=?, source_digest=?, "
                    "card_digest=?, updated_at=? WHERE job_id=? AND status='queued'",
                    (int(priority), payload_json, source_digest, card_digest, now, job_id),
                )
            return {"job_id": job_id, "created": False, "status": status}

    # ----- read-only peek (for dry-run; never mutates) -------------------------------------
    def peek_next_job(self, *, job_types: tuple[str, ...] | None = None,
                      conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        """Read-only: return the next claimable job WITHOUT claiming it (used by worker dry-run)."""
        clause, params = self._queued_filter(job_types)
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM assistant_enrichment_jobs "
                f"WHERE status='queued'{clause} ORDER BY priority, created_at LIMIT 1",
                params,
            ).fetchone()
        return self._job_row(row)

    # ----- atomic claim --------------------------------------------------------------------
    def claim_next_job(self, worker_id: str, lease_seconds: int = 300, *,
                       job_types: tuple[str, ...] | None = None, now: str | None = None,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        """Atomically lease the next queued job to ``worker_id``. Returns the job or ``None``.

        The conditional ``UPDATE ... WHERE job_id=? AND status='queued'`` is the atomicity guarantee:
        a second worker's update matches zero rows once the first has flipped the status, so two
        workers can never hold the same job.
        """
        now = now or _now()
        expiry = _lease_expiry(now, lease_seconds)
        clause, params = self._queued_filter(job_types)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            rows = c.execute(
                f"SELECT job_id FROM assistant_enrichment_jobs "
                f"WHERE status='queued'{clause} ORDER BY priority, created_at LIMIT 25",
                params,
            ).fetchall()
            for (job_id,) in rows:
                cur = c.execute(
                    "UPDATE assistant_enrichment_jobs SET status='claimed', lease_owner=?, "
                    "lease_expires_at=?, claimed_at=?, attempt_count=attempt_count+1, updated_at=? "
                    "WHERE job_id=? AND status='queued'",
                    (worker_id, expiry, now, now, job_id),
                )
                if cur.rowcount == 1:
                    return self.get_job(job_id, conn=c)
            return None

    def mark_running(self, job_id: str, worker_id: str, *,
                     conn: sqlite3.Connection | None = None) -> bool:
        """Transition a leased job to ``running`` (owner-checked)."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE assistant_enrichment_jobs SET status='running', updated_at=? "
                "WHERE job_id=? AND lease_owner=? AND status IN ('claimed','running')",
                (now, job_id, worker_id),
            )
            return cur.rowcount == 1

    def heartbeat_job(self, job_id: str, worker_id: str, lease_seconds: int = 300, *,
                      now: str | None = None, conn: sqlite3.Connection | None = None) -> bool:
        """Extend the lease for a job this worker owns. Returns False if not owned/leased."""
        now = now or _now()
        expiry = _lease_expiry(now, lease_seconds)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE assistant_enrichment_jobs SET lease_expires_at=?, updated_at=? "
                "WHERE job_id=? AND lease_owner=? AND status IN ('claimed','running')",
                (expiry, now, job_id, worker_id),
            )
            return cur.rowcount == 1

    def release_expired_leases(self, *, now: str | None = None,
                               conn: sqlite3.Connection | None = None) -> int:
        """Requeue jobs whose lease expired (e.g. a crashed worker). Returns count requeued."""
        now = now or _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE assistant_enrichment_jobs SET status='queued', lease_owner=NULL, "
                "lease_expires_at=NULL, updated_at=? "
                "WHERE status IN ('claimed','running') AND lease_expires_at IS NOT NULL "
                "AND lease_expires_at < ?",
                (now, now),
            )
            return cur.rowcount or 0

    # ----- terminal completion + receipts --------------------------------------------------
    def complete_job(self, job_id: str, worker_id: str, *, status: str, result_json: str | None,
                     applied_status: str, receipt_metadata: dict[str, Any] | None = None,
                     conn: sqlite3.Connection | None = None) -> bool:
        """Terminally complete an owned job and write its receipt (one transaction).

        Returns False (no write) if the caller does not own a currently-leased job — a lost lease
        (e.g. reclaimed after expiry) can never overwrite another worker's outcome.
        """
        if status not in _COMPLETE_STATUSES:
            raise EnrichmentValidationError(f"invalid completion status: {status}")
        if applied_status not in ENRICHMENT_APPLIED_STATUSES:
            raise EnrichmentValidationError(f"invalid applied_status: {applied_status}")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            owned = c.execute(
                "SELECT 1 FROM assistant_enrichment_jobs WHERE job_id=? AND lease_owner=? "
                "AND status IN ('claimed','running')",
                (job_id, worker_id),
            ).fetchone()
            if owned is None:
                return False
            c.execute(
                "UPDATE assistant_enrichment_jobs SET status=?, lease_owner=NULL, "
                "lease_expires_at=NULL, completed_at=?, updated_at=? WHERE job_id=?",
                (status, now, now, job_id),
            )
            self._write_receipt(c, job_id, applied_status, result_json, receipt_metadata, None, now)
        return True

    def fail_job(self, job_id: str, worker_id: str, error: str, *,
                 receipt_metadata: dict[str, Any] | None = None,
                 conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Record a failed attempt. Requeues if attempts remain, else marks the job ``failed``.

        Always writes a ``failed`` receipt. Returns ``{status, requeued}`` (or ``{owned: False}``).
        """
        now = _now()
        err = bound_text(error, ERROR_MAX_CHARS)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT attempt_count, max_attempts FROM assistant_enrichment_jobs "
                "WHERE job_id=? AND lease_owner=? AND status IN ('claimed','running')",
                (job_id, worker_id),
            ).fetchone()
            if row is None:
                return {"owned": False}
            attempt_count, max_attempts = int(row[0]), int(row[1])
            requeued = attempt_count < max_attempts
            if requeued:
                c.execute(
                    "UPDATE assistant_enrichment_jobs SET status='queued', lease_owner=NULL, "
                    "lease_expires_at=NULL, last_error=?, updated_at=? WHERE job_id=?",
                    (err, now, job_id),
                )
                new_status = STATUS_QUEUED
            else:
                c.execute(
                    "UPDATE assistant_enrichment_jobs SET status='failed', lease_owner=NULL, "
                    "lease_expires_at=NULL, last_error=?, completed_at=?, updated_at=? WHERE job_id=?",
                    (err, now, now, job_id),
                )
                new_status = STATUS_FAILED
            self._write_receipt(c, job_id, "failed", None, receipt_metadata, err, now)
        return {"status": new_status, "requeued": requeued}

    def _write_receipt(self, c: sqlite3.Connection, job_id: str, applied_status: str,
                       result_json: str | None, meta: dict[str, Any] | None,
                       error_message: str | None, now: str) -> None:
        meta = meta or {}
        job_type_row = c.execute(
            "SELECT job_type FROM assistant_enrichment_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        job_type = job_type_row[0] if job_type_row else meta.get("job_type")
        if result_json is not None and len(result_json) > RESULT_MAX_CHARS:
            result_json = bound_text(result_json, RESULT_MAX_CHARS)
        safety = meta.get("safety_flags")
        safety_json = None
        if safety:
            import json
            safety_json = bound_text(json.dumps(safety, sort_keys=True), SAFETY_FLAGS_MAX_CHARS)
        c.execute(
            "INSERT INTO assistant_enrichment_receipts "
            "(receipt_id, job_id, job_type, worker_id, runtime, model_name, prompt_version, "
            " input_digest, output_digest, source_digest_at_completion, card_digest_at_completion, "
            " result_json, applied_status, safety_flags_json, error_message, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, job_id, job_type, meta.get("worker_id"), meta.get("runtime"),
             meta.get("model_name"), meta.get("prompt_version"), meta.get("input_digest"),
             meta.get("output_digest"), meta.get("source_digest_at_completion"),
             meta.get("card_digest_at_completion"), result_json, applied_status, safety_json,
             bound_text(error_message, ERROR_MAX_CHARS) if error_message else None, now),
        )

    # ----- read (bounded) ------------------------------------------------------------------
    def get_job(self, job_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM assistant_enrichment_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        return self._job_row(row)

    def list_jobs(self, *, status: str | None = None, job_type: str | None = None,
                  limit: int = _DEFAULT_LIMIT,
                  conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("status", status), ("job_type", job_type)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_JOB_COLUMNS)} FROM assistant_enrichment_jobs {where}"
                "ORDER BY created_at DESC, job_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._job_row(r) for r in rows if r is not None]  # type: ignore[misc]

    def list_receipts(self, *, job_id: str | None = None, limit: int = _DEFAULT_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        where = "WHERE job_id=? " if job_id else ""
        params: list[Any] = [job_id] if job_id else []
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_enrichment_receipts {where}"
                "ORDER BY created_at DESC, receipt_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def count_jobs(self, *, status: str | None = None,
                   conn: sqlite3.Connection | None = None) -> int:
        where = "WHERE status=?" if status else ""
        params = (status,) if status else ()
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_enrichment_jobs {where}", params).fetchone()[0])

    @staticmethod
    def _queued_filter(job_types: tuple[str, ...] | None) -> tuple[str, list[Any]]:
        if not job_types:
            return "", []
        placeholders = ",".join("?" for _ in job_types)
        return f" AND job_type IN ({placeholders})", list(job_types)

    @staticmethod
    def _job_row(row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(zip(_JOB_COLUMNS, row, strict=True))
