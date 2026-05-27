"""Construction-agent SQLite repositories (V2 schema; metadata only).

Persists Graph source resolutions, per-source delta tokens, drive-item
inventory snapshots, and crawl receipts. **Never** stores body, content,
or text excerpts — only metadata identifiers and provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConstructionStore:
    """Thin facade over construction_* tables added in V2 migration."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        SQLiteMigrator(db_path).apply()

    # --- source resolutions -------------------------------------------------

    def upsert_resolution(
        self,
        *,
        source_key: str,
        kind: str,
        site_id: Optional[str],
        drive_id: Optional[str],
        web_url: Optional[str],
        resolution_status: str,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_source_resolutions
                    (source_key, kind, site_id, drive_id, web_url,
                     resolution_status, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    kind = excluded.kind,
                    site_id = COALESCE(excluded.site_id, construction_source_resolutions.site_id),
                    drive_id = COALESCE(excluded.drive_id, construction_source_resolutions.drive_id),
                    web_url = COALESCE(excluded.web_url, construction_source_resolutions.web_url),
                    resolution_status = excluded.resolution_status,
                    resolved_at = excluded.resolved_at
                """,
                (source_key, kind, site_id, drive_id, web_url, resolution_status, _utc_now()),
            )

    def get_resolution(self, source_key: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_key, kind, site_id, drive_id, web_url,
                   resolution_status, resolved_at
            FROM construction_source_resolutions
            WHERE source_key = ?
            """,
            (source_key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = ("source_key", "kind", "site_id", "drive_id", "web_url",
                "resolution_status", "resolved_at")
        return dict(zip(keys, row, strict=True))

    # --- delta tokens -------------------------------------------------------

    def get_delta_token(self, source_key: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_key, drive_id, delta_link, page_count, last_status, last_sync_at
            FROM construction_delta_tokens
            WHERE source_key = ?
            """,
            (source_key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = ("source_key", "drive_id", "delta_link", "page_count", "last_status", "last_sync_at")
        return dict(zip(keys, row, strict=True))

    def set_delta_token(
        self,
        *,
        source_key: str,
        drive_id: str,
        delta_link: Optional[str],
        page_count: int,
        last_status: str,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_delta_tokens
                    (source_key, drive_id, delta_link, page_count, last_status, last_sync_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    drive_id = excluded.drive_id,
                    delta_link = excluded.delta_link,
                    page_count = excluded.page_count,
                    last_status = excluded.last_status,
                    last_sync_at = excluded.last_sync_at
                """,
                (source_key, drive_id, delta_link, page_count, last_status, _utc_now()),
            )

    # --- inventory ----------------------------------------------------------

    def upsert_inventory_item(
        self,
        *,
        source_key: str,
        drive_id: str,
        item_id: str,
        name: Optional[str],
        web_url: Optional[str],
        parent_path: Optional[str],
        size_bytes: Optional[int],
        is_folder: bool,
        last_modified: Optional[str],
        etag: Optional[str],
    ) -> str:
        """Upsert a metadata-only inventory row; returns 'new' or 'updated'."""
        conn = get_connection(self._db_path)
        now = _utc_now()
        with transaction(conn):
            cur = conn.execute(
                "SELECT 1 FROM construction_drive_item_inventory WHERE source_key = ? AND item_id = ?",
                (source_key, item_id),
            )
            existed = cur.fetchone() is not None
            conn.execute(
                """
                INSERT INTO construction_drive_item_inventory
                    (source_key, drive_id, item_id, name, web_url, parent_path,
                     size_bytes, is_folder, last_modified, etag, status,
                     first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                ON CONFLICT(source_key, item_id) DO UPDATE SET
                    drive_id = excluded.drive_id,
                    name = excluded.name,
                    web_url = excluded.web_url,
                    parent_path = excluded.parent_path,
                    size_bytes = excluded.size_bytes,
                    is_folder = excluded.is_folder,
                    last_modified = excluded.last_modified,
                    etag = excluded.etag,
                    status = 'active',
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    source_key, drive_id, item_id, name, web_url, parent_path,
                    size_bytes, 1 if is_folder else 0, last_modified, etag,
                    now, now,
                ),
            )
        return "updated" if existed else "new"

    def mark_inventory_deleted(self, *, source_key: str, item_id: str) -> bool:
        """Mark an inventory row deleted (status='deleted'). Returns True if a row matched."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                UPDATE construction_drive_item_inventory
                SET status = 'deleted', last_seen_at = ?
                WHERE source_key = ? AND item_id = ?
                """,
                (_utc_now(), source_key, item_id),
            )
            return cur.rowcount > 0

    def count_inventory(self, source_key: str) -> dict[str, int]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT status, COUNT(*) FROM construction_drive_item_inventory
            WHERE source_key = ?
            GROUP BY status
            """,
            (source_key,),
        )
        return dict(cur.fetchall())

    def list_inventory_changed_since(
        self,
        source_key: str,
        since_iso: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return inventory rows with last_seen_at > since_iso (most recent first)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_key, drive_id, item_id, name, web_url, parent_path,
                   size_bytes, is_folder, last_modified, etag, status,
                   first_seen_at, last_seen_at
            FROM construction_drive_item_inventory
            WHERE source_key = ? AND last_seen_at > ?
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (source_key, since_iso, limit),
        )
        keys = ("source_key", "drive_id", "item_id", "name", "web_url", "parent_path",
                "size_bytes", "is_folder", "last_modified", "etag", "status",
                "first_seen_at", "last_seen_at")
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # --- receipts -----------------------------------------------------------

    def insert_crawl_receipt(
        self,
        *,
        run_id: str,
        source_key: str,
        mode: str,
        started_at: str,
        finished_at: Optional[str],
        pages_seen: int,
        items_seen: int,
        items_new: int,
        items_updated: int,
        items_deleted: int,
        delta_link_recorded: bool,
        status: str,
        error_redacted: Optional[str] = None,
    ) -> int:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO construction_crawl_receipts
                    (run_id, source_key, mode, started_at, finished_at,
                     pages_seen, items_seen, items_new, items_updated,
                     items_deleted, delta_link_recorded, status, error_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, source_key, mode, started_at, finished_at,
                    pages_seen, items_seen, items_new, items_updated,
                    items_deleted, 1 if delta_link_recorded else 0,
                    status, error_redacted,
                ),
            )
            return int(cur.lastrowid)

    def list_recent_receipts(self, source_key: str, limit: int = 5) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT id, run_id, mode, started_at, finished_at, pages_seen,
                   items_seen, items_new, items_updated, items_deleted,
                   delta_link_recorded, status, error_redacted
            FROM construction_crawl_receipts
            WHERE source_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (source_key, limit),
        )
        keys = ("id", "run_id", "mode", "started_at", "finished_at", "pages_seen",
                "items_seen", "items_new", "items_updated", "items_deleted",
                "delta_link_recorded", "status", "error_redacted")
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]
