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
                   e.body_checked, e.body_mention_detected
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
    ) -> None:
        """Idempotent update of the two body classification flags on the emails row."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                UPDATE emails
                SET body_checked = ?, body_mention_detected = ?
                WHERE source_record_id = ?
                """,
                (1 if body_checked else 0, 1 if body_mention_detected else 0, source_record_id),
            )

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
