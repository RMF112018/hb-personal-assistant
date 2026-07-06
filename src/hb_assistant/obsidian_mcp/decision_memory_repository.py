"""Sole reader/writer of the V104 decision/preference/open-loop tables (N8C-8).

Writes only ``assistant_decision_records`` / ``assistant_preference_records`` /
``assistant_open_loop_records`` / ``assistant_decision_memory_events`` — never a source/import/claim/
enrichment/context-pack/memory table, never the vault. Deterministic upsert semantics make re-running the
extractor idempotent:
  * a record with an unchanged deterministic id is a no-op (reused — no duplicate, no supersede);
  * a genuinely new record id supersedes ONLY prior ``candidate`` rows with the SAME ``identity_key``
    (same subject+action+lineage) — a changed evidence digest for that lineage. Independent sources get
    a different ``identity_key`` and coexist (they never auto-obsolete each other).

Every method threads an optional ``conn=`` so a caller can pin one read-only connection. Rows are plain
dicts (column-tuple ``SELECT`` + ``dict(zip(..., strict=True))``), following the N8C-4/5/6/7 conventions.
N8C-8 implements only creation, explicit stale, and lineage-scoped supersede — no accept/reject/close/
reopen operator-disposition workflow.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .decision_memory_models import (
    EVENT_TYPES,
    KIND_DECISION,
    KIND_OPEN_LOOP,
    KIND_PREFERENCE,
    STATUS_STALE,
    STATUS_SUPERSEDED,
    DecisionMemoryValidationError,
)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_DECISION_COLUMNS = (
    "decision_id", "identity_key", "decision_type", "decision_text", "normalized_subject",
    "normalized_decision", "domain", "status", "review_state", "confidence", "source_id",
    "note_rel_path", "claim_id", "memory_node_id", "memory_mention_id", "compilation_id", "pack_id",
    "pack_item_id", "receipt_id", "evidence_excerpt", "evidence_location", "source_digest",
    "card_digest", "observed_at", "decided_at", "valid_from", "valid_until", "created_by", "created_at",
    "updated_at", "metadata_json",
)

_PREFERENCE_COLUMNS = (
    "preference_id", "identity_key", "preference_type", "preference_text", "normalized_subject",
    "normalized_preference", "domain", "strength", "status", "review_state", "confidence", "source_id",
    "note_rel_path", "claim_id", "memory_node_id", "memory_mention_id", "compilation_id", "pack_id",
    "pack_item_id", "receipt_id", "evidence_excerpt", "evidence_location", "source_digest",
    "card_digest", "observed_at", "valid_from", "valid_until", "created_by", "created_at", "updated_at",
    "metadata_json",
)

_OPEN_LOOP_COLUMNS = (
    "open_loop_id", "identity_key", "open_loop_type", "open_loop_text", "normalized_subject",
    "normalized_action", "domain", "status", "review_state", "priority", "confidence", "source_id",
    "note_rel_path", "claim_id", "memory_node_id", "memory_mention_id", "compilation_id", "pack_id",
    "pack_item_id", "receipt_id", "evidence_excerpt", "evidence_location", "source_digest",
    "card_digest", "observed_at", "due_at", "stale_after", "owner_hint", "created_by", "created_at",
    "updated_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "record_kind", "record_id", "event_type", "from_status", "to_status", "detail",
    "created_at",
)

# Per-kind table wiring: (table, pk column, column tuple).
_SPEC = {
    KIND_DECISION: ("assistant_decision_records", "decision_id", _DECISION_COLUMNS),
    KIND_PREFERENCE: ("assistant_preference_records", "preference_id", _PREFERENCE_COLUMNS),
    KIND_OPEN_LOOP: ("assistant_open_loop_records", "open_loop_id", _OPEN_LOOP_COLUMNS),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


def _uuid() -> str:
    import uuid
    return uuid.uuid4().hex


class DecisionMemoryRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write ---------------------------------------------------------------------------
    def upsert_decision(self, row: dict[str, Any], *,
                        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        return self._upsert(KIND_DECISION, row, conn=conn)

    def upsert_preference(self, row: dict[str, Any], *,
                          conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        return self._upsert(KIND_PREFERENCE, row, conn=conn)

    def upsert_open_loop(self, row: dict[str, Any], *,
                         conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        return self._upsert(KIND_OPEN_LOOP, row, conn=conn)

    def _upsert(self, kind: str, row: dict[str, Any], *,
                conn: sqlite3.Connection | None) -> dict[str, Any]:
        table, pk, columns = _SPEC[kind]
        record_id = row.get(pk)
        identity_key = row.get("identity_key")
        if not record_id or not identity_key:
            raise DecisionMemoryValidationError(f"{pk}_and_identity_key_required")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                f"SELECT 1 FROM {table} WHERE {pk}=?", (record_id,)  # noqa: S608 (table from fixed map)
            ).fetchone()
            if exists is not None:
                return {"record_id": record_id, "created": False, "reused": True}
            # Lineage-scoped supersede: same identity_key, still candidate, different id → the evidence
            # for this lineage changed. Independent lineages have a different identity_key → untouched.
            priors = c.execute(
                f"SELECT {pk}, status FROM {table} WHERE identity_key=? AND {pk}!=? "  # noqa: S608
                "AND status='candidate'",
                (identity_key, record_id),
            ).fetchall()
            for prior_id, prior_status in priors:
                c.execute(
                    f"UPDATE {table} SET status='{STATUS_SUPERSEDED}', updated_at=? WHERE {pk}=?",  # noqa: S608
                    (now, prior_id),
                )
                self._insert_event(c, kind, prior_id, "superseded", from_status=prior_status,
                                   to_status=STATUS_SUPERSEDED, detail=record_id, now=now)
            insert_row = {**row, "created_by": row.get("created_by"), "created_at": now,
                          "updated_at": now}
            cols = [col for col in columns if col in insert_row]
            placeholders = ", ".join("?" for _ in cols)
            c.execute(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608
                tuple(insert_row.get(col) for col in cols),
            )
            self._insert_event(c, kind, record_id, "created", from_status=None,
                               to_status=row.get("status"), detail=row.get("identity_key"), now=now)
            return {"record_id": record_id, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors]}

    def _insert_event(self, c: sqlite3.Connection, kind: str, record_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise DecisionMemoryValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_decision_memory_events "
            "(event_id, record_kind, record_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (event_id, kind, record_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    def mark_open_loop_stale(self, open_loop_id: str, *, detail: str | None = None,
                             conn: sqlite3.Connection | None = None) -> bool:
        """Explicitly mark an open loop stale + log the event. No automatic/background stale scan."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT status FROM assistant_open_loop_records WHERE open_loop_id=?", (open_loop_id,)
            ).fetchone()
            if row is None:
                return False
            prev = row[0]
            if prev == STATUS_STALE:
                return True
            c.execute("UPDATE assistant_open_loop_records SET status=?, updated_at=? WHERE open_loop_id=?",
                      (STATUS_STALE, now, open_loop_id))
            self._insert_event(c, KIND_OPEN_LOOP, open_loop_id, "marked_stale", from_status=prev,
                               to_status=STATUS_STALE, detail=detail, now=now)
        return True

    # ----- read (bounded) ------------------------------------------------------------------
    def get_decision(self, decision_id: str, *,
                     conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        return self._get(KIND_DECISION, decision_id, conn=conn)

    def get_preference(self, preference_id: str, *,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        return self._get(KIND_PREFERENCE, preference_id, conn=conn)

    def get_open_loop(self, open_loop_id: str, *,
                      conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        return self._get(KIND_OPEN_LOOP, open_loop_id, conn=conn)

    def _get(self, kind: str, record_id: str, *,
             conn: sqlite3.Connection | None) -> dict[str, Any] | None:
        table, pk, columns = _SPEC[kind]
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(columns)} FROM {table} WHERE {pk}=?",  # noqa: S608
                (record_id,),
            ).fetchone()
        return dict(zip(columns, row, strict=True)) if row else None

    def list_decisions(self, *, decision_type: str | None = None, status: str | None = None,
                       limit: int = _DEFAULT_LIMIT,
                       conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        return self._list(KIND_DECISION, {"decision_type": decision_type, "status": status},
                          limit=limit, conn=conn)

    def list_preferences(self, *, preference_type: str | None = None, status: str | None = None,
                         limit: int = _DEFAULT_LIMIT,
                         conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        return self._list(KIND_PREFERENCE, {"preference_type": preference_type, "status": status},
                          limit=limit, conn=conn)

    def list_open_loops(self, *, open_loop_type: str | None = None, status: str | None = None,
                        limit: int = _DEFAULT_LIMIT,
                        conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        return self._list(KIND_OPEN_LOOP, {"open_loop_type": open_loop_type, "status": status},
                         limit=limit, conn=conn)

    def _list(self, kind: str, filters: dict[str, str | None], *, limit: int,
              conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
        table, pk, columns = _SPEC[kind]
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in filters.items():
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(columns)} FROM {table} {where}"  # noqa: S608
                f"ORDER BY updated_at DESC, {pk} DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(columns, r, strict=True)) for r in rows]

    def list_events(self, record_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_decision_memory_events "
                "WHERE record_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (record_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, kind: str, *, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        table, _pk, _cols = _SPEC[kind]
        where = "WHERE status=?" if status else ""
        params = (status,) if status else ()
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM {table} {where}", params).fetchone()[0])  # noqa: S608
