"""Sole reader/writer of the V105 review-overlay tables (N8C-9).

Writes only ``assistant_review_items`` / ``assistant_review_dispositions`` / ``assistant_review_events`` —
NEVER a source/import/claim/enrichment/context-pack/memory/decision table, never the vault. The overlay
points at existing advisory records; it never mutates them.

Two write paths, both explicit:
  * ``upsert_review_item`` — deterministic + idempotent. An unchanged ``review_item_id`` is a no-op
    (reused, no duplicate). A genuinely new id supersedes ONLY prior, un-disposed items of the SAME
    ``(target_kind, target_id, review_type)`` lineage (a changed ``target_digest``); items an operator has
    already disposed are left untouched (decisions are never silently overwritten).
  * ``record_disposition`` — APPEND-ONLY. It inserts one disposition row + one ``disposition_recorded``
    event and NEVER mutates the review item or any source table. The effective review state is COMPUTED
    from the item + its latest disposition (``effective_state_for_item``), never written back.

Every method threads an optional ``conn=`` so a caller (e.g. the MCP broker's read-only snapshot) can pin
one connection. Rows are plain dicts (column-tuple ``SELECT`` + ``dict(zip(..., strict=True))``).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .review_models import (
    EVENT_TYPES,
    REVIEW_NEEDS_REVIEW,
    REVIEW_SUPERSEDED,
    REVIEW_UNREVIEWED,
    ReviewValidationError,
    compute_disposition_id,
    disposition_states,
)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_ITEM_COLUMNS = (
    "review_item_id", "target_kind", "target_id", "target_digest", "target_state_digest", "review_type",
    "title", "summary", "review_state", "effective_state", "confidence", "priority", "stale",
    "superseded", "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
    "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
    "open_loop_id", "evidence_excerpt", "evidence_location", "source_digest", "card_digest",
    "created_by", "created_at", "updated_at", "metadata_json",
)

_DISPOSITION_COLUMNS = (
    "disposition_id", "review_item_id", "target_kind", "target_id", "disposition_type",
    "from_review_state", "to_review_state", "from_effective_state", "to_effective_state", "operator_id",
    "reason", "evidence_note", "created_by", "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "review_item_id", "event_type", "from_state", "to_state", "detail", "created_at",
)

# Prior items in this lifecycle set may be superseded by a rebuild; disposed items are protected.
_SUPERSEDABLE_STATES = (REVIEW_UNREVIEWED, REVIEW_NEEDS_REVIEW)


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


class ReviewRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write: review items -------------------------------------------------------------
    def upsert_review_item(self, row: dict[str, Any], *,
                           conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        review_item_id = row.get("review_item_id")
        target_kind = row.get("target_kind")
        target_id = row.get("target_id")
        review_type = row.get("review_type")
        if not review_item_id or not target_kind or not target_id or not review_type:
            raise ReviewValidationError("review_item_id_target_and_review_type_required")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_review_items WHERE review_item_id=?", (review_item_id,)
            ).fetchone()
            if exists is not None:
                return {"review_item_id": review_item_id, "created": False, "reused": True,
                        "superseded": []}
            # Lineage-scoped supersede: same target lineage, still un-disposed, different id (target
            # digest changed). Disposed items are protected so operator decisions are never overwritten.
            placeholders = ", ".join("?" for _ in _SUPERSEDABLE_STATES)
            priors = c.execute(
                "SELECT review_item_id, review_state FROM assistant_review_items "
                "WHERE target_kind=? AND target_id=? AND review_type=? AND review_item_id!=? "
                f"AND superseded=0 AND review_state IN ({placeholders})",
                (target_kind, target_id, review_type, review_item_id, *_SUPERSEDABLE_STATES),
            ).fetchall()
            for prior_id, prior_state in priors:
                c.execute(
                    "UPDATE assistant_review_items SET superseded=1, review_state=?, updated_at=? "
                    "WHERE review_item_id=?",
                    (REVIEW_SUPERSEDED, now, prior_id),
                )
                self._insert_event(c, prior_id, "marked_superseded", from_state=prior_state,
                                   to_state=REVIEW_SUPERSEDED, detail=review_item_id, now=now)
            insert_row = {**row, "created_at": now, "updated_at": now}
            cols = [col for col in _ITEM_COLUMNS if col in insert_row]
            placeholders = ", ".join("?" for _ in cols)
            c.execute(
                f"INSERT INTO assistant_review_items ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608
                tuple(insert_row.get(col) for col in cols),
            )
            self._insert_event(c, review_item_id, "created", from_state=None,
                               to_state=row.get("review_state"), detail=review_type, now=now)
            return {"review_item_id": review_item_id, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors]}

    # ----- write: dispositions (append-only) -----------------------------------------------
    def record_disposition(self, *, review_item_id: str, disposition_type: str,
                           operator_id: str | None = None, reason: str | None = None,
                           evidence_note: str | None = None, created_by: str = "cli",
                           conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Append one disposition + one event. Never mutates the review item or any source table.
        Raises ``ReviewValidationError`` if the review item does not exist."""
        to_review_state, to_effective_state = disposition_states(disposition_type)
        now = _now()
        nonce = _uuid()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            item = c.execute(
                "SELECT target_kind, target_id FROM assistant_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
            if item is None:
                raise ReviewValidationError(f"review_item_not_found:{review_item_id}")
            target_kind, target_id = item
            # The "from" states reflect the CURRENT effective state (item default or latest disposition).
            current = self._effective_state_for_item(c, review_item_id)
            disposition_id = compute_disposition_id(
                review_item_id, disposition_type, to_review_state, to_effective_state, operator_id,
                reason, nonce)
            drow = {
                "disposition_id": disposition_id, "review_item_id": review_item_id,
                "target_kind": target_kind, "target_id": target_id,
                "disposition_type": disposition_type,
                "from_review_state": current["effective_review_state"],
                "to_review_state": to_review_state,
                "from_effective_state": current["effective_state"],
                "to_effective_state": to_effective_state,
                "operator_id": operator_id,
                "reason": _bound(reason), "evidence_note": _bound(evidence_note),
                "created_by": created_by, "created_at": now, "metadata_json": None,
            }
            cols = list(_DISPOSITION_COLUMNS)
            placeholders = ", ".join("?" for _ in cols)
            c.execute(
                f"INSERT INTO assistant_review_dispositions ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608
                tuple(drow.get(col) for col in cols),
            )
            self._insert_event(c, review_item_id, "disposition_recorded",
                               from_state=current["effective_review_state"], to_state=to_review_state,
                               detail=disposition_type, now=now)
            return {"disposition_id": disposition_id, "review_item_id": review_item_id,
                    "disposition_type": disposition_type, "to_review_state": to_review_state,
                    "to_effective_state": to_effective_state, "recorded": True}

    def _insert_event(self, c: sqlite3.Connection, review_item_id: str, event_type: str, *,
                      from_state: str | None, to_state: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise ReviewValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_review_events "
            "(event_id, review_item_id, event_type, from_state, to_state, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, review_item_id, event_type, from_state, to_state, detail, now),
        )
        return event_id

    # ----- read (bounded) ------------------------------------------------------------------
    def get_review_item(self, review_item_id: str, *,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_ITEM_COLUMNS)} FROM assistant_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
        return dict(zip(_ITEM_COLUMNS, row, strict=True)) if row else None

    def list_review_items(self, *, target_kind: str | None = None, review_type: str | None = None,
                          review_state: str | None = None, effective_state: str | None = None,
                          include_superseded: bool = False, limit: int = _DEFAULT_LIMIT,
                          conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("target_kind", target_kind), ("review_type", review_type),
                         ("review_state", review_state), ("effective_state", effective_state)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        if not include_superseded:
            clauses.append("superseded=0")
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_ITEM_COLUMNS)} FROM assistant_review_items {where}"  # noqa: S608
                "ORDER BY updated_at DESC, review_item_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_ITEM_COLUMNS, r, strict=True)) for r in rows]

    def list_dispositions(self, review_item_id: str, *, limit: int = _MAX_LIMIT,
                          conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_DISPOSITION_COLUMNS)} FROM assistant_review_dispositions "
                "WHERE review_item_id=? ORDER BY created_at DESC, disposition_id DESC LIMIT ?",
                (review_item_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_DISPOSITION_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, review_item_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_review_events "
                "WHERE review_item_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (review_item_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    # ----- effective-state read model ------------------------------------------------------
    def get_effective_state(self, review_item_id: str, *,
                            conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            exists = c.execute(
                "SELECT 1 FROM assistant_review_items WHERE review_item_id=?", (review_item_id,)
            ).fetchone()
            if exists is None:
                return None
            return self._effective_state_for_item(c, review_item_id)

    def effective_state_for_target(self, target_kind: str, target_id: str, *,
                                   limit: int = _DEFAULT_LIMIT,
                                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            ids = [r[0] for r in c.execute(
                "SELECT review_item_id FROM assistant_review_items "
                "WHERE target_kind=? AND target_id=? ORDER BY updated_at DESC LIMIT ?",
                (target_kind, target_id, _clamp_limit(limit)),
            ).fetchall()]
            return [self._effective_state_for_item(c, rid) for rid in ids]

    def _effective_state_for_item(self, c: sqlite3.Connection, review_item_id: str) -> dict[str, Any]:
        """Effective state = latest disposition's target states if any disposition exists, else the review
        item's built defaults. Pure read — never writes."""
        item = c.execute(
            "SELECT review_state, effective_state FROM assistant_review_items WHERE review_item_id=?",
            (review_item_id,),
        ).fetchone()
        built_review = item[0] if item else None
        built_effective = item[1] if item else None
        latest = c.execute(
            "SELECT disposition_id, disposition_type, to_review_state, to_effective_state, created_at "
            "FROM assistant_review_dispositions WHERE review_item_id=? "
            "ORDER BY created_at DESC, disposition_id DESC LIMIT 1",
            (review_item_id,),
        ).fetchone()
        if latest is not None:
            return {
                "review_item_id": review_item_id,
                "built_review_state": built_review, "built_effective_state": built_effective,
                "effective_review_state": latest[2], "effective_state": latest[3],
                "latest_disposition_id": latest[0], "latest_disposition_type": latest[1],
                "disposed": True,
            }
        return {
            "review_item_id": review_item_id,
            "built_review_state": built_review, "built_effective_state": built_effective,
            "effective_review_state": built_review, "effective_state": built_effective,
            "latest_disposition_id": None, "latest_disposition_type": None, "disposed": False,
        }

    # ----- summary / counts ----------------------------------------------------------------
    def count(self, *, review_state: str | None = None, effective_state: str | None = None,
              include_superseded: bool = False, conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if review_state:
            clauses.append("review_state=?")
            params.append(review_state)
        if effective_state:
            clauses.append("effective_state=?")
            params.append(effective_state)
        if not include_superseded:
            clauses.append("superseded=0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_review_items {where}", params).fetchone()[0])  # noqa: S608

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over the review queue: counts by review_type / built review_state, plus
        disposed vs open (open = un-disposed, non-superseded). Pure read."""
        with borrow_connection(conn, self.db_path) as c:
            by_type = {r[0]: int(r[1]) for r in c.execute(
                "SELECT review_type, COUNT(*) FROM assistant_review_items WHERE superseded=0 "
                "GROUP BY review_type").fetchall()}
            by_state = {r[0]: int(r[1]) for r in c.execute(
                "SELECT review_state, COUNT(*) FROM assistant_review_items WHERE superseded=0 "
                "GROUP BY review_state").fetchall()}
            total = int(c.execute("SELECT COUNT(*) FROM assistant_review_items").fetchone()[0])
            superseded = int(c.execute(
                "SELECT COUNT(*) FROM assistant_review_items WHERE superseded=1").fetchone()[0])
            disposed = int(c.execute(
                "SELECT COUNT(DISTINCT review_item_id) FROM assistant_review_dispositions").fetchone()[0])
            dispositions = int(c.execute(
                "SELECT COUNT(*) FROM assistant_review_dispositions").fetchone()[0])
        return {
            "total_items": total, "active_items": total - superseded, "superseded_items": superseded,
            "disposed_items": disposed, "total_dispositions": dispositions,
            "by_review_type": by_type, "by_review_state": by_state,
        }


def _bound(text: str | None) -> str | None:
    from .memory_models import bound_text
    from .review_models import REASON_HARD_CAP
    return bound_text(text, REASON_HARD_CAP) if text else None
