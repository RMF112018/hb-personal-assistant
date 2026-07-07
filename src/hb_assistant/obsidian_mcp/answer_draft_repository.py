"""Sole reader/writer of the V108 answer-draft tables (N8C-14).

Writes only ``assistant_answer_drafts`` / ``assistant_answer_draft_sections`` /
``assistant_answer_draft_citations`` / ``assistant_answer_draft_receipts`` / ``assistant_answer_draft_events``
— NEVER a packet, projection, review, source, import, claim, enrichment, context-pack, memory, or decision
table (all of those are read-only inputs), never the vault, never a source file.

``upsert_draft`` is deterministic + idempotent: an unchanged ``draft_id`` is a no-op (reused, no duplicate).
A genuinely new id (a changed ``input_digest`` — e.g. a rebuilt packet, a changed effective state, or changed
citation lineage) supersedes ONLY prior ``draft``/``built`` DRAFTS of the SAME ``(draft_type, packet_id,
draft_policy_json)`` lineage — a draft-owned row. It never marks a packet, projection, review, or source
record stale/superseded.

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

from .answer_draft_models import EVENT_TYPES, AnswerDraftValidationError

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_DRAFT_COLUMNS = (
    "draft_id", "draft_type", "title", "objective", "question", "packet_id", "packet_type",
    "answer_contract_digest", "draft_policy_json", "budget_json", "status", "created_by", "created_at",
    "updated_at", "input_digest", "output_digest", "trusted_section_count", "candidate_section_count",
    "caveat_count", "citation_count", "open_question_count", "excluded_count", "section_count", "truncated",
    "metadata_json",
)

_SECTION_COLUMNS = (
    "draft_section_id", "draft_id", "packet_id", "packet_item_id", "section_order", "section_type", "heading",
    "section_body", "review_label", "effective_state", "inclusion_state", "answer_role", "confidence",
    "citation_ids_json", "source_refs_json", "trusted", "candidate", "open_question", "excluded",
    "token_estimate", "char_count", "created_at", "metadata_json",
)

_CITATION_COLUMNS = (
    "draft_citation_id", "draft_id", "draft_section_id", "packet_id", "packet_citation_id", "citation_order",
    "citation_type", "citation_label", "target_kind", "target_id", "source_id", "note_rel_path", "claim_id",
    "receipt_id", "pack_id", "pack_item_id", "memory_node_id", "memory_mention_id", "compilation_id",
    "decision_id", "preference_id", "open_loop_id", "review_item_id", "projection_item_id", "source_ref",
    "source_root_key", "rel_path", "source_digest", "card_digest", "target_digest", "evidence_excerpt",
    "evidence_location", "confidence", "review_state", "effective_state", "inclusion_state", "created_at",
    "metadata_json",
)

_RECEIPT_COLUMNS = (
    "draft_receipt_id", "draft_id", "builder_version", "packet_id", "input_digest", "output_digest",
    "answer_contract_digest", "draft_policy_json", "budget_json", "trusted_section_count",
    "candidate_section_count", "caveat_count", "citation_count", "open_question_count", "excluded_count",
    "section_count", "dropped_count", "truncated", "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "draft_id", "event_type", "from_status", "to_status", "detail", "created_at",
)

# Prior drafts in this lineage may be superseded by a rebuild.
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


class AnswerDraftRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write --------------------------------------------------------------------------
    def upsert_draft(self, draft: dict[str, Any], sections: list[dict[str, Any]],
                     citations: list[dict[str, Any]], receipt: dict[str, Any], *,
                     conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        did = draft.get("draft_id")
        dtype = draft.get("draft_type")
        if not did or not dtype:
            raise AnswerDraftValidationError("draft_id_and_type_required")
        packet_id = draft.get("packet_id") or ""
        policy = draft.get("draft_policy_json") or ""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_answer_drafts WHERE draft_id=?", (did,)
            ).fetchone()
            if exists is not None:
                return {"draft_id": did, "created": False, "reused": True, "superseded": []}
            # Lineage-scoped supersede: same (draft_type, packet_id, policy), still draft/built, new id.
            placeholders = ", ".join("?" for _ in _SUPERSEDABLE_STATES)
            priors = c.execute(
                "SELECT draft_id, status FROM assistant_answer_drafts "
                "WHERE draft_type=? AND IFNULL(packet_id,'')=? AND IFNULL(draft_policy_json,'')=? "
                f"AND draft_id!=? AND status IN ({placeholders})",
                (dtype, packet_id, policy, did, *_SUPERSEDABLE_STATES),
            ).fetchall()
            for prior_id, prior_status in priors:
                c.execute(
                    "UPDATE assistant_answer_drafts SET status='superseded', updated_at=? "
                    "WHERE draft_id=?", (now, prior_id))
                self._insert_event(c, prior_id, "marked_superseded", from_status=prior_status,
                                   to_status="superseded", detail=did, now=now)
            header = {**draft, "status": draft.get("status", "built"), "created_at": now,
                      "updated_at": now}
            self._insert(c, "assistant_answer_drafts", _DRAFT_COLUMNS, header)
            for s in sections:
                self._insert(c, "assistant_answer_draft_sections", _SECTION_COLUMNS,
                             {**s, "created_at": now})
            for ci in citations:
                self._insert(c, "assistant_answer_draft_citations", _CITATION_COLUMNS,
                             {**ci, "created_at": now})
            self._insert(c, "assistant_answer_draft_receipts", _RECEIPT_COLUMNS,
                         {**receipt, "created_at": now})
            self._insert_event(c, did, "created", from_status=None, to_status="draft",
                               detail=draft.get("input_digest"), now=now)
            self._insert_event(c, did, "built", from_status="draft", to_status="built",
                               detail=draft.get("output_digest"), now=now)
            return {"draft_id": did, "created": True, "reused": False,
                    "superseded": [p[0] for p in priors]}

    def _insert(self, c: sqlite3.Connection, table: str, columns: tuple[str, ...],
                row: dict[str, Any]) -> None:
        cols = [col for col in columns if col in row]
        placeholders = ", ".join("?" for _ in cols)
        c.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",  # noqa: S608 (fixed cols)
            tuple(row.get(col) for col in cols),
        )

    def _insert_event(self, c: sqlite3.Connection, draft_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise AnswerDraftValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_answer_draft_events "
            "(event_id, draft_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, draft_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    def mark_answer_draft_stale_if_needed(self, draft_id: str, *, current_input_digest: str,
                                          conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Explicit live check: if the draft's stored ``input_digest`` no longer matches the current inputs,
        mark it stale. No background scan exists. Draft-owned write only."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT status, input_digest FROM assistant_answer_drafts WHERE draft_id=?",
                (draft_id,)
            ).fetchone()
            if row is None:
                return {"draft_id": draft_id, "found": False}
            status, stored = row
            drifted = stored != current_input_digest
            if drifted and status not in ("stale", "superseded"):
                c.execute(
                    "UPDATE assistant_answer_drafts SET status='stale', updated_at=? "
                    "WHERE draft_id=?", (now, draft_id))
                self._insert_event(c, draft_id, "marked_stale", from_status=status, to_status="stale",
                                   detail="input_drift", now=now)
            return {"draft_id": draft_id, "found": True, "stale": drifted}

    # ----- read (bounded) -----------------------------------------------------------------
    def get_answer_draft(self, draft_id: str, *,
                         conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_DRAFT_COLUMNS)} FROM assistant_answer_drafts "
                "WHERE draft_id=?", (draft_id,)
            ).fetchone()
        return dict(zip(_DRAFT_COLUMNS, row, strict=True)) if row else None

    def list_answer_drafts(self, *, draft_type: str | None = None, status: str | None = None,
                           packet_id: str | None = None, limit: int = _DEFAULT_LIMIT,
                           conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("draft_type", draft_type), ("status", status), ("packet_id", packet_id)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_DRAFT_COLUMNS)} FROM assistant_answer_drafts "  # noqa: S608
                f"{where}ORDER BY updated_at DESC, draft_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_DRAFT_COLUMNS, r, strict=True)) for r in rows]

    def list_answer_draft_sections(self, draft_id: str, *, section_type: str | None = None,
                                   limit: int = _MAX_LIMIT,
                                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["draft_id=?"]
        params: list[Any] = [draft_id]
        if section_type:
            clauses.append("section_type=?")
            params.append(section_type)
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_SECTION_COLUMNS)} FROM assistant_answer_draft_sections "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY section_order ASC, draft_section_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_SECTION_COLUMNS, r, strict=True)) for r in rows]

    def list_answer_draft_citations(self, draft_id: str, *, draft_section_id: str | None = None,
                                    limit: int = _MAX_LIMIT,
                                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses = ["draft_id=?"]
        params: list[Any] = [draft_id]
        if draft_section_id:
            clauses.append("draft_section_id=?")
            params.append(draft_section_id)
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_CITATION_COLUMNS)} FROM assistant_answer_draft_citations "  # noqa: S608
                f"WHERE {' AND '.join(clauses)} ORDER BY citation_order ASC, draft_citation_id ASC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_CITATION_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, draft_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_answer_draft_receipts "
                "WHERE draft_id=? ORDER BY created_at DESC, draft_receipt_id DESC LIMIT ?",
                (draft_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, draft_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_answer_draft_events "
                "WHERE draft_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (draft_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count(self, *, draft_type: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("draft_type", draft_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_answer_drafts {where}",  # noqa: S608
                params).fetchone()[0])

    def summary(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Bounded aggregate over drafts: counts by type and status + total sections/citations. Pure read."""
        with borrow_connection(conn, self.db_path) as c:
            by_type = {r[0]: int(r[1]) for r in c.execute(
                "SELECT draft_type, COUNT(*) FROM assistant_answer_drafts "
                "GROUP BY draft_type").fetchall()}
            by_status = {r[0]: int(r[1]) for r in c.execute(
                "SELECT status, COUNT(*) FROM assistant_answer_drafts GROUP BY status").fetchall()}
            total = int(c.execute("SELECT COUNT(*) FROM assistant_answer_drafts").fetchone()[0])
            sections = int(c.execute(
                "SELECT COUNT(*) FROM assistant_answer_draft_sections").fetchone()[0])
            citations = int(c.execute(
                "SELECT COUNT(*) FROM assistant_answer_draft_citations").fetchone()[0])
        return {"total_drafts": total, "total_sections": sections, "total_citations": citations,
                "by_draft_type": by_type, "by_status": by_status}
