"""Sole reader/writer of the V103 memory tables (N8C-7).

Writes only to ``assistant_memory_nodes`` / ``_mentions`` / ``_compilations`` / ``_events`` — never a
source/import/claim/enrichment/context-pack table, never the vault. Deterministic upsert semantics make
re-running the compiler idempotent: a node/mention with an unchanged deterministic id is refreshed in
place (no duplicate); a compilation is immutable-by-input — a new ``compilation_id`` supersedes the
prior compilation of the same ``(node, compile_type)``.

Rows are plain dicts (column-tuple ``SELECT`` + ``dict(zip(..., strict=True))``), following the
N8C-4/5/6 repository conventions. Every method threads an optional ``conn=`` so a caller can pin one
read-only connection.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from .memory_models import (
    ALIASES_MAX,
    COMPILER_VERSION,
    EVENT_TYPES,
    MemoryValidationError,
)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_NODE_COLUMNS = (
    "node_id", "node_type", "canonical_name", "normalized_name", "aliases_json", "domain",
    "status", "review_tier", "confidence", "source_count", "claim_count", "mention_count",
    "compilation_count", "input_digest", "created_by", "created_at", "updated_at", "metadata_json",
)

_MENTION_COLUMNS = (
    "mention_id", "node_id", "mention_type", "mention_text", "source_id", "note_rel_path",
    "claim_id", "job_id", "receipt_id", "pack_id", "pack_item_id", "evidence_excerpt",
    "source_digest", "card_digest", "confidence", "review_tier", "source_state", "created_at",
    "metadata_json",
)

_COMPILATION_COLUMNS = (
    "compilation_id", "node_id", "compile_type", "summary", "key_points_json", "open_questions_json",
    "risks_json", "preferences_json", "source_count", "claim_count", "pack_count", "mention_count",
    "input_digest", "output_digest", "stale_count", "truncated", "review_tier", "status",
    "created_by", "created_at", "updated_at", "metadata_json",
)

_EVENT_COLUMNS = (
    "event_id", "node_id", "event_type", "from_status", "to_status", "detail", "created_at",
)


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


class MemoryRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- write ---------------------------------------------------------------------------
    def upsert_node(self, header: dict[str, Any], *,
                    conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Insert a node, or refresh an existing one (same deterministic ``node_id``) in place.

        Aliases are merged (union). Refresh updates canonical_name/review_tier/confidence/input_digest/
        counts and logs a ``created``/``updated`` event. Never creates a duplicate.
        """
        node_id = header.get("node_id")
        if not node_id:
            raise MemoryValidationError("node_id_required")
        now = _now()
        new_aliases = list(header.get("aliases") or [])
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            existing = c.execute(
                "SELECT aliases_json FROM assistant_memory_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            if existing is None:
                c.execute(
                    "INSERT INTO assistant_memory_nodes "
                    "(node_id, node_type, canonical_name, normalized_name, aliases_json, domain, "
                    " status, review_tier, confidence, source_count, claim_count, mention_count, "
                    " compilation_count, input_digest, created_by, created_at, updated_at, "
                    " metadata_json) "
                    "VALUES (?,?,?,?,?,?, 'active', ?,?, 0,0,0,0, ?,?,?,?,?)",
                    (node_id, header["node_type"], header["canonical_name"],
                     header["normalized_name"], _dump_aliases(new_aliases), header.get("domain"),
                     header.get("review_tier"), header.get("confidence"), header.get("input_digest"),
                     header.get("created_by"), now, now,
                     json.dumps(header["metadata"], sort_keys=True) if header.get("metadata") else None),
                )
                self._insert_event(c, node_id, "created", from_status=None, to_status="active",
                                   detail=header.get("canonical_name"), now=now)
                return {"node_id": node_id, "created": True}
            merged = _merge_aliases(existing[0], new_aliases)
            c.execute(
                "UPDATE assistant_memory_nodes SET canonical_name=?, normalized_name=?, aliases_json=?, "
                "domain=COALESCE(?, domain), review_tier=?, confidence=?, input_digest=?, updated_at=? "
                "WHERE node_id=?",
                (header["canonical_name"], header["normalized_name"], merged, header.get("domain"),
                 header.get("review_tier"), header.get("confidence"), header.get("input_digest"),
                 now, node_id),
            )
            self._insert_event(c, node_id, "updated", from_status="active", to_status="active",
                               detail=header.get("canonical_name"), now=now)
            return {"node_id": node_id, "created": False}

    def upsert_mention(self, row: dict[str, Any], *,
                       conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Insert a mention idempotently (same deterministic ``mention_id`` → no-op, no duplicate)."""
        mention_id = row.get("mention_id")
        if not mention_id:
            raise MemoryValidationError("mention_id_required")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_memory_mentions WHERE mention_id=?", (mention_id,)
            ).fetchone()
            if exists is not None:
                return {"mention_id": mention_id, "created": False}
            c.execute(
                "INSERT INTO assistant_memory_mentions "
                "(mention_id, node_id, mention_type, mention_text, source_id, note_rel_path, "
                " claim_id, job_id, receipt_id, pack_id, pack_item_id, evidence_excerpt, "
                " source_digest, card_digest, confidence, review_tier, source_state, created_at, "
                " metadata_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mention_id, row["node_id"], row["mention_type"], row.get("mention_text"),
                 row.get("source_id"), row.get("note_rel_path"), row.get("claim_id"),
                 row.get("job_id"), row.get("receipt_id"), row.get("pack_id"),
                 row.get("pack_item_id"), row.get("evidence_excerpt"), row.get("source_digest"),
                 row.get("card_digest"), row.get("confidence"), row.get("review_tier"),
                 row.get("source_state"), now, row.get("metadata_json")),
            )
            return {"mention_id": mention_id, "created": True}

    def refresh_node_counts(self, node_id: str, *,
                            conn: sqlite3.Connection | None = None) -> None:
        """Recompute a node's provenance counts from its mentions (keeps counts idempotent)."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE assistant_memory_nodes SET "
                " mention_count=(SELECT COUNT(*) FROM assistant_memory_mentions WHERE node_id=?), "
                " source_count=(SELECT COUNT(DISTINCT source_id) FROM assistant_memory_mentions "
                "               WHERE node_id=? AND source_id IS NOT NULL), "
                " claim_count=(SELECT COUNT(DISTINCT claim_id) FROM assistant_memory_mentions "
                "              WHERE node_id=? AND claim_id IS NOT NULL), "
                " compilation_count=(SELECT COUNT(*) FROM assistant_memory_compilations WHERE node_id=?), "
                " updated_at=? WHERE node_id=?",
                (node_id, node_id, node_id, node_id, now, node_id),
            )

    def persist_compilation(self, row: dict[str, Any], *,
                            conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Insert a new compilation (immutable-by-input). If its ``compilation_id`` already exists,
        report ``reused`` (no overwrite). Otherwise supersede any prior ``built`` compilation of the
        same ``(node, compile_type)``, bump the node's compilation_count, and log a ``compiled`` event.
        """
        compilation_id = row.get("compilation_id")
        node_id = row.get("node_id")
        if not compilation_id or not node_id:
            raise MemoryValidationError("compilation_id_and_node_id_required")
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            exists = c.execute(
                "SELECT 1 FROM assistant_memory_compilations WHERE compilation_id=?",
                (compilation_id,)
            ).fetchone()
            if exists is not None:
                return {"compilation_id": compilation_id, "created": False, "reused": True}
            # Supersede prior built compilation(s) for this node+compile_type.
            c.execute(
                "UPDATE assistant_memory_compilations SET status='superseded', updated_at=? "
                "WHERE node_id=? AND compile_type=? AND status='built'",
                (now, node_id, row["compile_type"]),
            )
            c.execute(
                "INSERT INTO assistant_memory_compilations "
                "(compilation_id, node_id, compile_type, summary, key_points_json, "
                " open_questions_json, risks_json, preferences_json, source_count, claim_count, "
                " pack_count, mention_count, input_digest, output_digest, stale_count, truncated, "
                " review_tier, status, created_by, created_at, updated_at, metadata_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'built', ?,?,?,?)",
                (compilation_id, node_id, row["compile_type"], row.get("summary"),
                 row.get("key_points_json"), row.get("open_questions_json"), row.get("risks_json"),
                 row.get("preferences_json"), int(row.get("source_count", 0)),
                 int(row.get("claim_count", 0)), int(row.get("pack_count", 0)),
                 int(row.get("mention_count", 0)), row.get("input_digest"), row.get("output_digest"),
                 int(row.get("stale_count", 0)), 1 if row.get("truncated") else 0,
                 row.get("review_tier"), row.get("created_by"), now, now,
                 json.dumps(row["metadata"], sort_keys=True) if row.get("metadata") else None),
            )
            c.execute(
                "UPDATE assistant_memory_nodes SET compilation_count=("
                "  SELECT COUNT(*) FROM assistant_memory_compilations WHERE node_id=?), updated_at=? "
                "WHERE node_id=?",
                (node_id, now, node_id),
            )
            self._insert_event(c, node_id, "compiled", from_status=None, to_status=None,
                               detail=row["compile_type"], now=now)
            return {"compilation_id": compilation_id, "created": True, "reused": False}

    def _insert_event(self, c: sqlite3.Connection, node_id: str, event_type: str, *,
                      from_status: str | None, to_status: str | None, detail: str | None,
                      now: str) -> str:
        if event_type not in EVENT_TYPES:
            raise MemoryValidationError(f"unknown_event_type:{event_type}")
        event_id = _uuid()
        c.execute(
            "INSERT INTO assistant_memory_events "
            "(event_id, node_id, event_type, from_status, to_status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event_id, node_id, event_type, from_status, to_status, detail, now),
        )
        return event_id

    def mark_node_stale(self, node_id: str, *, detail: str | None = None,
                        conn: sqlite3.Connection | None = None) -> bool:
        """Explicitly mark a node stale + log the event. No automatic/background stale scan exists."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT status FROM assistant_memory_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            if row is None:
                return False
            prev = row[0]
            if prev == "stale":
                return True
            c.execute("UPDATE assistant_memory_nodes SET status='stale', updated_at=? WHERE node_id=?",
                      (now, node_id))
            self._insert_event(c, node_id, "marked_stale", from_status=prev, to_status="stale",
                               detail=detail, now=now)
        return True

    # ----- read (bounded) ------------------------------------------------------------------
    def get_node(self, node_id: str, *,
                 conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                f"SELECT {', '.join(_NODE_COLUMNS)} FROM assistant_memory_nodes WHERE node_id=?",
                (node_id,),
            ).fetchone()
        return dict(zip(_NODE_COLUMNS, row, strict=True)) if row else None

    def list_nodes(self, *, node_type: str | None = None, status: str | None = None,
                   domain: str | None = None, limit: int = _DEFAULT_LIMIT,
                   conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (("node_type", node_type), ("status", status), ("domain", domain)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(_clamp_limit(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_NODE_COLUMNS)} FROM assistant_memory_nodes {where}"
                "ORDER BY mention_count DESC, updated_at DESC, node_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(zip(_NODE_COLUMNS, r, strict=True)) for r in rows]

    def search_nodes(self, query: str, *, limit: int = _DEFAULT_LIMIT,
                     conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        from .memory_models import normalize_memory_name
        like = f"%{normalize_memory_name(query)}%"
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_NODE_COLUMNS)} FROM assistant_memory_nodes "
                "WHERE normalized_name LIKE ? ORDER BY mention_count DESC, node_id DESC LIMIT ?",
                (like, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_NODE_COLUMNS, r, strict=True)) for r in rows]

    def list_mentions(self, node_id: str, *, limit: int = _MAX_LIMIT,
                      conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_MENTION_COLUMNS)} FROM assistant_memory_mentions "
                "WHERE node_id=? ORDER BY created_at ASC, mention_id ASC LIMIT ?",
                (node_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_MENTION_COLUMNS, r, strict=True)) for r in rows]

    def list_compilations(self, node_id: str, *, limit: int = _DEFAULT_LIMIT,
                          conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_COMPILATION_COLUMNS)} FROM assistant_memory_compilations "
                "WHERE node_id=? ORDER BY created_at DESC, compilation_id DESC LIMIT ?",
                (node_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_COMPILATION_COLUMNS, r, strict=True)) for r in rows]

    def list_built_compilations_for_sources(self, source_ids: list[str], *, limit: int = _MAX_LIMIT,
                                            conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        """Read-only: built compilations whose node has a mention in any of ``source_ids`` (bounded).

        Used by the N8C-8 decision/preference/open-loop extractor to mine a pack's memory context —
        never writes. Empty ``source_ids`` returns ``[]``.
        """
        ids = [s for s in dict.fromkeys(source_ids) if s]
        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join('c.' + col for col in _COMPILATION_COLUMNS)} "
                "FROM assistant_memory_compilations c WHERE c.status='built' AND c.node_id IN ("
                "  SELECT DISTINCT node_id FROM assistant_memory_mentions "
                f"  WHERE source_id IN ({placeholders})) "  # noqa: S608 (placeholders are bound params)
                "ORDER BY c.created_at DESC, c.compilation_id DESC LIMIT ?",
                (*ids, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_COMPILATION_COLUMNS, r, strict=True)) for r in rows]

    def list_events(self, node_id: str, *, limit: int = _MAX_LIMIT,
                    conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                f"SELECT {', '.join(_EVENT_COLUMNS)} FROM assistant_memory_events "
                "WHERE node_id=? ORDER BY created_at ASC, event_id ASC LIMIT ?",
                (node_id, _clamp_limit(limit)),
            ).fetchall()
        return [dict(zip(_EVENT_COLUMNS, r, strict=True)) for r in rows]

    def count_nodes(self, *, status: str | None = None,
                    conn: sqlite3.Connection | None = None) -> int:
        where = "WHERE status=?" if status else ""
        params = (status,) if status else ()
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(
                f"SELECT COUNT(*) FROM assistant_memory_nodes {where}", params).fetchone()[0])


def _dump_aliases(aliases: list[str]) -> str | None:
    uniq = sorted({a.strip() for a in aliases if a and a.strip()})[:ALIASES_MAX]
    return json.dumps(uniq, sort_keys=True) if uniq else None


def _merge_aliases(existing_json: str | None, new_aliases: list[str]) -> str | None:
    cur: list[str] = []
    if existing_json:
        try:
            loaded = json.loads(existing_json)
            if isinstance(loaded, list):
                cur = [str(x) for x in loaded]
        except (ValueError, TypeError):
            cur = []
    return _dump_aliases(cur + list(new_aliases))


# Keep COMPILER_VERSION importable from the repo module for callers that only import it here.
__all__ = ["MemoryRepository", "COMPILER_VERSION"]
