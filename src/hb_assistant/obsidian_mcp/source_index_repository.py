"""Sole reader/writer of the V93 source-intelligence tables + explicit FTS sync.

No triggers: every write path here keeps the regular FTS5 tables in sync by storing the
SQLite-assigned ``rowid`` back in ``source_intelligence_metadata.fts_rowid`` so reindex/delete
is a plain ``DELETE ... WHERE rowid=?``. Only bounded, already-redacted fields are ever indexed
into FTS (excerpt/rel_path/project_key/tags) — never a raw email body or Text-Vault content.

Background callers (indexer/watcher worker thread) pass no connection and each call owns+closes
its own connection (sqlite connections are per-thread). A caller may thread one borrowed
connection through a hot path via ``conn=``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction
from hb_assistant.store.source_intelligence_tables import fts5_available


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_id_for(source_kind: str, *, rel_path: str | None = None,
                  domain_ref_table: str | None = None, domain_ref_id: str | None = None) -> str:
    if rel_path is not None:
        key = f"{source_kind}|file|{rel_path}"
    else:
        key = f"{source_kind}|link|{domain_ref_table}|{domain_ref_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


class SourceIndexRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- low-level -------------------------------------------------------------------------
    def _fts_available(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT state_value FROM source_intelligence_state WHERE state_key='fts_available'"
        ).fetchone()
        if row is not None:
            return row[0] == "1"
        return fts5_available(conn)

    def _set_state(self, c: sqlite3.Connection, key: str, value: str) -> None:
        """Upsert a singleton k/v row in the existing transaction (no schema change)."""
        c.execute(
            "INSERT INTO source_intelligence_state (state_key, state_value, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value, updated_at=excluded.updated_at",
            (key, value, _now()),
        )

    def record_drain(self, *, conn: sqlite3.Connection | None = None) -> None:
        """Stamp the last successful queue-drain time (operator queue-health signal)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._set_state(c, "last_drain_at", _now())

    # ----- source roots ----------------------------------------------------------------------
    def register_source_roots(self, roots: Iterable[dict[str, Any]], *, conn: sqlite3.Connection | None = None) -> None:
        """Record configured roots in _state and deactivate sources of removed roots."""
        roots = list(roots)
        active_keys = {str(r.get("source_root_key")) for r in roots if r.get("enabled", True)}
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_state (state_key, state_value, updated_at) "
                "VALUES ('source_roots', ?, ?) "
                "ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value, updated_at=excluded.updated_at",
                (json.dumps(sorted(active_keys)), _now()),
            )
            # Deactivate file sources whose root is no longer configured/enabled.
            known = {
                row[0]
                for row in c.execute(
                    "SELECT DISTINCT source_root_key FROM source_intelligence_sources "
                    "WHERE source_root_key IS NOT NULL"
                ).fetchall()
            }
            for stale_key in known - active_keys:
                c.execute(
                    "UPDATE source_intelligence_sources SET active=0, updated_at=? WHERE source_root_key=?",
                    (_now(), stale_key),
                )

    # ----- idempotency lookups ---------------------------------------------------------------
    def lookup_by_path(self, source_kind: str, rel_path: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT s.source_id, m.content_sha256, m.mtime_ns, m.fts_rowid, s.deleted "
                "FROM source_intelligence_sources s "
                "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "WHERE s.source_kind=? AND s.rel_path=?",
                (source_kind, rel_path),
            ).fetchone()
        if row is None:
            return None
        return {"source_id": row[0], "content_sha256": row[1], "mtime_ns": row[2],
                "fts_rowid": row[3], "deleted": bool(row[4])}

    def active_rel_paths(self, source_root_key: str, *, conn: sqlite3.Connection | None = None) -> set[str]:
        with borrow_connection(conn, self.db_path) as c:
            return {
                row[0]
                for row in c.execute(
                    "SELECT rel_path FROM source_intelligence_sources "
                    "WHERE source_root_key=? AND rel_path IS NOT NULL AND deleted=0",
                    (source_root_key,),
                ).fetchall()
            }

    # ----- writes ----------------------------------------------------------------------------
    def upsert_source_file(self, record: dict[str, Any], *, conn: sqlite3.Connection | None = None) -> str:
        """Transactional write of one external file (sources+metadata+text+chunks+relationships+FTS)."""
        source_kind = record["source_kind"]
        rel_path = record["rel_path"]
        source_id = source_id_for(source_kind, rel_path=rel_path)
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            existing = c.execute(
                "SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_id=?",
                (source_id,),
            ).fetchone()
            old_fts_rowid = existing[0] if existing else None

            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_id, source_kind, source_root_key, rel_path, abs_path_hash, "
                " project_key, project_number, active, deleted, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,1,0,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                " source_root_key=excluded.source_root_key, project_key=excluded.project_key, "
                " project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at",
                (source_id, source_kind, record.get("source_root_key"), rel_path,
                 record.get("abs_path_hash"), record.get("project_key"), record.get("project_number"),
                 now, now),
            )

            # FTS sync (regular fts5; only bounded excerpt/rel_path/project_key indexed).
            fts_rowid = old_fts_rowid
            fts_table = "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
            if self._fts_available(c):
                if old_fts_rowid is not None:
                    c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (old_fts_rowid,))
                excerpt = record.get("text_excerpt") or ""
                aux = record.get("fts_aux") or record.get("project_key") or ""
                cur = c.execute(
                    f"INSERT INTO {fts_table}(text_excerpt, rel_path, aux) VALUES (?,?,?)",
                    (excerpt, rel_path, aux),
                )
                fts_rowid = cur.lastrowid

            c.execute(
                "INSERT INTO source_intelligence_metadata "
                "(source_id, file_ext, size_bytes, mtime_ns, content_sha256, page_count, "
                " paragraph_count, sheet_count, extraction_status, extraction_failure_code, fts_rowid, indexed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                " file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, "
                " content_sha256=excluded.content_sha256, page_count=excluded.page_count, "
                " paragraph_count=excluded.paragraph_count, sheet_count=excluded.sheet_count, "
                " extraction_status=excluded.extraction_status, extraction_failure_code=excluded.extraction_failure_code, "
                " fts_rowid=excluded.fts_rowid, indexed_at=excluded.indexed_at",
                (source_id, record.get("file_ext"), record.get("size_bytes"), record.get("mtime_ns"),
                 record.get("content_sha256"), record.get("page_count"), record.get("paragraph_count"),
                 record.get("sheet_count"), record.get("extraction_status", "ok"),
                 record.get("extraction_failure_code"), fts_rowid, now),
            )

            # _text (bounded excerpt; never raw body). Skipped for non-file kinds by callers.
            if record.get("text_excerpt") is not None or record.get("text_vault_ref") is not None:
                c.execute(
                    "INSERT INTO source_intelligence_text "
                    "(source_id, text_excerpt, excerpt_char_count, excerpt_truncated, full_text_sha256, "
                    " text_vault_ref, raw_body_persisted, redaction_applied, updated_at) "
                    "VALUES (?,?,?,?,?,?,0,1,?) "
                    "ON CONFLICT(source_id) DO UPDATE SET "
                    " text_excerpt=excluded.text_excerpt, excerpt_char_count=excluded.excerpt_char_count, "
                    " excerpt_truncated=excluded.excerpt_truncated, full_text_sha256=excluded.full_text_sha256, "
                    " text_vault_ref=excluded.text_vault_ref, updated_at=excluded.updated_at",
                    (source_id, record.get("text_excerpt"), record.get("excerpt_char_count", 0),
                     1 if record.get("excerpt_truncated") else 0, record.get("full_text_sha256"),
                     record.get("text_vault_ref"), now),
                )

            # chunks (replace set)
            c.execute("DELETE FROM source_intelligence_chunks WHERE source_id=?", (source_id,))
            for ordinal, chunk in enumerate(record.get("chunks") or []):
                c.execute(
                    "INSERT INTO source_intelligence_chunks "
                    "(chunk_id, source_id, ordinal, chunk_text, char_count, raw_body_persisted, created_at) "
                    "VALUES (?,?,?,?,?,0,?)",
                    (f"{source_id}:{ordinal}", source_id, ordinal, chunk, len(chunk), now),
                )

            # relationships (additive; UNIQUE guards dupes)
            for rel in record.get("relationships") or []:
                c.execute(
                    "INSERT INTO source_intelligence_relationships "
                    "(relationship_id, src_source_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(src_source_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                    " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                    (uuid.uuid4().hex, source_id, rel["dst_kind"], rel["dst_ref"], rel["relation"],
                     rel.get("confidence"), json.dumps(rel.get("evidence")) if rel.get("evidence") else None, now),
                )
        return source_id

    def link_domain_source(self, *, source_kind: str, domain_ref_table: str, domain_ref_id: str,
                           project_key: str | None = None, project_number: str | None = None,
                           conn: sqlite3.Connection | None = None) -> str:
        """Create a LINK row to an existing domain record (email/procore/schedule). No body re-ingest."""
        source_id = source_id_for(source_kind, domain_ref_table=domain_ref_table, domain_ref_id=domain_ref_id)
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_id, source_kind, domain_ref_table, domain_ref_id, project_key, project_number, "
                " active, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,1,0,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET project_key=excluded.project_key, "
                " project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at",
                (source_id, source_kind, domain_ref_table, domain_ref_id, project_key, project_number, now, now),
            )
        return source_id

    def mark_deleted(self, source_kind: str, rel_path: str, *, conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(
                "SELECT s.source_id, m.fts_rowid FROM source_intelligence_sources s "
                "LEFT JOIN source_intelligence_metadata m ON m.source_id=s.source_id "
                "WHERE s.source_kind=? AND s.rel_path=?",
                (source_kind, rel_path),
            ).fetchone()
            if row is None:
                return
            source_id, fts_rowid = row[0], row[1]
            if fts_rowid is not None and self._fts_available(c):
                fts_table = "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
                c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
            c.execute(
                "UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? WHERE source_id=?",
                (_now(), source_id),
            )
            self._mark_generated_notes_stale(c, source_id)

    def _mark_generated_notes_stale(self, c: sqlite3.Connection, source_id: str) -> None:
        c.execute(
            "UPDATE source_intelligence_generated_notes SET generation_status='stale', updated_at=? "
            "WHERE source_id=? AND generation_status='generated'",
            (_now(), source_id),
        )

    def mark_generated_notes_stale(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._mark_generated_notes_stale(c, source_id)

    # ----- source detail + generated-note tracking (source cards) ----------------------------
    def get_source_detail(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        """Joined sources+metadata+text row for rendering a source card. None if absent."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT s.source_id, s.source_kind, s.source_root_key, s.rel_path, s.domain_ref_table, "
                "  s.domain_ref_id, s.project_key, s.project_number, s.deleted, "
                "  m.file_ext, m.size_bytes, m.mtime_ns, m.content_sha256, m.page_count, "
                "  m.paragraph_count, m.sheet_count, m.extraction_status, m.indexed_at, "
                "  t.text_excerpt, t.excerpt_char_count, t.excerpt_truncated, t.text_vault_ref "
                "FROM source_intelligence_sources s "
                "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "LEFT JOIN source_intelligence_text t ON t.source_id = s.source_id "
                "WHERE s.source_id = ?",
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        keys = ("source_id", "source_kind", "source_root_key", "rel_path", "domain_ref_table",
                "domain_ref_id", "project_key", "project_number", "deleted", "file_ext",
                "size_bytes", "mtime_ns", "content_sha256", "page_count", "paragraph_count",
                "sheet_count", "extraction_status", "indexed_at", "text_excerpt",
                "excerpt_char_count", "excerpt_truncated", "text_vault_ref")
        detail = dict(zip(keys, row, strict=True))
        detail["deleted"] = bool(detail["deleted"])
        return detail

    def record_generated_note(self, source_id: str, note_rel_path: str, status: str,
                              generated_at: str, *, conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_generated_notes "
                "(generated_note_id, source_id, note_rel_path, generation_status, generated_at, updated_at) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source_id, note_rel_path) DO UPDATE SET "
                " generation_status=excluded.generation_status, generated_at=excluded.generated_at, "
                " updated_at=excluded.updated_at",
                (uuid.uuid4().hex, source_id, note_rel_path, status, generated_at, _now()),
            )
            if status == "generated":
                self._set_state(c, "last_note_at", _now())

    def has_generated_note(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
        """True if a card was ever generated for this source (status generated or stale)."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT 1 FROM source_intelligence_generated_notes "
                "WHERE source_id=? AND generation_status IN ('generated','stale') LIMIT 1",
                (source_id,),
            ).fetchone()
        return row is not None

    def list_stale_generated_notes(self, limit: int = 25, *, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT source_id, note_rel_path FROM source_intelligence_generated_notes "
                "WHERE generation_status='stale' ORDER BY updated_at LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [{"source_id": r[0], "note_rel_path": r[1]} for r in rows]

    # ----- advisory model-summary receipts (V94) ---------------------------------------------
    def upsert_summary(self, source_id: str, receipt: dict[str, Any], *,
                       conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_summaries "
                "(source_id, model_provider, model_name, prompt_version, prompt_sha256, "
                " summary_sha256, source_sha256, advisory, generated_at) "
                "VALUES (?,?,?,?,?,?,?,1,?) "
                "ON CONFLICT(source_id) DO UPDATE SET model_provider=excluded.model_provider, "
                " model_name=excluded.model_name, prompt_version=excluded.prompt_version, "
                " prompt_sha256=excluded.prompt_sha256, summary_sha256=excluded.summary_sha256, "
                " source_sha256=excluded.source_sha256, generated_at=excluded.generated_at",
                (source_id, receipt["model_provider"], receipt.get("model_name"),
                 receipt["prompt_version"], receipt.get("prompt_sha256"),
                 receipt.get("summary_sha256"), receipt.get("source_sha256"), _now()),
            )
            self._set_state(c, "last_summary_at", _now())

    def delete_summary(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute("DELETE FROM source_intelligence_summaries WHERE source_id=?", (source_id,))

    def get_summary(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT model_provider, model_name, prompt_version, prompt_sha256, summary_sha256, "
                " source_sha256, generated_at FROM source_intelligence_summaries WHERE source_id=?",
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(("model_provider", "model_name", "prompt_version", "prompt_sha256",
                         "summary_sha256", "source_sha256", "generated_at"), row, strict=True))

    def summary_counts(self, *, conn: sqlite3.Connection | None = None) -> dict[str, int]:
        """summarized_count + stale_summary_count (receipt source_sha drifted from current)."""
        with borrow_connection(conn, self.db_path) as c:
            total = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0]
            stale = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_summaries s "
                "JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "WHERE s.source_sha256 IS NOT m.content_sha256"
            ).fetchone()[0]
        return {"summarized_count": int(total), "stale_summary_count": int(stale)}

    # ----- durable queue ---------------------------------------------------------------------
    def enqueue_event(self, *, event_type: str, rel_path: str | None = None,
                      source_root_key: str | None = None, source_id: str | None = None,
                      conn: sqlite3.Connection | None = None) -> str:
        event_id = uuid.uuid4().hex
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            # Coalesce: if an identical queued event for this path exists, reuse it (debounce backstop).
            if rel_path is not None:
                existing = c.execute(
                    "SELECT event_id FROM source_intelligence_events "
                    "WHERE status='queued' AND rel_path=? AND event_type=?",
                    (rel_path, event_type),
                ).fetchone()
                if existing is not None:
                    return str(existing[0])
            c.execute(
                "INSERT INTO source_intelligence_events "
                "(event_id, source_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
                "VALUES (?,?,?,?,?,'queued',0,?,?)",
                (event_id, source_id, rel_path, source_root_key, event_type, now, now),
            )
        return event_id

    def claim_queued(self, limit: int = 50, *, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            rows = c.execute(
                "SELECT event_id, source_id, rel_path, source_root_key, event_type FROM source_intelligence_events "
                "WHERE status='queued' ORDER BY created_at LIMIT ?",
                (int(limit),),
            ).fetchall()
            claimed = []
            for r in rows:
                c.execute(
                    "UPDATE source_intelligence_events SET status='processing', attempts=attempts+1, updated_at=? "
                    "WHERE event_id=? AND status='queued'",
                    (now, r[0]),
                )
                claimed.append({"event_id": r[0], "source_id": r[1], "rel_path": r[2],
                                "source_root_key": r[3], "event_type": r[4]})
            return claimed

    def complete_event(self, event_id: str, status: str, *, error_code: str | None = None,
                       conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_intelligence_events SET status=?, error_code=?, updated_at=? WHERE event_id=?",
                (status, error_code, _now(), event_id),
            )

    def requeue_stuck(self, ttl_seconds: int = 900, *, conn: sqlite3.Connection | None = None) -> int:
        """Re-queue events stuck in 'processing' (e.g. across a crash). Returns count."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE source_intelligence_events SET status='queued', updated_at=? "
                "WHERE status='processing' AND (julianday('now') - julianday(updated_at)) * 86400 > ?",
                (_now(), int(ttl_seconds)),
            )
            return cur.rowcount or 0

    # ----- search ----------------------------------------------------------------------------
    def search_sources(self, query: str, *, limit: int = 20, project_key: str | None = None,
                       conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            if not self._fts_available(c):
                return []
            sql = (
                "SELECT f.rel_path, f.aux, bm25(source_intelligence_fts) AS rank, "
                " snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip, s.source_id "
                "FROM source_intelligence_fts f "
                "JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid "
                "JOIN source_intelligence_sources s ON s.source_id = m.source_id "
                "WHERE source_intelligence_fts MATCH ? AND s.deleted=0 AND s.source_kind='external_file' "
            )
            params: list[Any] = [query]
            if project_key:
                sql += "AND f.aux = ? "
                params.append(project_key)
            sql += "ORDER BY rank LIMIT ?"
            params.append(int(limit))
            rows = c.execute(sql, params).fetchall()
        return [
            {"result_type": "source", "source_id": r[4], "path": r[0], "project_key": r[1] or None,
             "score": float(r[2]), "snippet": r[3]}
            for r in rows
        ]

    def search_notes(self, query: str, *, limit: int = 20, path_prefix: str | None = None,
                     conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            if not self._fts_available(c):
                return []
            sql = (
                "SELECT n.rel_path, n.aux, bm25(obsidian_note_fts) AS rank, "
                " snippet(obsidian_note_fts, 0, '[', ']', '…', 12) AS snip, s.source_id "
                "FROM obsidian_note_fts n "
                "JOIN source_intelligence_metadata m ON m.fts_rowid = n.rowid "
                "JOIN source_intelligence_sources s ON s.source_id = m.source_id AND s.source_kind='obsidian_note' "
                "WHERE obsidian_note_fts MATCH ? AND s.deleted=0 "
            )
            params: list[Any] = [query]
            if path_prefix:
                sql += "AND n.rel_path LIKE ? "
                params.append(f"{path_prefix}%")
            sql += "ORDER BY rank LIMIT ?"
            params.append(int(limit))
            rows = c.execute(sql, params).fetchall()
        return [
            {"result_type": "obsidian_note", "source_id": r[4], "path": r[0], "tags": r[1] or None,
             "score": float(r[2]), "snippet": r[3]}
            for r in rows
        ]

    # ----- status ----------------------------------------------------------------------------
    def index_status(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        with borrow_connection(conn, self.db_path) as c:
            fts = self._fts_available(c)
            by_kind = {
                row[0]: row[1]
                for row in c.execute(
                    "SELECT source_kind, COUNT(*) FROM source_intelligence_sources "
                    "WHERE deleted=0 GROUP BY source_kind"
                ).fetchall()
            }
            total = sum(by_kind.values())
            queued = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='queued'"
            ).fetchone()[0]
            processing = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='processing'"
            ).fetchone()[0]
            errors = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='error'"
            ).fetchone()[0]
            last_indexed = c.execute(
                "SELECT MAX(indexed_at) FROM source_intelligence_metadata"
            ).fetchone()[0]
            stale_notes = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE generation_status='stale'"
            ).fetchone()[0]
            roots_row = c.execute(
                "SELECT state_value FROM source_intelligence_state WHERE state_key='source_roots'"
            ).fetchone()
            summarized = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0]
            stale_summaries = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_summaries s "
                "JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "WHERE s.source_sha256 IS NOT m.content_sha256"
            ).fetchone()[0]
        roots = json.loads(roots_row[0]) if roots_row and roots_row[0] else []
        return {
            "fts_available": fts,
            "sources_total": total,
            "by_kind": by_kind,
            "queued_count": queued,
            "processing_count": processing,
            "error_count": errors,
            "stale_note_count": stale_notes,
            "summarized_count": int(summarized),
            "stale_summary_count": int(stale_summaries),
            "last_indexed_at": last_indexed,
            "configured_roots": roots,
        }

    def queue_health(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Operator queue-health signals: stuck-event age + recent-activity timestamps.

        Reads only existing tables (events + the source_intelligence_state k/v rows stamped by
        drain/note/summary); no schema change. ``oldest_processing_age_seconds`` is None when
        nothing is in-flight.
        """
        with borrow_connection(conn, self.db_path) as c:
            counts = {
                status: c.execute(
                    "SELECT COUNT(*) FROM source_intelligence_events WHERE status=?", (status,)
                ).fetchone()[0]
                for status in ("queued", "processing", "error", "done")
            }
            oldest_age = c.execute(
                "SELECT (julianday('now') - julianday(MIN(updated_at))) * 86400 "
                "FROM source_intelligence_events WHERE status='processing'"
            ).fetchone()[0]
            last_event_at = c.execute(
                "SELECT MAX(created_at) FROM source_intelligence_events"
            ).fetchone()[0]
            state = {
                row[0]: row[1]
                for row in c.execute(
                    "SELECT state_key, state_value FROM source_intelligence_state "
                    "WHERE state_key IN ('last_drain_at','last_note_at','last_summary_at')"
                ).fetchall()
            }
        return {
            "queued_count": counts["queued"],
            "processing_count": counts["processing"],
            "error_count": counts["error"],
            "done_count": counts["done"],
            "oldest_processing_age_seconds": (round(float(oldest_age), 1) if oldest_age is not None else None),
            "last_event_at": last_event_at,
            "last_drain_at": state.get("last_drain_at"),
            "last_note_at": state.get("last_note_at"),
            "last_summary_at": state.get("last_summary_at"),
        }
