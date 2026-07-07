"""Sole reader/writer of the V111 quality tables (N8C-20).

Writes ONLY ``assistant_quality_runs`` / ``assistant_quality_findings`` / ``assistant_quality_targets`` /
``assistant_quality_receipts`` / ``assistant_quality_events`` — NEVER a workflow, feedback, action-stage,
review, source, packet, draft, projection, context-pack, claim, memory, decision, preference, or open-loop
table (all read-only inputs), never a review disposition, never an external system, never the vault, never a
source file, never a repair.

``upsert_quality_run`` is deterministic + idempotent: an unchanged ``quality_run_id`` is a no-op (reused, no
duplicate). A genuinely new id (a changed target → changed ``input_digest``) supersedes ONLY prior
``draft``/``evaluated`` runs of the SAME ``(target_kind, target_id, policy_json)`` lineage — a quality-owned
row. It never marks a workflow/feedback/action-stage/review/source record stale, never executes, never repairs.

Every read method threads an optional ``conn=`` so a caller (e.g. the MCP broker's read-only snapshot) can pin
one connection. Rows are plain dicts.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .quality_models import EVENT_TYPES, QualityValidationError

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

# Prior runs in this lineage may be superseded by a re-evaluation.
_SUPERSEDABLE_STATES = ("draft", "evaluated")

_RUN_COLUMNS = (
    "quality_run_id", "target_kind", "target_id", "target_digest", "title", "status", "action_policy",
    "execution_policy", "review_policy", "source_policy", "citation_policy", "requires_operator_review",
    "evaluator_version", "created_by", "created_at", "updated_at", "request_digest", "input_digest",
    "output_digest", "policy_json", "finding_count", "risk_count", "warn_count", "info_count", "truncated",
    "metadata_json",
)

_FINDING_COLUMNS = (
    "finding_id", "quality_run_id", "finding_order", "finding_type", "severity", "target_kind", "target_id",
    "detail", "advice", "action_policy", "execution_policy", "review_policy", "requires_operator_review",
    "workflow_id", "stage_id", "stage_item_id", "feedback_id", "recommendation_id", "draft_id",
    "draft_section_id", "packet_id", "projection_id", "projection_item_id", "context_pack_id",
    "review_item_id", "claim_id", "citation_id", "decision_id", "preference_id", "open_loop_id", "source_id",
    "source_ref", "source_root_key", "rel_path", "note_rel_path", "review_state", "effective_state",
    "finding_digest", "created_at", "metadata_json",
)

_TARGET_COLUMNS = (
    "quality_target_id", "quality_run_id", "target_order", "target_kind", "target_id", "target_label",
    "workflow_id", "stage_id", "stage_item_id", "feedback_id", "recommendation_id", "draft_id",
    "draft_section_id", "packet_id", "projection_id", "projection_item_id", "context_pack_id",
    "review_item_id", "claim_id", "citation_id", "decision_id", "preference_id", "open_loop_id", "source_id",
    "source_ref", "source_root_key", "rel_path", "note_rel_path", "target_digest", "review_state",
    "effective_state", "created_at", "metadata_json",
)

_RECEIPT_COLUMNS = (
    "quality_receipt_id", "quality_run_id", "evaluator_version", "request_digest", "input_digest",
    "output_digest", "finding_count", "risk_count", "warn_count", "info_count", "dropped_count", "truncated",
    "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "quality_run_id", "event_type", "from_status", "to_status", "detail", "created_at",
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


class QualityRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write (quality-owned tables ONLY) ---------------------------------------------
    def upsert_quality_run(self, run: dict[str, Any], findings: list[dict[str, Any]],
                           targets: list[dict[str, Any]], receipt: dict[str, Any], *,
                           conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        rid = run.get("quality_run_id")
        tkind = run.get("target_kind")
        tid = run.get("target_id")
        if not rid or not tkind or not tid:
            raise QualityValidationError("quality_run_id_target_kind_and_id_required")
        policy = run.get("policy_json") or ""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_quality_runs WHERE quality_run_id=?", (rid,)
            ).fetchone()
            if exists is not None:
                return {"quality_run_id": rid, "created": False, "reused": True, "superseded": []}
            placeholders = ", ".join("?" for _ in _SUPERSEDABLE_STATES)
            priors = c.execute(
                "SELECT quality_run_id, status FROM assistant_quality_runs "
                "WHERE target_kind=? AND target_id=? AND IFNULL(policy_json,'')=? "
                f"AND quality_run_id!=? AND status IN ({placeholders})",
                (tkind, tid, policy, rid, *_SUPERSEDABLE_STATES),
            ).fetchall()
            for prior_id, prior_status in priors:
                c.execute(
                    "UPDATE assistant_quality_runs SET status='superseded', updated_at=? "
                    "WHERE quality_run_id=?", (now, prior_id))
                self._insert_event(c, prior_id, "superseded", from_status=prior_status,
                                   to_status="superseded", detail=rid, now=now)
            header = {**run, "status": run.get("status", "evaluated"), "created_at": now, "updated_at": now}
            self._insert(c, "assistant_quality_runs", _RUN_COLUMNS, header)
            for f in findings:
                self._insert(c, "assistant_quality_findings", _FINDING_COLUMNS, {**f, "created_at": now})
            for t in targets:
                self._insert(c, "assistant_quality_targets", _TARGET_COLUMNS, {**t, "created_at": now})
            self._insert(c, "assistant_quality_receipts", _RECEIPT_COLUMNS, {**receipt, "created_at": now})
            self._insert_event(c, rid, "created", from_status=None, to_status="draft",
                               detail=run.get("input_digest"), now=now)
            self._insert_event(c, rid, "evaluated", from_status="draft", to_status="evaluated",
                               detail=str(len(findings)), now=now)
            if findings:
                self._insert_event(c, rid, "finding_added", from_status="evaluated", to_status="evaluated",
                                   detail=str(len(findings)), now=now)
            return {"quality_run_id": rid, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors], "finding_count": len(findings)}

    def _insert(self, c: sqlite3.Connection, table: str, columns: tuple[str, ...],
                row: dict[str, Any]) -> None:
        cols = [col for col in columns if col in row]
        placeholders = ", ".join("?" for _ in cols)
        c.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608 (fixed cols)
            tuple(row.get(col) for col in cols),
        )

    def _insert_event(self, c: sqlite3.Connection, quality_run_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise QualityValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_quality_events "
            "(event_id, quality_run_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, quality_run_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    # ----- read --------------------------------------------------------------------------
    def get_quality_run(self, quality_run_id: str, *,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_RUN_COLUMNS)} FROM assistant_quality_runs WHERE quality_run_id=?",
                (quality_run_id,),
            ).fetchone()
        return dict(zip(_RUN_COLUMNS, row, strict=True)) if row else None

    def list_quality_runs(self, *, target_kind: str | None = None, target_id: str | None = None,
                          status: str | None = None, limit: int = _DEFAULT_LIMIT,
                          conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("target_kind", target_kind), ("target_id", target_id), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RUN_COLUMNS)} FROM assistant_quality_runs "  # noqa: S608
                f"{where}ORDER BY updated_at DESC, quality_run_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_RUN_COLUMNS, r, strict=True)) for r in rows]

    def list_findings(self, quality_run_id: str, *, finding_type: str | None = None,
                      severity: str | None = None, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["quality_run_id=?"]
        params: list[Any] = [quality_run_id]
        for col, val in (("finding_type", finding_type), ("severity", severity)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_FINDING_COLUMNS)} FROM assistant_quality_findings "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY finding_order ASC, finding_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_FINDING_COLUMNS, r, strict=True)) for r in rows]

    def list_targets(self, quality_run_id: str, *, limit: int = _MAX_LIMIT,
                     conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_TARGET_COLUMNS)} FROM assistant_quality_targets "
                "WHERE quality_run_id=? ORDER BY target_order ASC, quality_target_id ASC LIMIT ?",
                (quality_run_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_TARGET_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, quality_run_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_quality_receipts "
                "WHERE quality_run_id=? ORDER BY created_at DESC, quality_receipt_id DESC LIMIT ?",
                (quality_run_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, quality_run_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_quality_events "
                "WHERE quality_run_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (quality_run_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, *, target_kind: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("target_kind", target_kind), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_quality_runs {where}",  # noqa: S608
                params).fetchone()[0])

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over quality runs: counts by target kind, status, finding type, and severity."""
        with borrow_connection(conn, self.db_path) as c:
            by_kind = {r[0]: int(r[1]) for r in c.execute(
                "SELECT target_kind, COUNT(*) FROM assistant_quality_runs GROUP BY target_kind").fetchall()}
            by_status = {r[0]: int(r[1]) for r in c.execute(
                "SELECT status, COUNT(*) FROM assistant_quality_runs GROUP BY status").fetchall()}
            by_finding = {r[0]: int(r[1]) for r in c.execute(
                "SELECT finding_type, COUNT(*) FROM assistant_quality_findings "
                "GROUP BY finding_type").fetchall()}
            by_severity = {r[0]: int(r[1]) for r in c.execute(
                "SELECT severity, COUNT(*) FROM assistant_quality_findings GROUP BY severity").fetchall()}
            total = int(c.execute("SELECT COUNT(*) FROM assistant_quality_runs").fetchone()[0])
            findings = int(c.execute("SELECT COUNT(*) FROM assistant_quality_findings").fetchone()[0])
        return {"total_runs": total, "total_findings": findings, "by_target_kind": by_kind,
                "by_status": by_status, "by_finding_type": by_finding, "by_severity": by_severity}
