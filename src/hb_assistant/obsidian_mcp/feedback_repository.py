"""Sole reader/writer of the V109 feedback tables (N8C-18).

Writes ONLY ``assistant_feedback_records`` / ``assistant_feedback_targets`` /
``assistant_feedback_recommendations`` / ``assistant_feedback_receipts`` / ``assistant_feedback_events`` —
NEVER a workflow, review, source, packet, draft, projection, context-pack, claim, memory, decision,
preference, or open-loop table (all of those are read-only inputs), never a review disposition, never the
vault, never a source file.

``upsert_feedback`` is deterministic + idempotent: an unchanged ``feedback_id`` (identical feedback type +
targets + note + author) is a no-op (reused, no duplicate). It never supersedes or mutates any upstream
record — feedback is advisory input to the review loop, not a state change.

Every read method threads an optional ``conn=`` so a caller (e.g. the MCP broker's read-only snapshot) can
pin one connection. Rows are plain dicts.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .feedback_models import EVENT_TYPES, FeedbackValidationError

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_RECORD_COLUMNS = (
    "feedback_id", "feedback_type", "note", "workflow_type", "workflow_id", "status", "action_policy",
    "execution_policy", "review_policy", "source_policy", "citation_policy", "requires_operator_review",
    "created_by", "created_at", "updated_at", "input_digest", "output_digest", "target_count",
    "recommendation_count", "truncated", "metadata_json",
)

_TARGET_COLUMNS = (
    "feedback_target_id", "feedback_id", "target_order", "target_kind", "target_id", "target_label",
    "workflow_id", "workflow_type", "workflow_section", "draft_id", "draft_section_id", "packet_id",
    "packet_item_id", "projection_id", "projection_item_id", "context_pack_id", "memory_node_id",
    "memory_mention_id", "decision_id", "preference_id", "open_loop_id", "review_item_id", "claim_id",
    "citation_id", "source_id", "source_ref", "source_root_key", "rel_path", "note_rel_path",
    "target_digest", "review_state", "effective_state", "created_at", "metadata_json",
)

_RECOMMENDATION_COLUMNS = (
    "recommendation_id", "feedback_id", "recommendation_order", "recommendation_type", "target_kind",
    "target_id", "rationale", "review_policy", "requires_operator_review", "created_at", "metadata_json",
)

_RECEIPT_COLUMNS = (
    "feedback_receipt_id", "feedback_id", "builder_version", "input_digest", "output_digest",
    "target_count", "recommendation_count", "dropped_count", "truncated", "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "feedback_id", "event_type", "from_status", "to_status", "detail", "created_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


class FeedbackRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write (feedback-owned tables ONLY) ---------------------------------------------
    def upsert_feedback(self, record: dict[str, Any], targets: list[dict[str, Any]],
                        recommendations: list[dict[str, Any]], receipt: dict[str, Any], *,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        fid = record.get("feedback_id")
        ftype = record.get("feedback_type")
        if not fid or not ftype:
            raise FeedbackValidationError("feedback_id_and_type_required")
        if not targets:
            raise FeedbackValidationError("feedback_requires_at_least_one_target")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_feedback_records WHERE feedback_id=?", (fid,)
            ).fetchone()
            if exists is not None:
                return {"feedback_id": fid, "created": False, "reused": True}
            header = {**record, "status": record.get("status", "open"), "created_at": now,
                      "updated_at": now}
            self._insert(c, "assistant_feedback_records", _RECORD_COLUMNS, header)
            for t in targets:
                self._insert(c, "assistant_feedback_targets", _TARGET_COLUMNS, {**t, "created_at": now})
            for r in recommendations:
                self._insert(c, "assistant_feedback_recommendations", _RECOMMENDATION_COLUMNS,
                             {**r, "created_at": now})
            self._insert(c, "assistant_feedback_receipts", _RECEIPT_COLUMNS, {**receipt, "created_at": now})
            self._insert_event(c, fid, "created", from_status=None, to_status="open",
                               detail=record.get("input_digest"), now=now)
            self._insert_event(c, fid, "linked", from_status="open", to_status="open",
                               detail=str(len(targets)), now=now)
            if recommendations:
                self._insert_event(c, fid, "recommended", from_status="open", to_status="open",
                                   detail=str(len(recommendations)), now=now)
            return {"feedback_id": fid, "created": True, "reused": False,
                    "target_count": len(targets), "recommendation_count": len(recommendations)}

    def _insert(self, c: sqlite3.Connection, table: str, columns: tuple[str, ...],
                row: dict[str, Any]) -> None:
        cols = [col for col in columns if col in row]
        placeholders = ", ".join("?" for _ in cols)
        c.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608 (fixed cols)
            tuple(row.get(col) for col in cols),
        )

    def _insert_event(self, c: sqlite3.Connection, feedback_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise FeedbackValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_feedback_events "
            "(event_id, feedback_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, feedback_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    # ----- read ---------------------------------------------------------------------------
    def get_feedback(self, feedback_id: str, *,
                     conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_RECORD_COLUMNS)} FROM assistant_feedback_records "
                "WHERE feedback_id=?", (feedback_id,)
            ).fetchone()
        return dict(zip(_RECORD_COLUMNS, row, strict=True)) if row else None

    def list_feedback(self, *, feedback_type: str | None = None, status: str | None = None,
                      workflow_id: str | None = None, limit: int = _DEFAULT_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("feedback_type", feedback_type), ("status", status),
                         ("workflow_id", workflow_id)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECORD_COLUMNS)} FROM assistant_feedback_records "  # noqa: S608
                f"{where}ORDER BY updated_at DESC, feedback_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_RECORD_COLUMNS, r, strict=True)) for r in rows]

    def list_targets(self, feedback_id: str, *, limit: int = _MAX_LIMIT,
                     conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_TARGET_COLUMNS)} FROM assistant_feedback_targets "
                "WHERE feedback_id=? ORDER BY target_order ASC, feedback_target_id ASC LIMIT ?",
                (feedback_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_TARGET_COLUMNS, r, strict=True)) for r in rows]

    def list_recommendations(self, feedback_id: str | None = None, *, recommendation_type: str | None = None,
                             target_kind: str | None = None, target_id: str | None = None,
                             limit: int = _MAX_LIMIT,
                             conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("feedback_id", feedback_id), ("recommendation_type", recommendation_type),
                         ("target_kind", target_kind), ("target_id", target_id)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECOMMENDATION_COLUMNS)} FROM assistant_feedback_recommendations "  # noqa: S608, E501
                f"{where}ORDER BY created_at DESC, recommendation_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_RECOMMENDATION_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, feedback_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_feedback_receipts "
                "WHERE feedback_id=? ORDER BY created_at DESC, feedback_receipt_id DESC LIMIT ?",
                (feedback_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, feedback_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_feedback_events "
                "WHERE feedback_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (feedback_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, *, feedback_type: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("feedback_type", feedback_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_feedback_records {where}",  # noqa: S608
                params).fetchone()[0])

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over feedback: counts by type and status + total targets/recommendations."""
        with borrow_connection(conn, self.db_path) as c:
            by_type = {r[0]: int(r[1]) for r in c.execute(
                "SELECT feedback_type, COUNT(*) FROM assistant_feedback_records "
                "GROUP BY feedback_type").fetchall()}
            by_status = {r[0]: int(r[1]) for r in c.execute(
                "SELECT status, COUNT(*) FROM assistant_feedback_records GROUP BY status").fetchall()}
            total = int(c.execute("SELECT COUNT(*) FROM assistant_feedback_records").fetchone()[0])
            targets = int(c.execute("SELECT COUNT(*) FROM assistant_feedback_targets").fetchone()[0])
            recs = int(c.execute(
                "SELECT COUNT(*) FROM assistant_feedback_recommendations").fetchone()[0])
        return {"total_feedback": total, "total_targets": targets, "total_recommendations": recs,
                "by_feedback_type": by_type, "by_status": by_status}
