"""Sole reader/writer of the V106 intelligence-projection tables (N8C-10).

Writes only ``assistant_intelligence_projections`` / ``assistant_intelligence_projection_items`` /
``assistant_intelligence_projection_receipts`` / ``assistant_intelligence_projection_events`` — NEVER a
source/import/claim/enrichment/context-pack/memory/decision table and NEVER a review table (claims,
dispositions, and events are read-only inputs), never the vault.

``upsert_projection`` is deterministic + idempotent: an unchanged ``projection_id`` is a no-op (reused,
no duplicate). A genuinely new id (a changed ``input_digest`` — e.g. a new disposition changed an item's
effective state) supersedes ONLY prior ``draft``/``built`` PROJECTIONS of the SAME ``(projection_type,
scope_json)`` lineage — a projection-owned row. It never marks a source-advisory or review record
stale/superseded.

Every read method threads an optional ``conn=`` so a caller (e.g. the MCP broker's read-only snapshot)
can pin one connection. Rows are plain dicts.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .intelligence_projection_models import EVENT_TYPES, ProjectionValidationError

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_PROJECTION_COLUMNS = (
    "projection_id", "projection_type", "title", "objective", "scope_json", "filter_policy_json",
    "budget_json", "status", "input_digest", "output_digest", "trusted_count", "candidate_count",
    "excluded_count", "stale_count", "superseded_count", "item_count", "truncated", "created_by",
    "created_at", "updated_at", "metadata_json",
)

_ITEM_COLUMNS = (
    "projection_item_id", "projection_id", "item_order", "target_kind", "target_id", "review_item_id",
    "disposition_id", "effective_state", "inclusion_state", "review_state", "title", "summary",
    "evidence_excerpt", "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id",
    "pack_item_id", "memory_node_id", "memory_mention_id", "compilation_id", "decision_id",
    "preference_id", "open_loop_id", "source_digest", "card_digest", "target_digest", "confidence",
    "priority", "token_estimate", "included", "exclusion_reason", "created_at", "metadata_json",
)

_RECEIPT_COLUMNS = (
    "projection_receipt_id", "projection_id", "builder_version", "input_digest", "output_digest",
    "filter_policy_json", "budget_json", "trusted_count", "candidate_count", "excluded_count",
    "stale_count", "superseded_count", "dropped_count", "truncated", "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "projection_id", "event_type", "from_status", "to_status", "detail", "created_at",
)

# Prior projections in this set may be superseded by a rebuild.
_SUPERSEDABLE_STATES = ("draft", "built")


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


class IntelligenceProjectionRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write --------------------------------------------------------------------------
    def upsert_projection(self, projection: dict[str, Any], items: list[dict[str, Any]],
                          receipt: dict[str, Any], *,
                          conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        pid = projection.get("projection_id")
        ptype = projection.get("projection_type")
        if not pid or not ptype:
            raise ProjectionValidationError("projection_id_and_type_required")
        scope = projection.get("scope_json") or ""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_intelligence_projections WHERE projection_id=?", (pid,)
            ).fetchone()
            if exists is not None:
                return {"projection_id": pid, "created": False, "reused": True, "superseded": []}
            # Lineage-scoped supersede: same (projection_type, scope), still draft/built, different id.
            placeholders = ", ".join("?" for _ in _SUPERSEDABLE_STATES)
            priors = c.execute(
                "SELECT projection_id, status FROM assistant_intelligence_projections "
                "WHERE projection_type=? AND IFNULL(scope_json,'')=? AND projection_id!=? "
                f"AND status IN ({placeholders})",
                (ptype, scope, pid, *_SUPERSEDABLE_STATES),
            ).fetchall()
            for prior_id, prior_status in priors:
                c.execute(
                    "UPDATE assistant_intelligence_projections SET status='superseded', updated_at=? "
                    "WHERE projection_id=?",
                    (now, prior_id),
                )
                self._insert_event(c, prior_id, "marked_superseded", from_status=prior_status,
                                   to_status="superseded", detail=pid, now=now)
            header = {**projection, "status": projection.get("status", "built"), "created_at": now,
                      "updated_at": now}
            self._insert(c, "assistant_intelligence_projections", _PROJECTION_COLUMNS, header)
            for it in items:
                self._insert(c, "assistant_intelligence_projection_items", _ITEM_COLUMNS,
                             {**it, "created_at": now})
            self._insert(c, "assistant_intelligence_projection_receipts", _RECEIPT_COLUMNS,
                         {**receipt, "created_at": now})
            self._insert_event(c, pid, "created", from_status=None, to_status="draft",
                               detail=projection.get("input_digest"), now=now)
            self._insert_event(c, pid, "built", from_status="draft", to_status="built",
                               detail=projection.get("output_digest"), now=now)
            return {"projection_id": pid, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors]}

    def _insert(self, c: sqlite3.Connection, table: str, columns: tuple[str, ...],
                row: dict[str, Any]) -> None:
        cols = [col for col in columns if col in row]
        placeholders = ", ".join("?" for _ in cols)
        c.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608 (fixed cols)
            tuple(row.get(col) for col in cols),
        )

    def _insert_event(self, c: sqlite3.Connection, projection_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise ProjectionValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_intelligence_projection_events "
            "(event_id, projection_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, projection_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    def mark_projection_stale_if_needed(self, projection_id: str, *, current_input_digest: str,
                                        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Explicit live check: if the projection's stored ``input_digest`` no longer matches the current
        inputs, mark it stale. No background scan exists. Projection-owned write only."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT status, input_digest FROM assistant_intelligence_projections "
                "WHERE projection_id=?", (projection_id,)
            ).fetchone()
            if row is None:
                return {"projection_id": projection_id, "found": False}
            status, stored = row
            drifted = stored != current_input_digest
            if drifted and status not in ("stale", "superseded"):
                c.execute(
                    "UPDATE assistant_intelligence_projections SET status='stale', updated_at=? "
                    "WHERE projection_id=?", (now, projection_id))
                self._insert_event(c, projection_id, "marked_stale", from_status=status,
                                   to_status="stale", detail="input_drift", now=now)
            return {"projection_id": projection_id, "found": True, "stale": drifted}

    # ----- read (bounded) -----------------------------------------------------------------
    def get_projection(self, projection_id: str, *,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_PROJECTION_COLUMNS)} FROM assistant_intelligence_projections "
                "WHERE projection_id=?", (projection_id,)
            ).fetchone()
        return dict(zip(_PROJECTION_COLUMNS, row, strict=True)) if row else None

    def list_projections(self, *, projection_type: str | None = None, status: str | None = None,
                         limit: int = _DEFAULT_LIMIT,
                         conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("projection_type", projection_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_PROJECTION_COLUMNS)} FROM assistant_intelligence_projections "  # noqa: S608
                f"{where}ORDER BY updated_at DESC, projection_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_PROJECTION_COLUMNS, r, strict=True)) for r in rows]

    def list_projection_items(self, projection_id: str, *, inclusion_state: str | None = None,
                              included_only: bool = False, limit: int = _MAX_LIMIT,
                              conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["projection_id=?"]
        params: list[Any] = [projection_id]
        if inclusion_state:
            clauses.append("inclusion_state=?")
            params.append(inclusion_state)
        if included_only:
            clauses.append("included=1")
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_ITEM_COLUMNS)} FROM assistant_intelligence_projection_items "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY item_order ASC, projection_item_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_ITEM_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, projection_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_intelligence_projection_receipts "
                "WHERE projection_id=? ORDER BY created_at DESC, projection_receipt_id DESC LIMIT ?",
                (projection_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, projection_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_intelligence_projection_events "
                "WHERE projection_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (projection_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, *, projection_type: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("projection_type", projection_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_intelligence_projections {where}",  # noqa: S608
                params).fetchone()[0])

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over projections: counts by type and status. Pure read."""
        with borrow_connection(conn, self.db_path) as c:
            by_type = {r[0]: int(r[1]) for r in c.execute(
                "SELECT projection_type, COUNT(*) FROM assistant_intelligence_projections "
                "GROUP BY projection_type").fetchall()}
            by_status = {r[0]: int(r[1]) for r in c.execute(
                "SELECT status, COUNT(*) FROM assistant_intelligence_projections "
                "GROUP BY status").fetchall()}
            total = int(c.execute(
                "SELECT COUNT(*) FROM assistant_intelligence_projections").fetchone()[0])
            items = int(c.execute(
                "SELECT COUNT(*) FROM assistant_intelligence_projection_items").fetchone()[0])
        return {"total_projections": total, "total_items": items, "by_projection_type": by_type,
                "by_status": by_status}
