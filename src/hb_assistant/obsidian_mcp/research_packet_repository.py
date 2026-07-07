"""Sole reader/writer of the V107 research-packet tables (N8C-11).

Writes only ``assistant_research_packets`` / ``assistant_research_packet_items`` /
``assistant_research_packet_citations`` / ``assistant_research_packet_receipts`` /
``assistant_research_packet_events`` — NEVER a source/import/claim/enrichment/context-pack/memory/decision
table, NEVER a review table, and NEVER a projection table (all of those are read-only inputs), never the
vault.

``upsert_packet`` is deterministic + idempotent: an unchanged ``packet_id`` is a no-op (reused, no
duplicate). A genuinely new id (a changed ``input_digest`` — e.g. a new projection or a changed effective
state / citation digest) supersedes ONLY prior ``draft``/``built`` PACKETS of the SAME ``(packet_type,
projection_id, scope_json)`` lineage — a packet-owned row. It never marks a projection, review, or
source-advisory record stale/superseded.

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

from .research_packet_models import EVENT_TYPES, ResearchPacketValidationError

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_PACKET_COLUMNS = (
    "packet_id", "packet_type", "title", "objective", "question", "scope_json", "answer_contract_json",
    "budget_json", "status", "created_by", "created_at", "updated_at", "projection_id", "input_digest",
    "output_digest", "answer_contract_digest", "trusted_count", "candidate_count", "excluded_count",
    "citation_count", "open_question_count", "item_count", "truncated", "metadata_json",
)

_ITEM_COLUMNS = (
    "packet_item_id", "packet_id", "projection_id", "projection_item_id", "item_order", "target_kind",
    "target_id", "review_item_id", "effective_state", "inclusion_state", "answer_role", "title", "summary",
    "evidence_excerpt", "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
    "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id", "open_loop_id",
    "source_digest", "card_digest", "target_digest", "confidence", "priority", "token_estimate", "included",
    "exclusion_reason", "citation_ids_json", "created_at", "metadata_json",
)

_CITATION_COLUMNS = (
    "citation_id", "packet_id", "packet_item_id", "citation_order", "citation_type", "label", "target_kind",
    "target_id", "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
    "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id", "open_loop_id",
    "review_item_id", "projection_item_id", "source_digest", "card_digest", "target_digest",
    "evidence_excerpt", "evidence_location", "confidence", "review_state", "effective_state",
    "inclusion_state", "created_at", "metadata_json",
)

_RECEIPT_COLUMNS = (
    "packet_receipt_id", "packet_id", "builder_version", "projection_id", "input_digest", "output_digest",
    "answer_contract_digest", "budget_json", "trusted_count", "candidate_count", "excluded_count",
    "citation_count", "open_question_count", "dropped_count", "truncated", "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "packet_id", "event_type", "from_status", "to_status", "detail", "created_at",
)

# Prior packets in this lineage may be superseded by a rebuild.
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


class ResearchPacketRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write --------------------------------------------------------------------------
    def upsert_packet(self, packet: dict[str, Any], items: list[dict[str, Any]],
                      citations: list[dict[str, Any]], receipt: dict[str, Any], *,
                      conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        pid = packet.get("packet_id")
        ptype = packet.get("packet_type")
        if not pid or not ptype:
            raise ResearchPacketValidationError("packet_id_and_type_required")
        projection_id = packet.get("projection_id") or ""
        scope = packet.get("scope_json") or ""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_research_packets WHERE packet_id=?", (pid,)
            ).fetchone()
            if exists is not None:
                return {"packet_id": pid, "created": False, "reused": True, "superseded": []}
            # Lineage-scoped supersede: same (packet_type, projection_id, scope), still draft/built, new id.
            placeholders = ", ".join("?" for _ in _SUPERSEDABLE_STATES)
            priors = c.execute(
                "SELECT packet_id, status FROM assistant_research_packets "
                "WHERE packet_type=? AND IFNULL(projection_id,'')=? AND IFNULL(scope_json,'')=? "
                f"AND packet_id!=? AND status IN ({placeholders})",
                (ptype, projection_id, scope, pid, *_SUPERSEDABLE_STATES),
            ).fetchall()
            for prior_id, prior_status in priors:
                c.execute(
                    "UPDATE assistant_research_packets SET status='superseded', updated_at=? "
                    "WHERE packet_id=?", (now, prior_id))
                self._insert_event(c, prior_id, "marked_superseded", from_status=prior_status,
                                   to_status="superseded", detail=pid, now=now)
            header = {**packet, "status": packet.get("status", "built"), "created_at": now,
                      "updated_at": now}
            self._insert(c, "assistant_research_packets", _PACKET_COLUMNS, header)
            for it in items:
                self._insert(c, "assistant_research_packet_items", _ITEM_COLUMNS, {**it, "created_at": now})
            for ci in citations:
                self._insert(c, "assistant_research_packet_citations", _CITATION_COLUMNS,
                             {**ci, "created_at": now})
            self._insert(c, "assistant_research_packet_receipts", _RECEIPT_COLUMNS,
                         {**receipt, "created_at": now})
            self._insert_event(c, pid, "created", from_status=None, to_status="draft",
                               detail=packet.get("input_digest"), now=now)
            self._insert_event(c, pid, "built", from_status="draft", to_status="built",
                               detail=packet.get("output_digest"), now=now)
            return {"packet_id": pid, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors]}

    def _insert(self, c: sqlite3.Connection, table: str, columns: tuple[str, ...],
                row: dict[str, Any]) -> None:
        cols = [col for col in columns if col in row]
        placeholders = ", ".join("?" for _ in cols)
        c.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608 (fixed cols)
            tuple(row.get(col) for col in cols),
        )

    def _insert_event(self, c: sqlite3.Connection, packet_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise ResearchPacketValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_research_packet_events "
            "(event_id, packet_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, packet_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    def mark_research_packet_stale_if_needed(self, packet_id: str, *, current_input_digest: str,
                                             conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Explicit live check: if the packet's stored ``input_digest`` no longer matches the current
        inputs, mark it stale. No background scan exists. Packet-owned write only."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT status, input_digest FROM assistant_research_packets WHERE packet_id=?",
                (packet_id,)
            ).fetchone()
            if row is None:
                return {"packet_id": packet_id, "found": False}
            status, stored = row
            drifted = stored != current_input_digest
            if drifted and status not in ("stale", "superseded"):
                c.execute(
                    "UPDATE assistant_research_packets SET status='stale', updated_at=? "
                    "WHERE packet_id=?", (now, packet_id))
                self._insert_event(c, packet_id, "marked_stale", from_status=status, to_status="stale",
                                   detail="input_drift", now=now)
            return {"packet_id": packet_id, "found": True, "stale": drifted}

    # ----- read (bounded) -----------------------------------------------------------------
    def get_research_packet(self, packet_id: str, *,
                            conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_PACKET_COLUMNS)} FROM assistant_research_packets "
                "WHERE packet_id=?", (packet_id,)
            ).fetchone()
        return dict(zip(_PACKET_COLUMNS, row, strict=True)) if row else None

    def list_research_packets(self, *, packet_type: str | None = None, status: str | None = None,
                              limit: int = _DEFAULT_LIMIT,
                              conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("packet_type", packet_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_PACKET_COLUMNS)} FROM assistant_research_packets "  # noqa: S608
                f"{where}ORDER BY updated_at DESC, packet_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_PACKET_COLUMNS, r, strict=True)) for r in rows]

    def list_research_packet_items(self, packet_id: str, *, answer_role: str | None = None,
                                   included_only: bool = False, limit: int = _MAX_LIMIT,
                                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["packet_id=?"]
        params: list[Any] = [packet_id]
        if answer_role:
            clauses.append("answer_role=?")
            params.append(answer_role)
        if included_only:
            clauses.append("included=1")
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_ITEM_COLUMNS)} FROM assistant_research_packet_items "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY item_order ASC, packet_item_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_ITEM_COLUMNS, r, strict=True)) for r in rows]

    def list_research_packet_citations(self, packet_id: str, *, packet_item_id: str | None = None,
                                       limit: int = _MAX_LIMIT,
                                       conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["packet_id=?"]
        params: list[Any] = [packet_id]
        if packet_item_id:
            clauses.append("packet_item_id=?")
            params.append(packet_item_id)
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_CITATION_COLUMNS)} FROM assistant_research_packet_citations "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY citation_order ASC, citation_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_CITATION_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, packet_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_research_packet_receipts "
                "WHERE packet_id=? ORDER BY created_at DESC, packet_receipt_id DESC LIMIT ?",
                (packet_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, packet_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_research_packet_events "
                "WHERE packet_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (packet_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, *, packet_type: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("packet_type", packet_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_research_packets {where}",  # noqa: S608
                params).fetchone()[0])

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over packets: counts by type and status + total items/citations. Pure read."""
        with borrow_connection(conn, self.db_path) as c:
            by_type = {r[0]: int(r[1]) for r in c.execute(
                "SELECT packet_type, COUNT(*) FROM assistant_research_packets "
                "GROUP BY packet_type").fetchall()}
            by_status = {r[0]: int(r[1]) for r in c.execute(
                "SELECT status, COUNT(*) FROM assistant_research_packets GROUP BY status").fetchall()}
            total = int(c.execute("SELECT COUNT(*) FROM assistant_research_packets").fetchone()[0])
            items = int(c.execute(
                "SELECT COUNT(*) FROM assistant_research_packet_items").fetchone()[0])
            citations = int(c.execute(
                "SELECT COUNT(*) FROM assistant_research_packet_citations").fetchone()[0])
        return {"total_packets": total, "total_items": items, "total_citations": citations,
                "by_packet_type": by_type, "by_status": by_status}
