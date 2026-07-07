"""Sole reader/writer of the V110 action-stage tables (N8C-19).

Writes ONLY ``assistant_action_stages`` / ``assistant_action_stage_items`` /
``assistant_action_stage_citations`` / ``assistant_action_stage_receipts`` / ``assistant_action_stage_events``
— NEVER a workflow, feedback, review, source, packet, draft, projection, context-pack, claim, memory,
decision, preference, or open-loop table (all read-only inputs), never a review disposition, never an
external system, never the vault, never a source file.

``upsert_stage`` is deterministic + idempotent: an unchanged ``stage_id`` is a no-op (reused, no duplicate).
A genuinely new id (changed workflow context / feedback recommendations → changed ``input_digest``)
supersedes ONLY prior ``draft``/``staged`` stages of the SAME ``(stage_type, workflow_type, request_digest,
stage_policy_json)`` lineage — a stage-owned row. It never marks a workflow/feedback/review/source record
stale, never executes, and never touches an external system.

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

from .action_stage_models import EVENT_TYPES, ActionStageValidationError

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

# Prior stages in this lineage may be superseded by a rebuild.
_SUPERSEDABLE_STATES = ("draft", "staged")

_STAGE_COLUMNS = (
    "stage_id", "stage_type", "workflow_type", "workflow_id", "title", "status", "action_policy",
    "execution_policy", "workflow_policy", "review_policy", "citation_policy", "source_policy",
    "requires_operator_review", "created_by", "created_at", "updated_at", "request_digest",
    "source_context_digest", "input_digest", "output_digest", "stage_policy_json", "budget_json",
    "item_count", "blocked_count", "citation_count", "truncated", "metadata_json",
)

_ITEM_COLUMNS = (
    "stage_item_id", "stage_id", "item_order", "action_kind", "staged_state", "source_section", "title",
    "detail", "block_reason", "execution_status", "external_system", "external_ref",
    "requires_operator_review", "target_kind", "target_id", "workflow_id", "draft_id", "packet_id",
    "projection_item_id", "context_pack_id", "memory_node_id", "decision_id", "preference_id",
    "open_loop_id", "review_item_id", "claim_id", "citation_id", "feedback_id", "recommendation_id",
    "source_id", "source_ref", "source_root_key", "rel_path", "note_rel_path", "review_state",
    "effective_state", "item_digest", "created_at", "metadata_json",
)

_CITATION_COLUMNS = (
    "stage_citation_id", "stage_id", "stage_item_id", "citation_order", "citation_type", "target_kind",
    "target_id", "workflow_id", "draft_id", "packet_id", "projection_item_id", "context_pack_id",
    "memory_node_id", "decision_id", "preference_id", "open_loop_id", "review_item_id", "claim_id",
    "citation_id", "feedback_id", "recommendation_id", "source_id", "source_ref", "source_root_key",
    "rel_path", "note_rel_path", "citation_label", "created_at", "metadata_json",
)

_RECEIPT_COLUMNS = (
    "stage_receipt_id", "stage_id", "builder_version", "request_digest", "source_context_digest",
    "input_digest", "output_digest", "item_count", "blocked_count", "citation_count", "dropped_count",
    "truncated", "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "stage_id", "event_type", "from_status", "to_status", "detail", "created_at",
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


class ActionStageRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write (action-stage-owned tables ONLY) ----------------------------------------
    def upsert_stage(self, stage: dict[str, Any], items: list[dict[str, Any]],
                     citations: list[dict[str, Any]], receipt: dict[str, Any], *,
                     conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        sid = stage.get("stage_id")
        stype = stage.get("stage_type")
        if not sid or not stype:
            raise ActionStageValidationError("stage_id_and_type_required")
        wtype = stage.get("workflow_type") or ""
        req = stage.get("request_digest") or ""
        policy = stage.get("stage_policy_json") or ""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_action_stages WHERE stage_id=?", (sid,)
            ).fetchone()
            if exists is not None:
                return {"stage_id": sid, "created": False, "reused": True, "superseded": []}
            # Lineage-scoped supersede: same (stage_type, workflow_type, request_digest, policy), still
            # draft/staged, new id.
            placeholders = ", ".join("?" for _ in _SUPERSEDABLE_STATES)
            priors = c.execute(
                "SELECT stage_id, status FROM assistant_action_stages "
                "WHERE stage_type=? AND IFNULL(workflow_type,'')=? AND IFNULL(request_digest,'')=? "
                f"AND IFNULL(stage_policy_json,'')=? AND stage_id!=? AND status IN ({placeholders})",
                (stype, wtype, req, policy, sid, *_SUPERSEDABLE_STATES),
            ).fetchall()
            for prior_id, prior_status in priors:
                c.execute(
                    "UPDATE assistant_action_stages SET status='superseded', updated_at=? "
                    "WHERE stage_id=?", (now, prior_id))
                self._insert_event(c, prior_id, "superseded", from_status=prior_status,
                                   to_status="superseded", detail=sid, now=now)
            header = {**stage, "status": stage.get("status", "staged"), "created_at": now,
                      "updated_at": now}
            self._insert(c, "assistant_action_stages", _STAGE_COLUMNS, header)
            for it in items:
                self._insert(c, "assistant_action_stage_items", _ITEM_COLUMNS, {**it, "created_at": now})
            for ci in citations:
                self._insert(c, "assistant_action_stage_citations", _CITATION_COLUMNS,
                             {**ci, "created_at": now})
            self._insert(c, "assistant_action_stage_receipts", _RECEIPT_COLUMNS,
                         {**receipt, "created_at": now})
            self._insert_event(c, sid, "created", from_status=None, to_status="draft",
                               detail=stage.get("input_digest"), now=now)
            self._insert_event(c, sid, "staged", from_status="draft", to_status="staged",
                               detail=str(len(items)), now=now)
            if citations:
                self._insert_event(c, sid, "citation_added", from_status="staged", to_status="staged",
                                   detail=str(len(citations)), now=now)
            return {"stage_id": sid, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors], "item_count": len(items),
                    "citation_count": len(citations)}

    def _insert(self, c: sqlite3.Connection, table: str, columns: tuple[str, ...],
                row: dict[str, Any]) -> None:
        cols = [col for col in columns if col in row]
        placeholders = ", ".join("?" for _ in cols)
        c.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608 (fixed cols)
            tuple(row.get(col) for col in cols),
        )

    def _insert_event(self, c: sqlite3.Connection, stage_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise ActionStageValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_action_stage_events "
            "(event_id, stage_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, stage_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    # ----- read --------------------------------------------------------------------------
    def get_stage(self, stage_id: str, *,
                  conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_STAGE_COLUMNS)} FROM assistant_action_stages WHERE stage_id=?",
                (stage_id,),
            ).fetchone()
        return dict(zip(_STAGE_COLUMNS, row, strict=True)) if row else None

    def list_stages(self, *, stage_type: str | None = None, status: str | None = None,
                    workflow_type: str | None = None, limit: int = _DEFAULT_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("stage_type", stage_type), ("status", status),
                         ("workflow_type", workflow_type)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_STAGE_COLUMNS)} FROM assistant_action_stages "  # noqa: S608
                f"{where}ORDER BY updated_at DESC, stage_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_STAGE_COLUMNS, r, strict=True)) for r in rows]

    def list_items(self, stage_id: str, *, staged_state: str | None = None, limit: int = _MAX_LIMIT,
                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["stage_id=?"]
        params: list[Any] = [stage_id]
        if staged_state:
            clauses.append("staged_state=?")
            params.append(staged_state)
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_ITEM_COLUMNS)} FROM assistant_action_stage_items "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY item_order ASC, stage_item_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_ITEM_COLUMNS, r, strict=True)) for r in rows]

    def list_citations(self, stage_id: str, *, stage_item_id: str | None = None, limit: int = _MAX_LIMIT,
                       conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["stage_id=?"]
        params: list[Any] = [stage_id]
        if stage_item_id:
            clauses.append("stage_item_id=?")
            params.append(stage_item_id)
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_CITATION_COLUMNS)} FROM assistant_action_stage_citations "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY stage_item_id ASC, citation_order ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_CITATION_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, stage_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_action_stage_receipts "
                "WHERE stage_id=? ORDER BY created_at DESC, stage_receipt_id DESC LIMIT ?",
                (stage_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, stage_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_action_stage_events "
                "WHERE stage_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (stage_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, *, stage_type: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("stage_type", stage_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_action_stages {where}",  # noqa: S608
                params).fetchone()[0])

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over stages: counts by type and status + total items/blocked/citations."""
        with borrow_connection(conn, self.db_path) as c:
            by_type = {r[0]: int(r[1]) for r in c.execute(
                "SELECT stage_type, COUNT(*) FROM assistant_action_stages GROUP BY stage_type").fetchall()}
            by_status = {r[0]: int(r[1]) for r in c.execute(
                "SELECT status, COUNT(*) FROM assistant_action_stages GROUP BY status").fetchall()}
            total = int(c.execute("SELECT COUNT(*) FROM assistant_action_stages").fetchone()[0])
            items = int(c.execute("SELECT COUNT(*) FROM assistant_action_stage_items").fetchone()[0])
            blocked = int(c.execute(
                "SELECT COUNT(*) FROM assistant_action_stage_items WHERE staged_state='blocked'").fetchone()[0])
            cits = int(c.execute(
                "SELECT COUNT(*) FROM assistant_action_stage_citations").fetchone()[0])
        return {"total_stages": total, "total_items": items, "total_blocked": blocked,
                "total_citations": cits, "by_stage_type": by_type, "by_status": by_status}
