"""Sole reader/writer of the V102 context-pack tables (N8C-6).

Writes only to ``assistant_context_packs`` / ``_items`` / ``_receipts`` / ``_events`` — never a
source/import/claim/enrichment table, never the vault. A pack is persisted atomically in one
transaction via :meth:`persist_pack` (header + items + reproducibility receipt + a ``built`` event).
``pack_id`` is a primary key: :meth:`persist_pack` refuses to overwrite an existing pack (raises
``ContextPackValidationError``) — the builder decides reuse-or-report.

Rows are plain dicts (column-tuple ``SELECT`` + ``dict(zip(..., strict=True))``), following the
N8C-4/5 repository conventions. Every method threads an optional ``conn=`` so a caller can pin one
read-only connection.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .context_pack_models import (
    BUILDER_VERSION,
    EVENT_BUILT,
    EVENT_TYPES,
    STATUS_STALE,
    ContextPackValidationError,
)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_PACK_COLUMNS = (
    "pack_id", "pack_type", "title", "objective", "scope_json", "budget_json", "status",
    "created_by", "builder_version", "input_digest", "output_digest", "source_count",
    "claim_count", "receipt_count", "item_count", "truncated", "stale_count", "created_at",
    "updated_at", "metadata_json",
)

_ITEM_COLUMNS = (
    "pack_item_id", "pack_id", "item_order", "item_type", "source_id", "note_rel_path", "claim_id",
    "job_id", "receipt_id", "title", "content_excerpt", "evidence_excerpt", "source_digest",
    "card_digest", "result_digest", "source_state", "confidence", "review_tier", "token_estimate",
    "included", "exclusion_reason", "metadata_json", "created_at",
)

_RECEIPT_COLUMNS = (
    "receipt_id", "pack_id", "builder_version", "input_digest", "output_digest", "scope_json",
    "budget_json", "included_count", "excluded_count", "source_count", "claim_count",
    "receipt_count", "stale_count", "truncated", "total_chars", "total_token_estimate",
    "created_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "pack_id", "event_type", "from_status", "to_status", "detail", "created_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


class ContextPackRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write (atomic pack persist) -----------------------------------------------------
    def persist_pack(
        self,
        header: dict[str, Any],
        item_rows: list[dict[str, Any]],
        receipt: dict[str, Any] | None = None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Insert a pack header, its ordered items, an optional reproducibility receipt, and a
        ``built`` lifecycle event in ONE transaction. Refuses to overwrite an existing ``pack_id``.
        """
        pack_id = header.get("pack_id")
        if not pack_id:
            raise ContextPackValidationError("pack_id_required")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_context_packs WHERE pack_id=?", (pack_id,)
            ).fetchone()
            if exists is not None:
                raise ContextPackValidationError(f"pack_exists:{pack_id}")
            self._insert_pack(c, header, now)
            for order, row in enumerate(item_rows):
                self._insert_item(c, {**row, "pack_id": pack_id}, order, now)
            if receipt is not None:
                self._insert_receipt(c, {**receipt, "pack_id": pack_id}, now)
            self._insert_event(
                c, pack_id, EVENT_BUILT, from_status="draft",
                to_status=str(header.get("status", "built")),
                detail=f"items={len(item_rows)}", now=now,
            )
        return {"pack_id": pack_id, "item_count": len(item_rows)}

    def _insert_pack(self, c: sqlite3.Connection, header: dict[str, Any], now: str) -> None:
        meta = header.get("metadata")
        c.execute(
            "INSERT INTO assistant_context_packs "
            "(pack_id, pack_type, title, objective, scope_json, budget_json, status, created_by, "
            " builder_version, input_digest, output_digest, source_count, claim_count, "
            " receipt_count, item_count, truncated, stale_count, created_at, updated_at, "
            " metadata_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                header["pack_id"], header["pack_type"], header.get("title"), header.get("objective"),
                header.get("scope_json"), header.get("budget_json"),
                str(header.get("status", "built")), header.get("created_by"),
                header.get("builder_version", BUILDER_VERSION), header.get("input_digest"),
                header.get("output_digest"), int(header.get("source_count", 0)),
                int(header.get("claim_count", 0)), int(header.get("receipt_count", 0)),
                int(header.get("item_count", len(header.get("items", []) or []))),
                1 if header.get("truncated") else 0, int(header.get("stale_count", 0)),
                now, now,
                json.dumps(meta, sort_keys=True) if meta else None,
            ),
        )

    def _insert_item(self, c: sqlite3.Connection, row: dict[str, Any], order: int, now: str) -> None:
        c.execute(
            "INSERT INTO assistant_context_pack_items "
            "(pack_item_id, pack_id, item_order, item_type, source_id, note_rel_path, claim_id, "
            " job_id, receipt_id, title, content_excerpt, evidence_excerpt, source_digest, "
            " card_digest, result_digest, source_state, confidence, review_tier, token_estimate, "
            " included, exclusion_reason, metadata_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex, row["pack_id"], int(row.get("item_order", order)), row["item_type"],
                row.get("source_id"), row.get("note_rel_path"), row.get("claim_id"),
                row.get("job_id"), row.get("receipt_id"), row.get("title"),
                row.get("content_excerpt"), row.get("evidence_excerpt"), row.get("source_digest"),
                row.get("card_digest"), row.get("result_digest"), row.get("source_state"),
                row.get("confidence"), row.get("review_tier"), int(row.get("token_estimate", 0)),
                1 if row.get("included", 1) else 0, row.get("exclusion_reason"),
                row.get("metadata_json"), now,
            ),
        )

    def _insert_receipt(self, c: sqlite3.Connection, r: dict[str, Any], now: str) -> None:
        meta = r.get("metadata")
        c.execute(
            "INSERT INTO assistant_context_pack_receipts "
            "(receipt_id, pack_id, builder_version, input_digest, output_digest, scope_json, "
            " budget_json, included_count, excluded_count, source_count, claim_count, "
            " receipt_count, stale_count, truncated, total_chars, total_token_estimate, created_at, "
            " metadata_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r.get("receipt_id") or uuid.uuid4().hex, r["pack_id"],
                r.get("builder_version", BUILDER_VERSION), r.get("input_digest"),
                r.get("output_digest"), r.get("scope_json"), r.get("budget_json"),
                int(r.get("included_count", 0)), int(r.get("excluded_count", 0)),
                int(r.get("source_count", 0)), int(r.get("claim_count", 0)),
                int(r.get("receipt_count", 0)), int(r.get("stale_count", 0)),
                1 if r.get("truncated") else 0, int(r.get("total_chars", 0)),
                int(r.get("total_token_estimate", 0)), now,
                json.dumps(meta, sort_keys=True) if meta else None,
            ),
        )

    def _insert_event(self, c: sqlite3.Connection, pack_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise ContextPackValidationError(f"unknown_event_type:{event_type}")
        event_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO assistant_context_pack_events "
            "(event_id, pack_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, pack_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    def log_event(self, pack_id: str, event_type: str, *, from_status: str | None = None,
                  to_status: str | None = None, detail: str | None = None,
                  conn: sqlite3.Connection | None = None) -> str:
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            return self._insert_event(c, pack_id, event_type, from_status=from_status,
                                      to_status=to_status, detail=detail, now=now)

    def mark_pack_stale(self, pack_id: str, *, detail: str | None = None,
                        conn: sqlite3.Connection | None = None) -> bool:
        """Explicitly mark a pack stale + log the event. No automatic/background stale scan exists."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT status FROM assistant_context_packs WHERE pack_id=?", (pack_id,)
            ).fetchone()
            if row is None:
                return False
            prev = row[0]
            if prev == STATUS_STALE:
                return True
            c.execute(
                "UPDATE assistant_context_packs SET status=?, updated_at=? WHERE pack_id=?",
                (STATUS_STALE, now, pack_id),
            )
            self._insert_event(c, pack_id, "marked_stale", from_status=prev,
                               to_status=STATUS_STALE, detail=detail, now=now)
        return True

    # ----- read (bounded) ------------------------------------------------------------------
    def get_pack(self, pack_id: str, *,
                 conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_PACK_COLUMNS)} FROM assistant_context_packs WHERE pack_id=?",
                (pack_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(_PACK_COLUMNS, row, strict=True))

    def list_packs(self, *, pack_type: str | None = None, status: str | None = None,
                   limit: int = _DEFAULT_LIMIT,
                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("pack_type", pack_type), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_PACK_COLUMNS)} FROM assistant_context_packs {where}"
                "ORDER BY created_at DESC, pack_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_PACK_COLUMNS, r, strict=True)) for r in rows]

    def list_items(self, pack_id: str, *, limit: int = _MAX_LIMIT,
                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_ITEM_COLUMNS)} FROM assistant_context_pack_items "
                "WHERE pack_id=? ORDER BY item_order ASC, pack_item_id ASC LIMIT ?",
                (pack_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_ITEM_COLUMNS, r, strict=True)) for r in rows]

    def list_receipts(self, pack_id: str, *, limit: int = _DEFAULT_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_RECEIPT_COLUMNS)} FROM assistant_context_pack_receipts "
                "WHERE pack_id=? ORDER BY created_at DESC, receipt_id DESC LIMIT ?",
                (pack_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_RECEIPT_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, pack_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_context_pack_events "
                "WHERE pack_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (pack_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count_packs(self, *, status: str | None = None,
                    conn: sqlite3.Connection | None = None) -> int:
        where = "WHERE status=?" if status else ""
        params = (status,) if status else ()
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_context_packs {where}", params).fetchone()[0])
