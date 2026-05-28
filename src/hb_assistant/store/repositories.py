"""Store facade and repositories for source_records + child tables.

All upserts are by (source_type, source_key) with last_seen_at bump.
Returns the integer source_record_id.
Redacted/minimal fields only — never full bodies or file content.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.normalize.attachment import Attachment
from hb_assistant.normalize.calendar_event import CalendarEvent
from hb_assistant.normalize.drive_item import DriveItem
from hb_assistant.normalize.email import Email

from .connection import get_connection, transaction


class Store:
    """High-level facade over the SQLite store (Phase 5 MVP).

    Prefer using SourceLinkRegistry for high-level persist operations that enforce links.
    Direct use of Store is for low-level / testing scenarios.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        # Ensure schema on first use (cheap idempotent call)
        from .migrator import SQLiteMigrator

        SQLiteMigrator(db_path).apply()

    # --- Source records (universal) ---

    def upsert_source_record(
        self,
        *,
        source_type: str,
        source_key: str,
        source_system: str,
        title_redacted: Optional[str] = None,
        source_url: Optional[str] = None,
        external_id: Optional[str] = None,
        immutable_id: Optional[str] = None,
        content_hash: Optional[str] = None,
        metadata_hash: Optional[str] = None,
    ) -> int:
        """Upsert a source_record. Returns its id (new or existing)."""
        conn = get_connection(self._db_path)
        now = datetime.now(timezone.utc).isoformat()
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO source_records
                    (source_type, source_key, source_system, title_redacted, source_url,
                     external_id, immutable_id, content_hash, metadata_hash, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_key) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    title_redacted = COALESCE(excluded.title_redacted, source_records.title_redacted),
                    source_url = COALESCE(excluded.source_url, source_records.source_url)
                RETURNING id
                """,
                (
                    source_type,
                    source_key,
                    source_system,
                    title_redacted,
                    source_url,
                    external_id,
                    immutable_id,
                    content_hash,
                    metadata_hash,
                    now,
                ),
            )
            row = cur.fetchone()
            return int(row[0])

    def get_source_record(self, source_record_id: int) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT * FROM source_records WHERE id = ?", (source_record_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Emails ---

    def persist_email(self, email: Email, source_key: str | None = None) -> int:
        """Persist a redacted Email (from Phase 4 MailClient). Returns source_record_id."""
        key = source_key or f"graph:mail:{email.id}"
        sid = self.upsert_source_record(
            source_type="graph:mail",
            source_key=key,
            source_system="microsoft-graph",
            title_redacted=email.subject_redacted,
            source_url=email.web_link,
            external_id=email.id,
            immutable_id=email.immutable_id or email.internet_message_id,
            metadata_hash=None,  # caller may supply
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO emails (source_record_id, folder, conversation_id, internet_message_id,
                                    sender_domain, received_datetime, sent_datetime, has_attachments,
                                    body_checked, body_mention_detected, web_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                ON CONFLICT(source_record_id) DO UPDATE SET
                    has_attachments = excluded.has_attachments
                """,
                (
                    sid,
                    email.folder,
                    email.conversation_id,
                    email.internet_message_id,
                    email.sender_domain,
                    email.received_datetime.isoformat() if email.received_datetime else None,
                    email.sent_datetime.isoformat() if email.sent_datetime else None,
                    1 if email.has_attachments else 0,
                    email.web_link,
                ),
            )
        # Update the model in-memory for caller convenience
        email.source_record_id = sid
        return sid

    # --- Calendar events ---

    def persist_calendar_event(self, event: CalendarEvent, source_key: str | None = None) -> int:
        key = source_key or f"graph:event:{event.id}"
        sid = self.upsert_source_record(
            source_type="graph:event",
            source_key=key,
            source_system="microsoft-graph",
            title_redacted=event.subject_redacted,
            source_url=event.web_link,
            external_id=event.id,
            immutable_id=event.ical_uid,
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_events (source_record_id, ical_uid, start_datetime, end_datetime,
                                             timezone, is_cancelled, is_private, web_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_record_id) DO NOTHING
                """,
                (
                    sid,
                    event.ical_uid,
                    event.start.isoformat() if event.start else None,
                    event.end.isoformat() if event.end else None,
                    event.timezone,
                    1 if event.is_cancelled else 0,
                    1 if event.is_private else 0,
                    event.web_link,
                ),
            )
        event.source_record_id = sid
        return sid

    # --- Attachments (metadata only) ---

    def persist_attachment(self, att: Attachment, parent_source_record_id: int, source_key: str | None = None) -> int:
        key = source_key or f"graph:attachment:{att.id}"
        sid = self.upsert_source_record(
            source_type="graph:attachment",
            source_key=key,
            source_system="microsoft-graph",
            title_redacted=att.name,
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO attachments (source_record_id, parent_source_record_id, attachment_id,
                                         name, content_type, size_bytes, is_inline, eligibility_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_record_id) DO NOTHING
                """,
                (
                    sid,
                    parent_source_record_id,
                    att.id,
                    att.name,
                    att.content_type,
                    att.size,
                    1 if att.is_inline else 0,
                    "metadata_only",
                ),
            )
        att.source_record_id = sid
        return sid

    # --- Drive items / files (metadata) ---

    def persist_drive_item(self, item: DriveItem, source_key: str | None = None) -> int:
        key = source_key or f"graph:drive-item:{item.id}"
        sid = self.upsert_source_record(
            source_type="graph:drive-item",
            source_key=key,
            source_system="microsoft-graph",
            title_redacted=item.name,
            source_url=item.web_url,
            external_id=item.id,
            content_hash=item.e_tag,  # rough
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            ext = None
            if item.name and "." in item.name:
                ext = item.name.rsplit(".", 1)[-1].lower()
            conn.execute(
                """
                INSERT INTO files (source_record_id, drive_item_id, name, extension, size_bytes,
                                   web_url, sha256, local_cache_path, download_status, parse_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_record_id) DO NOTHING
                """,
                (
                    sid,
                    item.id,
                    item.name,
                    ext,
                    item.size,
                    item.web_url,
                    None,
                    item.cached_path,
                    item.download_status or "not_downloaded",
                    item.download_status or "not_parsed",
                ),
            )
        item.source_record_id = sid
        return sid

    # --- Assistant run ledger (for run_cmd and automation) ---

    def record_assistant_run(
        self,
        *,
        run_type: str,
        target_date: str,
        trigger: str,
        dry_run: bool,
        status: str = "started",
    ) -> int:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO assistant_runs (run_type, target_date, trigger, dry_run, status)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                (run_type, target_date, trigger, 1 if dry_run else 0, status),
            )
            row = cur.fetchone()
            return int(row[0])

    def finish_assistant_run(self, run_id: int, status: str = "completed") -> None:
        conn = get_connection(self._db_path)
        now = datetime.now(timezone.utc).isoformat()
        with transaction(conn):
            conn.execute(
                "UPDATE assistant_runs SET status = ?, finished_at = ? WHERE id = ?",
                (status, now, run_id),
            )

    # --- Source links (low-level; prefer registry) ---

    def create_source_link(
        self,
        *,
        from_source_record_id: Optional[int],
        to_source_record_id: Optional[int],
        action_item_id: Optional[int] = None,
        link_type: str,
        confidence: Optional[float] = None,
    ) -> int:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO source_links (from_source_record_id, to_source_record_id, action_item_id, link_type, confidence)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                (from_source_record_id, to_source_record_id, action_item_id, link_type, confidence),
            )
            row = cur.fetchone()
            return int(row[0])

    def get_links_for_source(self, source_record_id: int) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT * FROM source_links WHERE from_source_record_id = ? OR to_source_record_id = ?",
            (source_record_id, source_record_id),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Phase 8: minimal action_item helpers for Daily Brief (excerpts + links only, never full bodies) ---

    def get_recent_action_items(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent open action_items (for brief generation)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT id, stable_key, action_type, title, due_date, confidence, status
            FROM action_items
            WHERE status = 'open'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_action_items_for_source(self, source_record_id: int) -> list[dict[str, Any]]:
        """Return action_items linked to a given source_record via source_links."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT ai.*
            FROM action_items ai
            JOIN source_links sl ON sl.action_item_id = ai.id
            WHERE sl.from_source_record_id = ? OR sl.to_source_record_id = ?
            """,
            (source_record_id, source_record_id),
        )
        return [dict(r) for r in cur.fetchall()]

    def upsert_action_item(
        self,
        *,
        stable_key: str,
        action_type: str,
        title: str,
        confidence: float,
        due_date: Optional[str] = None,
        status: str = "open",
    ) -> int:
        """Upsert action_item by stable_key. Returns id (new or existing).

        Preserves completed status/completed_at on re-seen (never resets completed items).
        Updates other fields safely with COALESCE per upsert_source_record pattern.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO action_items
                    (stable_key, action_type, title, due_date, confidence, status, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stable_key) DO UPDATE SET
                    action_type = excluded.action_type,
                    title = COALESCE(excluded.title, action_items.title),
                    due_date = COALESCE(excluded.due_date, action_items.due_date),
                    confidence = excluded.confidence,
                    status = CASE
                        WHEN action_items.status = 'completed' OR action_items.completed_at IS NOT NULL
                        THEN action_items.status
                        ELSE excluded.status
                    END,
                    completed_at = COALESCE(action_items.completed_at, excluded.completed_at)
                RETURNING id
                """,
                (stable_key, action_type, title, due_date, confidence, status, None),
            )
            row = cur.fetchone()
            return int(row[0])

    def get_action_item_by_stable_key(self, stable_key: str) -> Optional[dict[str, Any]]:
        """Return action_item by stable_key or None (for tests/verification)."""
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT * FROM action_items WHERE stable_key = ?", (stable_key,))
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Phase 6: body classification flag helpers (minimal, no body text ever read or written) ---

    def get_emails_needing_body_check(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return source_records + basic email metadata for emails not yet body-checked.

        Returns only metadata + redacted preview (never full body). Used by classification batch jobs.
        """
        conn = get_connection(self._db_path)
        # Join source_records + emails where body_checked=0
        cur = conn.execute(
            """
            SELECT sr.id as source_record_id, sr.source_key, sr.title_redacted,
                   e.folder, e.sender_domain, e.received_datetime, e.web_link,
                   e.body_checked, e.body_mention_detected,
                   e.body_detection_method, e.body_match_excerpt_redacted
            FROM source_records sr
            JOIN emails e ON e.source_record_id = sr.id
            WHERE e.body_checked = 0
            ORDER BY sr.last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def update_email_body_flags(
        self,
        source_record_id: int,
        *,
        body_checked: bool,
        body_mention_detected: bool,
        body_detection_method: Optional[str] = None,
        body_match_excerpt_redacted: Optional[str] = None,
    ) -> None:
        """Idempotent update of body classification flags + Prompt 05 detection metadata.

        Additive columns (body_detection_method, body_match_excerpt_redacted) are
        optional and ignored on older DB schemas.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            # Base columns always present
            conn.execute(
                """
                UPDATE emails
                SET body_checked = ?, body_mention_detected = ?
                WHERE source_record_id = ?
                """,
                (1 if body_checked else 0, 1 if body_mention_detected else 0, source_record_id),
            )
            # Additive P05 columns (best-effort; older schemas silently ignore via try)
            if body_detection_method is not None or body_match_excerpt_redacted is not None:
                try:
                    conn.execute(
                        """
                        UPDATE emails
                        SET body_detection_method = COALESCE(?, body_detection_method),
                            body_match_excerpt_redacted = COALESCE(?, body_match_excerpt_redacted)
                        WHERE source_record_id = ?
                        """,
                        (body_detection_method, body_match_excerpt_redacted, source_record_id),
                    )
                except Exception:
                    pass  # schema not yet migrated or column missing — safe no-op

    # --- Diagnostics / counts (safe, redacted) ---

    def get_summary(self) -> dict[str, Any]:
        conn = get_connection(self._db_path)
        summary: dict[str, Any] = {"db_path": str(self._db_path or "default")}
        tables = ["source_records", "emails", "calendar_events", "attachments", "files", "assistant_runs", "source_links"]
        for t in tables:
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {t}")
                summary[t] = cur.fetchone()[0]
            except sqlite3.OperationalError:
                summary[t] = "missing"
        # Last run (redacted)
        cur = conn.execute("SELECT id, run_type, target_date, trigger, dry_run, status, started_at FROM assistant_runs ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            summary["last_run"] = {
                "id": row[0],
                "run_type": row[1],
                "target_date": row[2],
                "trigger": row[3],
                "dry_run": bool(row[4]),
                "status": row[5],
                "started_at": row[6],
            }
        return summary

    # --- Phase 9: file/attachment/parser_output persistence (excerpts + status only) ---

    def persist_file(self, drive_item: "DriveItem", source_record_id: int, sha256: Optional[str] = None, local_cache: Optional[str] = None) -> int:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO files (source_record_id, drive_item_id, name, size_bytes, web_url, sha256, local_cache_path, download_status, parse_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'downloaded', 'not_parsed')
                ON CONFLICT(source_record_id) DO UPDATE SET download_status='downloaded', sha256=COALESCE(excluded.sha256, files.sha256), local_cache_path=COALESCE(excluded.local_cache_path, files.local_cache_path)
                """,
                (source_record_id, drive_item.id, drive_item.name, drive_item.size, drive_item.web_url, sha256, local_cache),
            )
        return source_record_id

    def update_file_status(self, source_record_id: int, *, download_status: Optional[str] = None, parse_status: Optional[str] = None) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            sets, vals = [], []
            if download_status: sets.append("download_status=?"); vals.append(download_status)
            if parse_status: sets.append("parse_status=?"); vals.append(parse_status)
            if sets:
                conn.execute(f"UPDATE files SET {', '.join(sets)} WHERE source_record_id=?", vals + [source_record_id])

    def persist_parser_output(self, file_source_record_id: int, parser_name: str, parser_version: str, content_hash: str, excerpt: str, char_count: int, status: str = "success") -> int:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                "INSERT INTO parser_outputs (file_source_record_id, parser_name, parser_version, content_hash, extraction_status, text_excerpt, char_count) VALUES (?,?,?,?,?,?,?) RETURNING id",
                (file_source_record_id, parser_name, parser_version, content_hash, status, excerpt, char_count),
            )
            return int(cur.fetchone()[0])

    # --- Phase 10: file/parser_output query helpers (for tests, CLI, validation, selective status) ---

    def get_file(self, source_record_id: int) -> Optional[dict[str, Any]]:
        """Return files row for a source (post DL)."""
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT * FROM files WHERE source_record_id = ?", (source_record_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_parser_outputs(self, file_source_record_id: int) -> list[dict[str, Any]]:
        """Return parser outputs linked to a file (excerpts only, never full content)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT * FROM parser_outputs WHERE file_source_record_id = ? ORDER BY id DESC",
            (file_source_record_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_files_by_status(
        self,
        download_status: Optional[str] = None,
        parse_status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query files by status (for smoke tests / monitoring)."""
        conn = get_connection(self._db_path)
        where: list[str] = []
        vals: list[Any] = []
        if download_status:
            where.append("download_status=?")
            vals.append(download_status)
        if parse_status:
            where.append("parse_status=?")
            vals.append(parse_status)
        sql = "SELECT * FROM files"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY source_record_id DESC LIMIT ?"
        vals.append(limit)
        cur = conn.execute(sql, vals)
        return [dict(r) for r in cur.fetchall()]

    def list_pending_ingest_candidates(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return provenance-backed drive file candidates not yet fully ingested."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_record_id, drive_item_id, name, size_bytes, web_url, download_status, parse_status
            FROM files
            WHERE source_record_id > 0
              AND (download_status IS NULL OR download_status != 'downloaded'
                   OR parse_status IS NULL OR parse_status != 'success')
            ORDER BY source_record_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def list_upcoming_calendar_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return upcoming calendar rows (metadata only, bounded)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_record_id, start_datetime, end_datetime, web_link, is_cancelled
            FROM calendar_events
            WHERE is_cancelled = 0
            ORDER BY start_datetime ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def list_file_review_queue(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return files needing review/processing (metadata only, bounded)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_record_id, name, size_bytes, download_status, parse_status
            FROM files
            WHERE download_status != 'downloaded'
               OR parse_status != 'success'
            ORDER BY source_record_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def list_recent_body_mentions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return source records flagged by body mention detection (redacted metadata only)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT sr.id as source_record_id, sr.title_redacted, e.sender_domain, e.web_link
            FROM source_records sr
            JOIN emails e ON e.source_record_id = sr.id
            WHERE e.body_mention_detected = 1
            ORDER BY sr.last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Phase 11: retrieval helpers (redacted excerpts/previews only, for Retriever) ---

    def list_recent_parser_outputs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Recent parser outputs for retrieval (excerpts only)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT * FROM parser_outputs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    # email retrieval helper removed for schema compat (emails table stores flags + redacted subject not preview text); parser_outputs + actions sufficient for Phase 11 MVP


# =============================================================================
# Prompt_09: Procore pilot sync — additive tables + repository helpers (idempotent)
# All writes are local-only. No external mutation. Redacted fields only.
# Tables created IF NOT EXISTS on first use (additive, safe with migrator).
# =============================================================================

import json  # local to this additive section (module already likely imports it)


def _ensure_procore_sync_tables(db_path: Optional[Path] = None) -> None:
    """Idempotent additive table creation for Prompt_09 sync receipts + normalized entities + watermarks."""
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS procore_sync_runs (
            id TEXT PRIMARY KEY,
            correlation_id TEXT,
            mode TEXT NOT NULL,
            pilot_project_key TEXT NOT NULL,
            company_id TEXT NOT NULL DEFAULT '5280',
            started_at TEXT,
            completed_at TEXT,
            audit_prerequisite_passed INTEGER,
            total_planned_requests INTEGER,
            total_items_normalized INTEGER,
            persisted_to_sqlite INTEGER,
            policy_used TEXT,
            receipt_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS procore_sync_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            correlation_id TEXT,
            endpoint_id TEXT,
            error_code TEXT,
            message_redacted TEXT,
            http_status INTEGER,
            retry_count INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS procore_synced_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_project_key TEXT NOT NULL,
            endpoint_id TEXT NOT NULL,
            entity_stable_key TEXT NOT NULL,
            category TEXT,
            review_required INTEGER DEFAULT 0,
            canonical_fields_json TEXT,
            fetched_at TEXT,
            correlation_id TEXT,
            redaction_applied INTEGER DEFAULT 1,
            last_seen_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source_project_key, endpoint_id, entity_stable_key)
        );

        CREATE TABLE IF NOT EXISTS procore_sync_watermarks (
            endpoint_id TEXT NOT NULL,
            project_key TEXT NOT NULL,
            last_successful_watermark TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (endpoint_id, project_key)
        );

        CREATE INDEX IF NOT EXISTS idx_procore_synced_entities_project_endpoint
            ON procore_synced_entities(source_project_key, endpoint_id);
        """
    )
    conn.commit()


def upsert_procore_sync_run(
    db_path: Optional[Path],
    receipt: Dict[str, Any],
    correlation: Optional[str] = None,
) -> None:
    """Persist run receipt (dry-run or apply). Idempotent on sync_id."""
    _ensure_procore_sync_tables(db_path)
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO procore_sync_runs
        (id, correlation_id, mode, pilot_project_key, company_id, started_at, completed_at,
         audit_prerequisite_passed, total_planned_requests, total_items_normalized,
         persisted_to_sqlite, policy_used, receipt_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            receipt.get("sync_id"),
            correlation or receipt.get("correlation_id"),
            receipt.get("mode"),
            receipt.get("pilot_project_key"),
            receipt.get("company_id", "5280"),
            receipt.get("started_at"),
            receipt.get("completed_at"),
            1 if receipt.get("audit_prerequisite_passed") else 0,
            receipt.get("total_planned_requests", 0),
            receipt.get("total_items_normalized", 0),
            1 if receipt.get("persisted_to_sqlite") else 0,
            receipt.get("policy_used", "auto"),
            json.dumps(redact_for_evidence(receipt)),  # double redaction belt-and-suspenders
        ),
    )
    conn.commit()


def upsert_procore_sync_error(
    db_path: Optional[Path],
    run_id: str,
    error: Dict[str, Any],
    correlation: Optional[str] = None,
) -> None:
    """Log redacted error for a sync run."""
    _ensure_procore_sync_tables(db_path)
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO procore_sync_errors
        (run_id, correlation_id, endpoint_id, error_code, message_redacted, http_status, retry_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            correlation,
            error.get("endpoint_id") or error.get("endpoint"),
            error.get("error_code") or error.get("error"),
            error.get("message_redacted") or str(error)[:500],
            error.get("http_status"),
            error.get("retry_count", 0),
        ),
    )
    conn.commit()


def upsert_procore_synced_entity(
    db_path: Optional[Path],
    entity: Dict[str, Any],
    correlation: Optional[str] = None,
) -> None:
    """Idempotent upsert of normalized Procore entity row (local only)."""
    _ensure_procore_sync_tables(db_path)
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO procore_synced_entities
        (source_project_key, endpoint_id, entity_stable_key, category, review_required,
         canonical_fields_json, fetched_at, correlation_id, redaction_applied, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_project_key, endpoint_id, entity_stable_key) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            canonical_fields_json = excluded.canonical_fields_json,
            redaction_applied = excluded.redaction_applied
        """,
        (
            entity["source_project_key"],
            entity["endpoint_id"],
            entity["entity_stable_key"],
            entity.get("category"),
            1 if entity.get("review_required") else 0,
            json.dumps(entity.get("canonical_fields", {})),
            entity.get("fetched_at"),
            correlation or entity.get("correlation_id"),
            1 if entity.get("redaction_applied", True) else 0,
            entity.get("last_seen_at") or entity.get("fetched_at"),
        ),
    )
    conn.commit()


def get_procore_sync_watermark(
    db_path: Optional[Path], endpoint_id: str, project_key: str
) -> Optional[str]:
    """Return last successful watermark/cursor for incremental policy (redacted safe)."""
    _ensure_procore_sync_tables(db_path)
    conn = get_connection(db_path)
    cur = conn.execute(
        "SELECT last_successful_watermark FROM procore_sync_watermarks WHERE endpoint_id = ? AND project_key = ?",
        (endpoint_id, project_key),
    )
    row = cur.fetchone()
    return row[0] if row else None


def set_procore_sync_watermark(
    db_path: Optional[Path], endpoint_id: str, project_key: str, watermark: str
) -> None:
    """Store/update watermark after successful apply (no secrets)."""
    _ensure_procore_sync_tables(db_path)
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO procore_sync_watermarks (endpoint_id, project_key, last_successful_watermark, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (endpoint_id, project_key, watermark),
    )
    conn.commit()
