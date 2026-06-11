"""Construction-agent SQLite repositories (V2-V5 schema; metadata only).

Persists Graph source resolutions, per-source delta tokens, drive-item
inventory snapshots, and crawl receipts (V2); review queue (V3); model
decisions (V4); and the canonical Phase 02 alignment layer — source
locations, sync state, crawl runs, drive items, project identity,
project↔source matches, document cards, processing receipts, sync errors,
and the email-intelligence deferred-state singleton (V5). **Never** stores
body, content, or text excerpts — only metadata identifiers and provenance.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_older_than(earlier_iso: str, reference_iso: str, seconds: int) -> bool:
    """True when ``earlier_iso`` is at least ``seconds`` before ``reference_iso``.

    Used for retry-backoff eligibility. Unparseable timestamps are treated as eligible (True)
    so a malformed receipt never permanently blocks a job.
    """

    def _parse(value: str) -> Optional[datetime]:
        try:
            text = value.replace("Z", "+00:00") if value.endswith("Z") else value
            dt = datetime.fromisoformat(text)
        except (ValueError, AttributeError):
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    a = _parse(earlier_iso)
    b = _parse(reference_iso)
    if a is None or b is None:
        return True
    return (b - a).total_seconds() >= seconds


class CalendarBatchApplyError(RuntimeError):
    """Calendar apply failed after producing a sanitized operation diagnostic."""

    def __init__(self, diagnostic: dict[str, Any]) -> None:
        self.diagnostic = diagnostic
        operation = diagnostic.get("operation") or "calendar_apply"
        exception_type = diagnostic.get("exception_type") or "Exception"
        super().__init__(f"{operation}:{exception_type}")


class EmailDiscoverBatchApplyError(RuntimeError):
    """Email project discover batch apply failed after producing a sanitized operation diagnostic.

    Used for all-project (and scoped) discover hardening: single-tx batch for messages +
    recipients + matches + receipt + sync/crawl side effects. On failure, best-effort
    failed receipt written in separate tx (redacted diag only: op, msg_id_hash, pk, exc_type).
    """

    def __init__(self, diagnostic: dict[str, Any]) -> None:
        self.diagnostic = diagnostic
        operation = diagnostic.get("operation") or "email_discover_apply"
        exception_type = diagnostic.get("exception_type") or "Exception"
        super().__init__(f"{operation}:{exception_type}")


# Column order for construction_drive_items reads (V5 base + V15 rich metadata).
_DRIVE_ITEM_KEYS: tuple[str, ...] = (
    "source_id",
    "drive_id",
    "drive_item_id",
    "parent_drive_item_id",
    "site_id",
    "list_id",
    "list_item_id",
    "name",
    "path",
    "web_url",
    "is_folder",
    "is_file",
    "file_extension",
    "mime_type",
    "size_bytes",
    "last_modified_datetime",
    "deleted",
    "quick_xor_hash",
    "project_number_detected",
    "document_type_detected",
    "indexing_policy",
    "classification_status",
    "created_utc",
    "updated_utc",
    "is_package",
    "e_tag",
    "c_tag",
    "created_datetime",
    "parent_reference_path",
    "folder_child_count",
    "sharepoint_web_id",
    "sharepoint_list_item_id",
    "file_hashes_json",
    "package_json_redacted",
    "remote_item_json_redacted",
    "first_seen_utc",
    "last_seen_utc",
    "project_key",
    "match_confidence",
    "match_status",
    "review_required",
    "review_reason",
    "match_signals_json",
    "parent_folder_name",
    "last_modified_by_display_name",
    "last_modified_by_user_id",
    "last_modified_by_email",
    "last_modified_by_application_display_name",
    "last_modified_by_raw_json",
)


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
        keys = (
            "source_key",
            "kind",
            "site_id",
            "drive_id",
            "web_url",
            "resolution_status",
            "resolved_at",
        )
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
                    source_key,
                    drive_id,
                    item_id,
                    name,
                    web_url,
                    parent_path,
                    size_bytes,
                    1 if is_folder else 0,
                    last_modified,
                    etag,
                    now,
                    now,
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

    def list_inventory(
        self,
        *,
        source_key: str,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Iterate V2 ``construction_drive_item_inventory`` rows for a source.

        Used by the V2↔V5 drive-item bridge to enumerate legacy inventory
        without creating a write path. ``limit`` is optional; callers
        handling bridge sweeps should pass a row-count cap to avoid
        unbounded reads.
        """
        sql = (
            "SELECT source_key, drive_id, item_id, name, web_url, parent_path, "
            "size_bytes, is_folder, last_modified, etag, status, "
            "first_seen_at, last_seen_at "
            "FROM construction_drive_item_inventory WHERE source_key = ? "
            "ORDER BY item_id"
        )
        params: tuple[Any, ...] = (source_key,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (source_key, int(limit))
        conn = get_connection(self._db_path)
        keys = (
            "source_key",
            "drive_id",
            "item_id",
            "name",
            "web_url",
            "parent_path",
            "size_bytes",
            "is_folder",
            "last_modified",
            "etag",
            "status",
            "first_seen_at",
            "last_seen_at",
        )
        out: list[dict[str, Any]] = []
        for row in conn.execute(sql, params).fetchall():
            record = dict(zip(keys, row, strict=True))
            record["is_folder"] = bool(record["is_folder"])
            out.append(record)
        return out

    def count_inventory_by_kind(self, source_key: str) -> dict[str, int]:
        """Return ``{file_count, folder_count, total_size_bytes}`` for active rows.

        Used by the baseline-comparison primitive to compare live counts against
        the historic counts carried on the source registry's ``baseline`` block.
        Only ``status='active'`` rows are counted.
        """
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT
              SUM(CASE WHEN is_folder = 0 THEN 1 ELSE 0 END) AS file_count,
              SUM(CASE WHEN is_folder = 1 THEN 1 ELSE 0 END) AS folder_count,
              COALESCE(SUM(CASE WHEN is_folder = 0 THEN size_bytes ELSE 0 END), 0)
                AS total_size_bytes
            FROM construction_drive_item_inventory
            WHERE source_key = ? AND status = 'active'
            """,
            (source_key,),
        )
        row = cur.fetchone()
        if row is None:
            return {"file_count": 0, "folder_count": 0, "total_size_bytes": 0}
        return {
            "file_count": int(row[0] or 0),
            "folder_count": int(row[1] or 0),
            "total_size_bytes": int(row[2] or 0),
        }

    def list_inventory_for_source(
        self,
        source_key: str,
        *,
        include_deleted: bool = False,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        """List inventory rows for a source (active only by default)."""
        conn = get_connection(self._db_path)
        sql = """
            SELECT source_key, drive_id, item_id, name, web_url, parent_path,
                   size_bytes, is_folder, last_modified, etag, status,
                   first_seen_at, last_seen_at
            FROM construction_drive_item_inventory
            WHERE source_key = ?
        """
        params: tuple[Any, ...] = (source_key,)
        if not include_deleted:
            sql += " AND status = 'active'"
        sql += " ORDER BY item_id LIMIT ?"
        params = (*params, limit)
        cur = conn.execute(sql, params)
        keys = (
            "source_key",
            "drive_id",
            "item_id",
            "name",
            "web_url",
            "parent_path",
            "size_bytes",
            "is_folder",
            "last_modified",
            "etag",
            "status",
            "first_seen_at",
            "last_seen_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

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
        keys = (
            "source_key",
            "drive_id",
            "item_id",
            "name",
            "web_url",
            "parent_path",
            "size_bytes",
            "is_folder",
            "last_modified",
            "etag",
            "status",
            "first_seen_at",
            "last_seen_at",
        )
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
                    run_id,
                    source_key,
                    mode,
                    started_at,
                    finished_at,
                    pages_seen,
                    items_seen,
                    items_new,
                    items_updated,
                    items_deleted,
                    1 if delta_link_recorded else 0,
                    status,
                    error_redacted,
                ),
            )
            return int(cur.lastrowid)

    # --- review queue (V3) --------------------------------------------------

    def enqueue_review_item(self, match: Any) -> bool:
        """Insert a review-queue row from a :class:`RuleMatch`.

        Idempotent on ``(source_key, item_id, rule_id)``. Returns True if a new
        row was inserted, False if the unique constraint already had it.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO construction_review_queue
                    (source_key, project_key, item_id, name, parent_path,
                     rule_id, classification_label, sensitivity, reason,
                     suggested_action, confidence, status, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    match.source_key,
                    match.project_key,
                    match.item_id,
                    match.name,
                    match.parent_path,
                    match.rule_id,
                    match.classification_label,
                    match.sensitivity,
                    match.reason,
                    match.suggested_action,
                    match.confidence,
                    _utc_now(),
                ),
            )
            return cur.rowcount > 0

    def list_review_queue(
        self,
        *,
        source_key: str | None = None,
        status: str | None = "open",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List review-queue rows. ``status=None`` returns every status."""
        conn = get_connection(self._db_path)
        sql = """
            SELECT id, source_key, project_key, item_id, name, parent_path,
                   rule_id, classification_label, sensitivity, reason,
                   suggested_action, confidence, status, routed_at, resolved_at
            FROM construction_review_queue
            WHERE 1=1
        """
        params: list[Any] = []
        if source_key is not None:
            sql += " AND source_key = ?"
            params.append(source_key)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY routed_at DESC, id DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = (
            "id",
            "source_key",
            "project_key",
            "item_id",
            "name",
            "parent_path",
            "rule_id",
            "classification_label",
            "sensitivity",
            "reason",
            "suggested_action",
            "confidence",
            "status",
            "routed_at",
            "resolved_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def count_review_queue(
        self,
        *,
        source_key: str | None = None,
        status: str | None = "open",
    ) -> int:
        conn = get_connection(self._db_path)
        sql = "SELECT COUNT(*) FROM construction_review_queue WHERE 1=1"
        params: list[Any] = []
        if source_key is not None:
            sql += " AND source_key = ?"
            params.append(source_key)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        row = conn.execute(sql, tuple(params)).fetchone()
        return int(row[0]) if row else 0

    # --- model decisions (V4) -----------------------------------------------

    def record_model_decision(self, decision: Any) -> int:
        """Insert a :class:`ClassificationDecision` row. Returns lastrowid."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO construction_model_decisions
                    (source_key, item_id, project_key, model_name, model_task,
                     proposed_label, confidence, rationale_truncated,
                     raw_output_truncated, status, routing_reason, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.source_key,
                    decision.item_id,
                    decision.project_key,
                    decision.model_name,
                    decision.model_task,
                    decision.proposed_label,
                    decision.confidence,
                    decision.rationale_truncated,
                    decision.raw_output_truncated,
                    decision.status,
                    decision.routing_reason,
                    decision.routed_at,
                ),
            )
            return int(cur.lastrowid)

    def list_model_decisions(
        self,
        *,
        source_key: str | None = None,
        status: str | None = None,
        item_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List model-decisions rows. ``status=None`` returns every status."""
        conn = get_connection(self._db_path)
        sql = """
            SELECT id, source_key, item_id, project_key, model_name, model_task,
                   proposed_label, confidence, rationale_truncated,
                   raw_output_truncated, status, routing_reason, routed_at
            FROM construction_model_decisions
            WHERE 1=1
        """
        params: list[Any] = []
        if source_key is not None:
            sql += " AND source_key = ?"
            params.append(source_key)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        if item_id is not None:
            sql += " AND item_id = ?"
            params.append(item_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = (
            "id",
            "source_key",
            "item_id",
            "project_key",
            "model_name",
            "model_task",
            "proposed_label",
            "confidence",
            "rationale_truncated",
            "raw_output_truncated",
            "status",
            "routing_reason",
            "routed_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def count_model_decisions(
        self,
        *,
        source_key: str | None = None,
        status: str | None = None,
    ) -> int:
        conn = get_connection(self._db_path)
        sql = "SELECT COUNT(*) FROM construction_model_decisions WHERE 1=1"
        params: list[Any] = []
        if source_key is not None:
            sql += " AND source_key = ?"
            params.append(source_key)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        row = conn.execute(sql, tuple(params)).fetchone()
        return int(row[0]) if row else 0

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
        keys = (
            "id",
            "run_id",
            "mode",
            "started_at",
            "finished_at",
            "pages_seen",
            "items_seen",
            "items_new",
            "items_updated",
            "items_deleted",
            "delta_link_recorded",
            "status",
            "error_redacted",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # =====================================================================
    # V5: Phase 02 canonical alignment adapters.
    #
    # Surface the canonical construction-index concepts (source_locations,
    # sync_state, crawl_runs, drive_items, project_identity, project_source_
    # matches, document_cards, processing_receipts, sync_errors,
    # email_intelligence_deferred_state) without disturbing V2-V4 tables.
    # Defense-in-depth: adapter-level guardrails reject read_only=False and
    # mailbox-writeback/full-body opt-ins before SQL CHECKs ever fire.
    # =====================================================================

    @staticmethod
    def _dump_json(value: Optional[dict[str, Any] | list[Any]]) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True)

    @staticmethod
    def _load_json(value: Optional[str]) -> Optional[Any]:
        if value is None:
            return None
        return json.loads(value)

    # --- canonical source locations (V5) ------------------------------------

    def upsert_source_location(
        self,
        *,
        source_id: str,
        source_system: str,
        source_scope: str,
        source_name: str,
        project_key: Optional[str] = None,
        project_number: Optional[str] = None,
        project_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        site_url: Optional[str] = None,
        site_id: Optional[str] = None,
        drive_id: Optional[str] = None,
        folder_item_id: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_web_url: Optional[str] = None,
        library_name: Optional[str] = None,
        list_id: Optional[str] = None,
        local_sync_path: Optional[str] = None,
        sync_mode: Optional[str] = None,
        sync_frequency_minutes: Optional[int] = None,
        enabled: bool = True,
        read_only: bool = True,
        baseline_policy: Optional[dict[str, Any]] = None,
        folder_policies: Optional[dict[str, Any]] = None,
    ) -> None:
        if read_only is not True:
            raise ValueError(
                "construction_source_locations.read_only must be True "
                "(no writeback path in Phase 02)"
            )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_source_locations
                    (source_id, source_system, source_scope, source_name,
                     project_key, project_number, project_name, tenant_id,
                     site_url, site_id, drive_id, folder_item_id, folder_path,
                     folder_web_url, library_name, list_id, local_sync_path,
                     sync_mode, sync_frequency_minutes, enabled, read_only,
                     baseline_policy_json, folder_policies_json,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                        ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_system = excluded.source_system,
                    source_scope = excluded.source_scope,
                    source_name = excluded.source_name,
                    project_key = excluded.project_key,
                    project_number = excluded.project_number,
                    project_name = excluded.project_name,
                    tenant_id = excluded.tenant_id,
                    site_url = excluded.site_url,
                    site_id = excluded.site_id,
                    drive_id = excluded.drive_id,
                    folder_item_id = excluded.folder_item_id,
                    folder_path = excluded.folder_path,
                    folder_web_url = excluded.folder_web_url,
                    library_name = excluded.library_name,
                    list_id = excluded.list_id,
                    local_sync_path = excluded.local_sync_path,
                    sync_mode = excluded.sync_mode,
                    sync_frequency_minutes = excluded.sync_frequency_minutes,
                    enabled = excluded.enabled,
                    baseline_policy_json = excluded.baseline_policy_json,
                    folder_policies_json = excluded.folder_policies_json,
                    updated_utc = excluded.updated_utc
                """,
                (
                    source_id,
                    source_system,
                    source_scope,
                    source_name,
                    project_key,
                    project_number,
                    project_name,
                    tenant_id,
                    site_url,
                    site_id,
                    drive_id,
                    folder_item_id,
                    folder_path,
                    folder_web_url,
                    library_name,
                    list_id,
                    local_sync_path,
                    sync_mode,
                    sync_frequency_minutes,
                    1 if enabled else 0,
                    self._dump_json(baseline_policy),
                    self._dump_json(folder_policies),
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def upsert_calendar_source_location(
        self,
        *,
        source_id: str,
        mailbox_owner_hash: str,
        mailbox_owner_domain: Optional[str] = None,
        calendar_id_hash: Optional[str] = None,
        calendar_role: str = "primary",
        calendar_display_name_hash: Optional[str] = None,
        enabled: bool = True,
        read_only: bool = True,
        lookback_days: int = 14,
        lookahead_days: int = 30,
        max_items_per_run: int = 250,
        policy_id: Optional[str] = None,
    ) -> None:
        """Upsert a Phase 07B calendar source-registry entry (read-only only)."""
        if read_only is not True:
            raise ValueError(
                "calendar_source_locations.read_only must be True (no calendar writeback path)"
            )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_source_locations
                    (source_id, mailbox_owner_hash, mailbox_owner_domain, calendar_id_hash,
                     calendar_role, calendar_display_name_hash, enabled, read_only,
                     lookback_days, lookahead_days, max_items_per_run, policy_id,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    mailbox_owner_hash = excluded.mailbox_owner_hash,
                    mailbox_owner_domain = excluded.mailbox_owner_domain,
                    calendar_id_hash = excluded.calendar_id_hash,
                    calendar_role = excluded.calendar_role,
                    calendar_display_name_hash = excluded.calendar_display_name_hash,
                    enabled = excluded.enabled,
                    lookback_days = excluded.lookback_days,
                    lookahead_days = excluded.lookahead_days,
                    max_items_per_run = excluded.max_items_per_run,
                    policy_id = excluded.policy_id,
                    updated_utc = excluded.updated_utc
                """,
                (
                    source_id,
                    mailbox_owner_hash,
                    mailbox_owner_domain,
                    calendar_id_hash,
                    calendar_role,
                    calendar_display_name_hash,
                    1 if enabled else 0,
                    lookback_days,
                    lookahead_days,
                    max_items_per_run,
                    policy_id,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def upsert_calendar_sync_state(
        self,
        *,
        source_id: str,
        last_successful_sync_utc: Optional[str] = None,
        last_attempted_sync_utc: Optional[str] = None,
        window_start_utc: Optional[str] = None,
        window_end_utc: Optional[str] = None,
        last_event_count: int = 0,
        sync_status: str = "pending",
        error_redacted: Optional[str] = None,
    ) -> None:
        """Upsert bounded calendar sync state (redacted error text only)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_sync_state
                    (source_id, last_successful_sync_utc, last_attempted_sync_utc,
                     window_start_utc, window_end_utc, last_event_count, sync_status,
                     error_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    last_successful_sync_utc = excluded.last_successful_sync_utc,
                    last_attempted_sync_utc = excluded.last_attempted_sync_utc,
                    window_start_utc = excluded.window_start_utc,
                    window_end_utc = excluded.window_end_utc,
                    last_event_count = excluded.last_event_count,
                    sync_status = excluded.sync_status,
                    error_redacted = excluded.error_redacted
                """,
                (
                    source_id,
                    last_successful_sync_utc,
                    last_attempted_sync_utc,
                    window_start_utc,
                    window_end_utc,
                    last_event_count,
                    sync_status,
                    error_redacted,
                ),
            )

    def apply_calendar_index_batch(
        self,
        *,
        source_id: str,
        mailbox_owner_hash: str,
        mailbox_owner_domain: Optional[str] = None,
        calendar_role: str = "primary",
        policy_id: Optional[str] = None,
        lookback_days: int = 14,
        lookahead_days: int = 30,
        max_items_per_run: int = 250,
        run_id: str,
        mode: str,
        window_start_utc: str,
        window_end_utc: str,
        events_seen: int,
        events_private: int,
        events_cancelled: int,
        events_review_required: int,
        event_records: list[dict[str, Any]],
        last_attempted_sync_utc: str,
        failure_injector: Callable[[str, Optional[int], Optional[str]], None] | None = None,
        chunked: bool = False,
        is_final_chunk: bool = True,
        partial_ok: bool = False,
        failure_diagnostics: Optional[list[dict[str, Any]]] = None,
        last_event_ordinal: Optional[int] = None,
    ) -> int:
        """Apply a (chunk of) calendar index batch in one SQLite transaction.

        For larger-window reliability (post-148 / Prompt 15): when chunked=True + partial_ok=True,
        per-event errors are isolated (try per upsert, collect diag, continue; successful events
        in the chunk are committed). Chunked calls use INSERT OR IGNORE for crawl + partial
        UPDATEs to checkpointed (non-final) or completed (final chunk); sync_state updated on
        each chunk. On structural failure, still best-effort failed receipt in sep tx + raise.
        Caller (event_indexer) chunks the records (50-100), accumulates, surfaces per-ev diags
        in IndexResult. Idempotent upserts + bounded windows preserved; no body/desc/join ever.
        """

        def _diag(
            operation: str,
            exc: BaseException,
            *,
            event_ordinal: Optional[int] = None,
            event_index_id: Optional[str] = None,
        ) -> dict[str, Any]:
            return {
                "event_index_id": event_index_id,
                "event_ordinal": event_ordinal,
                "operation": operation,
                "exception_type": type(exc).__name__,
            }

        def _inject(
            operation: str,
            event_ordinal: Optional[int] = None,
            event_index_id: Optional[str] = None,
        ) -> None:
            if failure_injector is not None:
                failure_injector(operation, event_ordinal, event_index_id)

        def _persist_failed_receipt(diagnostic: dict[str, Any]) -> None:
            if diagnostic["operation"] == "source_location_upsert":
                return
            conn2 = get_connection(self._db_path)
            with transaction(conn2):
                now2 = _utc_now()
                conn2.execute(
                    """
                    INSERT INTO calendar_source_locations
                        (source_id, mailbox_owner_hash, mailbox_owner_domain, calendar_role,
                         enabled, read_only, lookback_days, lookahead_days, max_items_per_run,
                         policy_id, created_utc, updated_utc)
                    VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        mailbox_owner_hash = excluded.mailbox_owner_hash,
                        mailbox_owner_domain = excluded.mailbox_owner_domain,
                        calendar_role = excluded.calendar_role,
                        enabled = excluded.enabled,
                        lookback_days = excluded.lookback_days,
                        lookahead_days = excluded.lookahead_days,
                        max_items_per_run = excluded.max_items_per_run,
                        policy_id = excluded.policy_id,
                        updated_utc = excluded.updated_utc
                    """,
                    (
                        source_id,
                        mailbox_owner_hash,
                        mailbox_owner_domain,
                        calendar_role,
                        lookback_days,
                        lookahead_days,
                        max_items_per_run,
                        policy_id,
                        now2,
                        now2,
                    ),
                )
                conn2.execute(
                    """
                    INSERT OR REPLACE INTO calendar_crawl_runs
                        (run_id, source_id, mode, started_at_utc, completed_at_utc,
                         window_start_utc, window_end_utc, events_seen, events_indexed,
                         events_private, events_cancelled, events_review_required, status,
                         error_redacted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'failed', ?)
                    """,
                    (
                        run_id,
                        source_id,
                        mode,
                        now2,
                        now2,
                        window_start_utc,
                        window_end_utc,
                        events_seen,
                        events_private,
                        events_cancelled,
                        events_review_required,
                        f"{diagnostic['operation']}:{diagnostic['exception_type']}",
                    ),
                )
                conn2.execute(
                    """
                    INSERT INTO calendar_sync_state
                        (source_id, last_successful_sync_utc, last_attempted_sync_utc,
                         window_start_utc, window_end_utc, last_event_count, sync_status,
                         error_redacted)
                    VALUES (?, NULL, ?, ?, ?, ?, 'failed', ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        last_successful_sync_utc = NULL,
                        last_attempted_sync_utc = excluded.last_attempted_sync_utc,
                        window_start_utc = excluded.window_start_utc,
                        window_end_utc = excluded.window_end_utc,
                        last_event_count = excluded.last_event_count,
                        sync_status = excluded.sync_status,
                        error_redacted = excluded.error_redacted
                    """,
                    (
                        source_id,
                        last_attempted_sync_utc,
                        window_start_utc,
                        window_end_utc,
                        events_seen,
                        f"{diagnostic['operation']}:{diagnostic['exception_type']}",
                    ),
                )

        conn = get_connection(self._db_path)
        indexed = 0
        operation = "calendar_apply"
        event_ordinal: Optional[int] = None
        event_index_id: Optional[str] = None
        try:
            with transaction(conn):
                now = _utc_now()
                operation = "source_location_upsert"
                event_ordinal = None
                event_index_id = None
                _inject(operation)
                conn.execute(
                    """
                    INSERT INTO calendar_source_locations
                        (source_id, mailbox_owner_hash, mailbox_owner_domain, calendar_role,
                         enabled, read_only, lookback_days, lookahead_days, max_items_per_run,
                         policy_id, created_utc, updated_utc)
                    VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        mailbox_owner_hash = excluded.mailbox_owner_hash,
                        mailbox_owner_domain = excluded.mailbox_owner_domain,
                        calendar_role = excluded.calendar_role,
                        enabled = excluded.enabled,
                        lookback_days = excluded.lookback_days,
                        lookahead_days = excluded.lookahead_days,
                        max_items_per_run = excluded.max_items_per_run,
                        policy_id = excluded.policy_id,
                        updated_utc = excluded.updated_utc
                    """,
                    (
                        source_id,
                        mailbox_owner_hash,
                        mailbox_owner_domain,
                        calendar_role,
                        lookback_days,
                        lookahead_days,
                        max_items_per_run,
                        policy_id,
                        now,
                        now,
                    ),
                )

                operation = "crawl_run_insert"
                event_ordinal = None
                event_index_id = None
                _inject(operation)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO calendar_crawl_runs
                        (run_id, source_id, mode, started_at_utc, window_start_utc,
                         window_end_utc, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'running')
                    """,
                    (run_id, source_id, mode, now, window_start_utc, window_end_utc),
                )

                for rec in event_records:
                    fields = rec["fields"]
                    event_ordinal = rec["event_ordinal"]
                    event_index_id = fields["event_index_id"]
                    operation = "event_upsert"
                    _inject(operation, event_ordinal, event_index_id)
                    try:
                        conn.execute(
                            """
                            INSERT INTO calendar_event_index
                                (event_index_id, source_id, graph_event_id_hash, ical_uid_hash,
                                 series_master_id_hash, web_link_hash, subject_hash, subject_redacted,
                                 subject_token_hashes_json, organizer_hash, organizer_domain,
                                 location_hash, location_redacted, start_datetime_utc, end_datetime_utc,
                                 timezone, is_cancelled, is_private, is_online_meeting,
                                 online_meeting_provider, has_attachments, project_key,
                                 project_match_method, project_match_confidence, review_required,
                                 review_reasons_json, created_utc, updated_utc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                    ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(source_id, graph_event_id_hash) DO UPDATE SET
                                ical_uid_hash = excluded.ical_uid_hash,
                                series_master_id_hash = excluded.series_master_id_hash,
                                web_link_hash = excluded.web_link_hash,
                                subject_hash = excluded.subject_hash,
                                subject_redacted = excluded.subject_redacted,
                                subject_token_hashes_json = excluded.subject_token_hashes_json,
                                organizer_hash = excluded.organizer_hash,
                                organizer_domain = excluded.organizer_domain,
                                location_hash = excluded.location_hash,
                                location_redacted = excluded.location_redacted,
                                start_datetime_utc = excluded.start_datetime_utc,
                                end_datetime_utc = excluded.end_datetime_utc,
                                timezone = excluded.timezone,
                                is_cancelled = excluded.is_cancelled,
                                is_private = excluded.is_private,
                                is_online_meeting = excluded.is_online_meeting,
                                online_meeting_provider = excluded.online_meeting_provider,
                                has_attachments = excluded.has_attachments,
                                project_key = excluded.project_key,
                                project_match_method = excluded.project_match_method,
                                project_match_confidence = excluded.project_match_confidence,
                                review_required = excluded.review_required,
                                review_reasons_json = excluded.review_reasons_json,
                                updated_utc = excluded.updated_utc
                            """,
                            (
                                fields["event_index_id"],
                                fields["source_id"],
                                fields["graph_event_id_hash"],
                                fields.get("ical_uid_hash"),
                                fields.get("series_master_id_hash"),
                                fields.get("web_link_hash"),
                                fields.get("subject_hash"),
                                fields.get("subject_redacted"),
                                fields.get("subject_token_hashes_json"),
                                fields.get("organizer_hash"),
                                fields.get("organizer_domain"),
                                fields.get("location_hash"),
                                fields.get("location_redacted"),
                                fields["start_datetime_utc"],
                                fields["end_datetime_utc"],
                                fields.get("timezone"),
                                1 if fields.get("is_cancelled") else 0,
                                1 if fields.get("is_private") else 0,
                                1 if fields.get("is_online_meeting") else 0,
                                fields.get("online_meeting_provider"),
                                1 if fields.get("has_attachments") else 0,
                                fields.get("project_key"),
                                fields.get("project_match_method"),
                                fields.get("project_match_confidence"),
                                1 if fields.get("review_required") else 0,
                                fields.get("review_reasons_json"),
                                now,
                                now,
                            ),
                        )
                        for att in rec["attendees"]:
                            operation = "attendee_upsert"
                            _inject(operation, event_ordinal, event_index_id)
                            conn.execute(
                                """
                                INSERT INTO calendar_event_attendees
                                    (event_index_id, attendee_hash, attendee_domain, attendee_role,
                                     response_status, review_required)
                                VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT(event_index_id, attendee_hash) DO UPDATE SET
                                    attendee_domain = excluded.attendee_domain,
                                    attendee_role = excluded.attendee_role,
                                    response_status = excluded.response_status,
                                    review_required = excluded.review_required
                                """,
                                (
                                    event_index_id,
                                    att["attendee_hash"],
                                    att.get("attendee_domain"),
                                    att.get("attendee_role"),
                                    att.get("response_status"),
                                    1 if att.get("review_required") else 0,
                                ),
                            )
                        indexed += 1
                    except Exception as ev_exc:
                        if not partial_ok:
                            raise
                        d = _diag(
                            operation,
                            ev_exc,
                            event_ordinal=event_ordinal,
                            event_index_id=event_index_id,
                        )
                        if failure_diagnostics is not None:
                            failure_diagnostics.append(d)
                        # continue; chunk tx commits prior successes in this chunk
                        continue

                now_done = _utc_now()
                # For chunked runs: non-final chunks -> 'checkpointed' + accum events_indexed via COALESCE + delta;
                # final chunk (or non-chunked) -> 'completed'. Sync always updated (last_attempted) for progress.
                if not chunked or is_final_chunk:
                    status_val = "completed"
                    err_for_crawl: Optional[str] = None
                else:
                    status_val = "checkpointed"
                    err_for_crawl = None

                operation = (
                    "crawl_run_finalize"
                    if (not chunked or is_final_chunk)
                    else "crawl_run_checkpoint"
                )
                event_ordinal = None
                event_index_id = None
                _inject(operation)
                conn.execute(
                    """
                    UPDATE calendar_crawl_runs SET
                        status = ?, completed_at_utc = ?, events_seen = ?,
                        events_indexed = COALESCE(events_indexed, 0) + ?,
                        events_private = ?, events_cancelled = ?, events_review_required = ?,
                        error_redacted = ?
                    WHERE run_id = ?
                    """,
                    (
                        status_val,
                        now_done,
                        events_seen,
                        indexed,
                        events_private,
                        events_cancelled,
                        events_review_required,
                        err_for_crawl,
                        run_id,
                    ),
                )

                # Sync state updated on every chunk (or single) to reflect attempted progress even for partials.
                operation = "sync_state_update"
                event_ordinal = None
                event_index_id = None
                _inject(operation)
                conn.execute(
                    """
                    INSERT INTO calendar_sync_state
                        (source_id, last_successful_sync_utc, last_attempted_sync_utc,
                         window_start_utc, window_end_utc, last_event_count, sync_status,
                         error_redacted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                    ON CONFLICT(source_id) DO UPDATE SET
                        last_successful_sync_utc = excluded.last_successful_sync_utc,
                        last_attempted_sync_utc = excluded.last_attempted_sync_utc,
                        window_start_utc = excluded.window_start_utc,
                        window_end_utc = excluded.window_end_utc,
                        last_event_count = excluded.last_event_count,
                        sync_status = excluded.sync_status,
                        error_redacted = excluded.error_redacted
                    """,
                    (
                        source_id,
                        window_end_utc if (not chunked or is_final_chunk) else None,
                        last_attempted_sync_utc,
                        window_start_utc,
                        window_end_utc,
                        events_seen,
                        "completed" if (not chunked or is_final_chunk) else "checkpointed",
                    ),
                )
        except Exception as exc:
            diagnostic = _diag(
                operation,
                exc,
                event_ordinal=event_ordinal,
                event_index_id=event_index_id,
            )
            with contextlib.suppress(Exception):
                _persist_failed_receipt(diagnostic)
            raise CalendarBatchApplyError(diagnostic) from exc
        return indexed

    def insert_calendar_crawl_run(
        self,
        *,
        run_id: str,
        source_id: str,
        mode: str,
        started_at_utc: Optional[str] = None,
        window_start_utc: Optional[str] = None,
        window_end_utc: Optional[str] = None,
        status: str = "running",
    ) -> None:
        """Open a Phase 07B calendar crawl-run receipt (V23). The raw_body /
        full_text / external_writeback CHECK columns stay at their 0 default."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_crawl_runs
                    (run_id, source_id, mode, started_at_utc, window_start_utc,
                     window_end_utc, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    mode,
                    started_at_utc or _utc_now(),
                    window_start_utc,
                    window_end_utc,
                    status,
                ),
            )

    def complete_calendar_crawl_run(
        self,
        *,
        run_id: str,
        status: str,
        completed_at_utc: Optional[str] = None,
        events_seen: int = 0,
        events_indexed: int = 0,
        events_private: int = 0,
        events_cancelled: int = 0,
        events_review_required: int = 0,
        error_redacted: Optional[str] = None,
    ) -> bool:
        """Finalize a calendar crawl-run receipt with counters (redacted error only)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                UPDATE calendar_crawl_runs SET
                    status = ?, completed_at_utc = ?, events_seen = ?,
                    events_indexed = ?, events_private = ?, events_cancelled = ?,
                    events_review_required = ?, error_redacted = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    completed_at_utc or _utc_now(),
                    events_seen,
                    events_indexed,
                    events_private,
                    events_cancelled,
                    events_review_required,
                    error_redacted,
                    run_id,
                ),
            )
            return cur.rowcount > 0

    def upsert_calendar_event_index(
        self,
        *,
        event_index_id: str,
        source_id: str,
        graph_event_id_hash: str,
        start_datetime_utc: str,
        end_datetime_utc: str,
        ical_uid_hash: Optional[str] = None,
        series_master_id_hash: Optional[str] = None,
        web_link_hash: Optional[str] = None,
        subject_hash: Optional[str] = None,
        subject_redacted: Optional[str] = None,
        subject_token_hashes_json: Optional[str] = None,
        organizer_hash: Optional[str] = None,
        organizer_domain: Optional[str] = None,
        location_hash: Optional[str] = None,
        location_redacted: Optional[str] = None,
        timezone: Optional[str] = None,
        is_cancelled: bool = False,
        is_private: bool = False,
        is_online_meeting: bool = False,
        online_meeting_provider: Optional[str] = None,
        has_attachments: bool = False,
        project_key: Optional[str] = None,
        project_match_method: Optional[str] = None,
        project_match_confidence: Optional[float] = None,
        review_required: bool = False,
        review_reasons_json: Optional[str] = None,
    ) -> None:
        """Upsert a redacted calendar event index row (V23). Idempotent by
        (source_id, graph_event_id_hash). Stores hashes/redactions only; the
        raw_body / full_text / external_writeback CHECK columns remain 0."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_event_index
                    (event_index_id, source_id, graph_event_id_hash, ical_uid_hash,
                     series_master_id_hash, web_link_hash, subject_hash, subject_redacted,
                     subject_token_hashes_json, organizer_hash, organizer_domain,
                     location_hash, location_redacted, start_datetime_utc, end_datetime_utc,
                     timezone, is_cancelled, is_private, is_online_meeting,
                     online_meeting_provider, has_attachments, project_key,
                     project_match_method, project_match_confidence, review_required,
                     review_reasons_json, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, graph_event_id_hash) DO UPDATE SET
                    ical_uid_hash = excluded.ical_uid_hash,
                    series_master_id_hash = excluded.series_master_id_hash,
                    web_link_hash = excluded.web_link_hash,
                    subject_hash = excluded.subject_hash,
                    subject_redacted = excluded.subject_redacted,
                    subject_token_hashes_json = excluded.subject_token_hashes_json,
                    organizer_hash = excluded.organizer_hash,
                    organizer_domain = excluded.organizer_domain,
                    location_hash = excluded.location_hash,
                    location_redacted = excluded.location_redacted,
                    start_datetime_utc = excluded.start_datetime_utc,
                    end_datetime_utc = excluded.end_datetime_utc,
                    timezone = excluded.timezone,
                    is_cancelled = excluded.is_cancelled,
                    is_private = excluded.is_private,
                    is_online_meeting = excluded.is_online_meeting,
                    online_meeting_provider = excluded.online_meeting_provider,
                    has_attachments = excluded.has_attachments,
                    project_key = excluded.project_key,
                    project_match_method = excluded.project_match_method,
                    project_match_confidence = excluded.project_match_confidence,
                    review_required = excluded.review_required,
                    review_reasons_json = excluded.review_reasons_json,
                    updated_utc = excluded.updated_utc
                """,
                (
                    event_index_id,
                    source_id,
                    graph_event_id_hash,
                    ical_uid_hash,
                    series_master_id_hash,
                    web_link_hash,
                    subject_hash,
                    subject_redacted,
                    subject_token_hashes_json,
                    organizer_hash,
                    organizer_domain,
                    location_hash,
                    location_redacted,
                    start_datetime_utc,
                    end_datetime_utc,
                    timezone,
                    1 if is_cancelled else 0,
                    1 if is_private else 0,
                    1 if is_online_meeting else 0,
                    online_meeting_provider,
                    1 if has_attachments else 0,
                    project_key,
                    project_match_method,
                    project_match_confidence,
                    1 if review_required else 0,
                    review_reasons_json,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def upsert_calendar_event_attendee(
        self,
        *,
        event_index_id: str,
        attendee_hash: str,
        attendee_domain: Optional[str] = None,
        attendee_role: Optional[str] = None,
        response_status: Optional[str] = None,
        review_required: bool = False,
    ) -> None:
        """Upsert an attendee row (hash/domain only). Idempotent by
        (event_index_id, attendee_hash). No raw addresses stored."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_event_attendees
                    (event_index_id, attendee_hash, attendee_domain, attendee_role,
                     response_status, review_required)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_index_id, attendee_hash) DO UPDATE SET
                    attendee_domain = excluded.attendee_domain,
                    attendee_role = excluded.attendee_role,
                    response_status = excluded.response_status,
                    review_required = excluded.review_required
                """,
                (
                    event_index_id,
                    attendee_hash,
                    attendee_domain,
                    attendee_role,
                    response_status,
                    1 if review_required else 0,
                ),
            )

    def list_calendar_event_index(
        self, *, source_id: Optional[str] = None, limit: int = 100000
    ) -> list[dict[str, Any]]:
        """Read redacted calendar event index rows for Phase 07B project matching.
        Returns hashed/redacted metadata only (no raw values were ever stored)."""
        conn = get_connection(self._db_path)
        sql = (
            "SELECT event_index_id, source_id, subject_token_hashes_json, organizer_domain,"
            " start_datetime_utc, end_datetime_utc,"
            " is_private, is_cancelled, project_key, project_match_method,"
            " project_match_confidence, review_required, review_reasons_json"
            " FROM calendar_event_index"
        )
        params: tuple[Any, ...] = ()
        if source_id is not None:
            sql += " WHERE source_id = ?"
            params = (source_id,)
        sql += " ORDER BY start_datetime_utc LIMIT ?"
        params = (*params, limit)
        keys = (
            "event_index_id",
            "source_id",
            "subject_token_hashes_json",
            "organizer_domain",
            "start_datetime_utc",
            "end_datetime_utc",
            "is_private",
            "is_cancelled",
            "project_key",
            "project_match_method",
            "project_match_confidence",
            "review_required",
            "review_reasons_json",
        )
        rows: list[dict[str, Any]] = []
        for row in conn.execute(sql, params):
            rec = dict(zip(keys, row, strict=True))
            rec["subject_token_hashes"] = (
                self._load_json(rec.pop("subject_token_hashes_json")) or []
            )
            rec["review_reasons"] = self._load_json(rec.pop("review_reasons_json")) or []
            rec["is_private"] = bool(rec["is_private"])
            rec["is_cancelled"] = bool(rec["is_cancelled"])
            rec["review_required"] = bool(rec["review_required"])
            rows.append(rec)
        return rows

    def list_calendar_prep_source_events(
        self,
        *,
        project_key: Optional[str] = None,
        include_cancelled: bool = False,
        include_private: bool = False,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        """Read safe, redacted calendar-event metadata for Phase 10 meeting-prep.

        Returns only already-redacted/hashed fields from ``calendar_event_index`` plus aggregate
        attendee facts (count + DISTINCT domains) from ``calendar_event_attendees`` — never subjects,
        bodies, join URLs, attendee names, or emails. Cancelled/private events are excluded by
        default. Ordered by start time; time-window selection is done by the caller (deterministic,
        no clock read here)."""
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if not include_cancelled:
            clauses.append("i.is_cancelled = 0")
        if not include_private:
            clauses.append("i.is_private = 0")
        if project_key is not None:
            clauses.append("i.project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        sql = f"""
            SELECT i.event_index_id, i.subject_redacted, i.location_redacted, i.organizer_domain,
                   i.start_datetime_utc, i.end_datetime_utc, i.is_online_meeting,
                   i.online_meeting_provider, i.project_key,
                   COUNT(a.id) AS attendee_count,
                   group_concat(DISTINCT a.attendee_domain) AS participant_domains_csv
            FROM calendar_event_index i
            LEFT JOIN calendar_event_attendees a ON a.event_index_id = i.event_index_id
            {where}
            GROUP BY i.event_index_id
            ORDER BY i.start_datetime_utc, i.event_index_id
            LIMIT ?
        """
        keys = (
            "event_index_id",
            "subject_redacted",
            "location_redacted",
            "organizer_domain",
            "start_datetime_utc",
            "end_datetime_utc",
            "is_online_meeting",
            "online_meeting_provider",
            "project_key",
            "attendee_count",
            "participant_domains_csv",
        )
        rows: list[dict[str, Any]] = []
        for row in conn.execute(sql, tuple(params)):
            rec = dict(zip(keys, row, strict=True))
            csv = rec.pop("participant_domains_csv") or ""
            rec["participant_domains"] = sorted({d for d in csv.split(",") if d})[:20]
            rec["is_online_meeting"] = bool(rec["is_online_meeting"])
            rec["attendee_count"] = int(rec["attendee_count"] or 0)
            rows.append(rec)
        return rows

    def upsert_calendar_project_match_candidate(
        self,
        *,
        candidate_id: str,
        event_index_id: str,
        project_key: str,
        candidate_type: str,
        signals_json: str,
        confidence: float,
        confidence_class: str,
        deterministic: bool = False,
        model_proposed: bool = False,
        review_required: bool = True,
        promotion_status: str = "candidate",
    ) -> None:
        """Upsert a calendar event→project match candidate (V23). Candidates only —
        ``promotion_status`` defaults to 'candidate' (no auto-promotion). Idempotent
        by candidate_id. signals_json must carry safe values only (hashes/counts);
        the raw_body / external_writeback CHECK columns remain 0."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO calendar_project_match_candidates
                    (candidate_id, event_index_id, project_key, candidate_type,
                     signals_json, confidence, confidence_class, deterministic,
                     model_proposed, review_required, promotion_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    event_index_id = excluded.event_index_id,
                    project_key = excluded.project_key,
                    candidate_type = excluded.candidate_type,
                    signals_json = excluded.signals_json,
                    confidence = excluded.confidence,
                    confidence_class = excluded.confidence_class,
                    deterministic = excluded.deterministic,
                    model_proposed = excluded.model_proposed,
                    review_required = excluded.review_required,
                    promotion_status = excluded.promotion_status
                """,
                (
                    candidate_id,
                    event_index_id,
                    project_key,
                    candidate_type,
                    signals_json,
                    confidence,
                    confidence_class,
                    1 if deterministic else 0,
                    1 if model_proposed else 0,
                    1 if review_required else 0,
                    promotion_status,
                    _utc_now(),
                ),
            )

    def upsert_meeting_email_relationship_candidate(
        self,
        *,
        candidate_id: str,
        event_index_id: str,
        thread_key_hash: str,
        candidate_type: str,
        source_reference_json: str,
        confidence: float,
        confidence_class: str,
        project_key: Optional[str] = None,
        time_window_signal: Optional[str] = None,
        participant_signal: Optional[str] = None,
        subject_topic_signal: Optional[str] = None,
        deterministic: bool = False,
        model_proposed: bool = False,
        review_required: bool = True,
        promotion_status: str = "candidate",
    ) -> None:
        """Upsert a calendar event → email thread relationship candidate (V23).
        Candidates only — ``promotion_status`` defaults to 'candidate' (no
        auto-promotion); the calendar/thread rows are never written. Idempotent by
        candidate_id. The signal / source_reference JSON must carry safe values only
        (hashes/bools/datetimes/counts); the raw_body / raw_prompt / raw_response /
        external_writeback CHECK columns remain 0."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO meeting_email_relationship_candidates
                    (candidate_id, event_index_id, thread_key_hash, project_key,
                     candidate_type, time_window_signal, participant_signal,
                     subject_topic_signal, source_reference_json, confidence,
                     confidence_class, deterministic, model_proposed, review_required,
                     promotion_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    event_index_id = excluded.event_index_id,
                    thread_key_hash = excluded.thread_key_hash,
                    project_key = excluded.project_key,
                    candidate_type = excluded.candidate_type,
                    time_window_signal = excluded.time_window_signal,
                    participant_signal = excluded.participant_signal,
                    subject_topic_signal = excluded.subject_topic_signal,
                    source_reference_json = excluded.source_reference_json,
                    confidence = excluded.confidence,
                    confidence_class = excluded.confidence_class,
                    deterministic = excluded.deterministic,
                    model_proposed = excluded.model_proposed,
                    review_required = excluded.review_required,
                    promotion_status = excluded.promotion_status
                """,
                (
                    candidate_id,
                    event_index_id,
                    thread_key_hash,
                    project_key,
                    candidate_type,
                    time_window_signal,
                    participant_signal,
                    subject_topic_signal,
                    source_reference_json,
                    confidence,
                    confidence_class,
                    1 if deterministic else 0,
                    1 if model_proposed else 0,
                    1 if review_required else 0,
                    promotion_status,
                    _utc_now(),
                ),
            )

    _MEETING_EMAIL_CANDIDATE_KEYS: tuple[str, ...] = (
        "candidate_id",
        "event_index_id",
        "thread_key_hash",
        "project_key",
        "candidate_type",
        "time_window_signal",
        "participant_signal",
        "subject_topic_signal",
        "source_reference_json",
        "confidence",
        "confidence_class",
        "deterministic",
        "model_proposed",
        "review_required",
        "promotion_status",
        "created_utc",
    )

    def list_meeting_email_relationship_candidates(
        self,
        *,
        project_key: Optional[str] = None,
        event_index_id: Optional[str] = None,
        review_required: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List calendar event → email thread relationship candidates (V23) with
        optional filters. Signal / source_reference JSON columns are decoded; the
        boolean flags are returned as booleans."""
        keys = self._MEETING_EMAIL_CANDIDATE_KEYS
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if event_index_id is not None:
            clauses.append("event_index_id = ?")
            params.append(event_index_id)
        if review_required is not None:
            clauses.append("review_required = ?")
            params.append(1 if review_required else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM meeting_email_relationship_candidates "
            f"{where} ORDER BY confidence DESC, candidate_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for json_field in (
                "time_window_signal",
                "participant_signal",
                "subject_topic_signal",
                "source_reference_json",
            ):
                record[json_field] = self._load_json(record[json_field])
            for bool_field in ("deterministic", "model_proposed", "review_required"):
                record[bool_field] = bool(record[bool_field])
            results.append(record)
        return results

    def get_source_location(self, source_id: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_id, source_system, source_scope, source_name,
                   project_key, project_number, project_name, tenant_id,
                   site_url, site_id, drive_id, folder_item_id, folder_path,
                   folder_web_url, library_name, list_id, local_sync_path,
                   sync_mode, sync_frequency_minutes, enabled, read_only,
                   baseline_policy_json, folder_policies_json,
                   created_utc, updated_utc
            FROM construction_source_locations
            WHERE source_id = ?
            """,
            (source_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "source_id",
            "source_system",
            "source_scope",
            "source_name",
            "project_key",
            "project_number",
            "project_name",
            "tenant_id",
            "site_url",
            "site_id",
            "drive_id",
            "folder_item_id",
            "folder_path",
            "folder_web_url",
            "library_name",
            "list_id",
            "local_sync_path",
            "sync_mode",
            "sync_frequency_minutes",
            "enabled",
            "read_only",
            "baseline_policy_json",
            "folder_policies_json",
            "created_utc",
            "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        record["baseline_policy"] = self._load_json(record.pop("baseline_policy_json"))
        record["folder_policies"] = self._load_json(record.pop("folder_policies_json"))
        record["enabled"] = bool(record["enabled"])
        record["read_only"] = bool(record["read_only"])
        return record

    def list_source_locations(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = "SELECT source_id FROM construction_source_locations WHERE 1=1"
        params: list[Any] = []
        if project_key is not None:
            sql += " AND project_key = ?"
            params.append(project_key)
        sql += " ORDER BY source_id LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        ids = [row[0] for row in cur.fetchall()]
        return [self.get_source_location(s) for s in ids if self.get_source_location(s)]

    # --- canonical sync state (V5) ------------------------------------------

    def upsert_source_sync_state(
        self,
        *,
        source_id: str,
        drive_id: Optional[str] = None,
        folder_item_id: Optional[str] = None,
        delta_link: Optional[str] = None,
        delta_link_fingerprint: Optional[str] = None,
        last_successful_sync_utc: Optional[str] = None,
        last_attempted_sync_utc: Optional[str] = None,
        last_baseline_item_count: Optional[int] = None,
        last_change_count: Optional[int] = None,
        sync_status: str = "pending",
        error_message_redacted: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_source_sync_state
                    (source_id, drive_id, folder_item_id, delta_link,
                     delta_link_fingerprint, last_successful_sync_utc,
                     last_attempted_sync_utc, last_baseline_item_count,
                     last_change_count, sync_status, error_message_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    drive_id = excluded.drive_id,
                    folder_item_id = excluded.folder_item_id,
                    delta_link = excluded.delta_link,
                    delta_link_fingerprint = excluded.delta_link_fingerprint,
                    last_successful_sync_utc = excluded.last_successful_sync_utc,
                    last_attempted_sync_utc = excluded.last_attempted_sync_utc,
                    last_baseline_item_count = excluded.last_baseline_item_count,
                    last_change_count = excluded.last_change_count,
                    sync_status = excluded.sync_status,
                    error_message_redacted = excluded.error_message_redacted
                """,
                (
                    source_id,
                    drive_id,
                    folder_item_id,
                    delta_link,
                    delta_link_fingerprint,
                    last_successful_sync_utc,
                    last_attempted_sync_utc,
                    last_baseline_item_count,
                    last_change_count,
                    sync_status,
                    error_message_redacted,
                ),
            )

    def get_source_sync_state(self, source_id: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_id, drive_id, folder_item_id, delta_link,
                   delta_link_fingerprint, last_successful_sync_utc,
                   last_attempted_sync_utc, last_baseline_item_count,
                   last_change_count, sync_status, error_message_redacted
            FROM construction_source_sync_state
            WHERE source_id = ?
            """,
            (source_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "source_id",
            "drive_id",
            "folder_item_id",
            "delta_link",
            "delta_link_fingerprint",
            "last_successful_sync_utc",
            "last_attempted_sync_utc",
            "last_baseline_item_count",
            "last_change_count",
            "sync_status",
            "error_message_redacted",
        )
        return dict(zip(keys, row, strict=True))

    # --- canonical crawl runs (V5) ------------------------------------------

    def insert_source_crawl_run(
        self,
        *,
        run_id: str,
        source_id: str,
        source_scope: str,
        mode: str,
        started_at: str,
        completed_at: Optional[str] = None,
        pages_seen: int = 0,
        items_seen: int = 0,
        items_in_scope: int = 0,
        items_out_of_scope_filtered: int = 0,
        delta_link_recorded: bool = False,
        status: str,
        error_redacted: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_source_crawl_runs
                    (run_id, source_id, source_scope, mode, started_at,
                     completed_at, pages_seen, items_seen, items_in_scope,
                     items_out_of_scope_filtered, delta_link_recorded, status,
                     error_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    source_scope,
                    mode,
                    started_at,
                    completed_at,
                    pages_seen,
                    items_seen,
                    items_in_scope,
                    items_out_of_scope_filtered,
                    1 if delta_link_recorded else 0,
                    status,
                    error_redacted,
                ),
            )

    def list_source_crawl_runs(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = """
            SELECT run_id, source_id, source_scope, mode, started_at,
                   completed_at, pages_seen, items_seen, items_in_scope,
                   items_out_of_scope_filtered, delta_link_recorded, status,
                   error_redacted
            FROM construction_source_crawl_runs
            WHERE 1=1
        """
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = (
            "run_id",
            "source_id",
            "source_scope",
            "mode",
            "started_at",
            "completed_at",
            "pages_seen",
            "items_seen",
            "items_in_scope",
            "items_out_of_scope_filtered",
            "delta_link_recorded",
            "status",
            "error_redacted",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]
        for r in rows:
            r["delta_link_recorded"] = bool(r["delta_link_recorded"])
        return rows

    # --- canonical drive items (V5) -----------------------------------------

    def upsert_drive_item(
        self,
        *,
        source_id: str,
        drive_id: str,
        drive_item_id: str,
        parent_drive_item_id: Optional[str] = None,
        site_id: Optional[str] = None,
        list_id: Optional[str] = None,
        list_item_id: Optional[str] = None,
        name: Optional[str] = None,
        path: Optional[str] = None,
        web_url: Optional[str] = None,
        is_folder: bool = False,
        is_file: bool = False,
        file_extension: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        last_modified_datetime: Optional[str] = None,
        deleted: bool = False,
        quick_xor_hash: Optional[str] = None,
        project_key: Optional[str] = None,
        project_number_detected: Optional[str] = None,
        document_type_detected: Optional[str] = None,
        indexing_policy: Optional[str] = None,
        classification_status: Optional[str] = None,
        # v15 Phase 06 (Files) rich driveItem metadata.
        is_package: bool = False,
        e_tag: Optional[str] = None,
        c_tag: Optional[str] = None,
        created_datetime: Optional[str] = None,
        parent_reference_path: Optional[str] = None,
        folder_child_count: Optional[int] = None,
        sharepoint_web_id: Optional[str] = None,
        sharepoint_list_item_id: Optional[str] = None,
        file_hashes_json: Optional[str] = None,
        package_json_redacted: Optional[str] = None,
        remote_item_json_redacted: Optional[str] = None,
        # v44 Phase 10 Graph driveItem modified-by metadata.
        parent_folder_name: Optional[str] = None,
        last_modified_by_display_name: Optional[str] = None,
        last_modified_by_user_id: Optional[str] = None,
        last_modified_by_email: Optional[str] = None,
        last_modified_by_application_display_name: Optional[str] = None,
        last_modified_by_raw_json: Optional[str] = None,
    ) -> None:
        now = _utc_now()
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_drive_items
                    (source_id, drive_id, drive_item_id, parent_drive_item_id,
                     site_id, list_id, list_item_id, name, path, web_url,
                     is_folder, is_file, file_extension, mime_type, size_bytes,
                     last_modified_datetime, deleted, quick_xor_hash,
                     project_number_detected, document_type_detected,
                     indexing_policy, classification_status,
                     created_utc, updated_utc,
                     is_package, e_tag, c_tag, created_datetime,
                     parent_reference_path, folder_child_count,
                     sharepoint_web_id, sharepoint_list_item_id,
                     file_hashes_json, package_json_redacted,
                     remote_item_json_redacted, first_seen_utc, last_seen_utc,
                     project_key, parent_folder_name,
                     last_modified_by_display_name, last_modified_by_user_id,
                     last_modified_by_email, last_modified_by_application_display_name,
                     last_modified_by_raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?)
                ON CONFLICT(source_id, drive_item_id) DO UPDATE SET
                    drive_id = excluded.drive_id,
                    parent_drive_item_id = excluded.parent_drive_item_id,
                    site_id = excluded.site_id,
                    list_id = excluded.list_id,
                    list_item_id = excluded.list_item_id,
                    name = excluded.name,
                    path = excluded.path,
                    web_url = excluded.web_url,
                    is_folder = excluded.is_folder,
                    is_file = excluded.is_file,
                    file_extension = excluded.file_extension,
                    mime_type = excluded.mime_type,
                    size_bytes = excluded.size_bytes,
                    last_modified_datetime = excluded.last_modified_datetime,
                    deleted = excluded.deleted,
                    quick_xor_hash = excluded.quick_xor_hash,
                    project_number_detected = excluded.project_number_detected,
                    document_type_detected = excluded.document_type_detected,
                    indexing_policy = excluded.indexing_policy,
                    classification_status = excluded.classification_status,
                    updated_utc = excluded.updated_utc,
                    is_package = excluded.is_package,
                    e_tag = excluded.e_tag,
                    c_tag = excluded.c_tag,
                    created_datetime = excluded.created_datetime,
                    parent_reference_path = excluded.parent_reference_path,
                    folder_child_count = excluded.folder_child_count,
                    sharepoint_web_id = excluded.sharepoint_web_id,
                    sharepoint_list_item_id = excluded.sharepoint_list_item_id,
                    file_hashes_json = excluded.file_hashes_json,
                    package_json_redacted = excluded.package_json_redacted,
                    remote_item_json_redacted = excluded.remote_item_json_redacted,
                    last_seen_utc = excluded.last_seen_utc,
                    project_key = COALESCE(construction_drive_items.project_key, excluded.project_key),
                    parent_folder_name = excluded.parent_folder_name,
                    last_modified_by_display_name = excluded.last_modified_by_display_name,
                    last_modified_by_user_id = excluded.last_modified_by_user_id,
                    last_modified_by_email = excluded.last_modified_by_email,
                    last_modified_by_application_display_name = excluded.last_modified_by_application_display_name,
                    last_modified_by_raw_json = excluded.last_modified_by_raw_json
                """,
                (
                    source_id,
                    drive_id,
                    drive_item_id,
                    parent_drive_item_id,
                    site_id,
                    list_id,
                    list_item_id,
                    name,
                    path,
                    web_url,
                    1 if is_folder else 0,
                    1 if is_file else 0,
                    file_extension,
                    mime_type,
                    size_bytes,
                    last_modified_datetime,
                    1 if deleted else 0,
                    quick_xor_hash,
                    project_number_detected,
                    document_type_detected,
                    indexing_policy,
                    classification_status,
                    now,
                    now,
                    1 if is_package else 0,
                    e_tag,
                    c_tag,
                    created_datetime,
                    parent_reference_path,
                    folder_child_count,
                    sharepoint_web_id,
                    sharepoint_list_item_id,
                    file_hashes_json,
                    package_json_redacted,
                    remote_item_json_redacted,
                    now,
                    now,
                    project_key,
                    parent_folder_name,
                    last_modified_by_display_name,
                    last_modified_by_user_id,
                    last_modified_by_email,
                    last_modified_by_application_display_name,
                    last_modified_by_raw_json,
                ),
            )

    def get_drive_item(
        self,
        *,
        source_id: str,
        drive_item_id: str,
    ) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT source_id, drive_id, drive_item_id, parent_drive_item_id,
                   site_id, list_id, list_item_id, name, path, web_url,
                   is_folder, is_file, file_extension, mime_type, size_bytes,
                   last_modified_datetime, deleted, quick_xor_hash,
                   project_number_detected, document_type_detected,
                   indexing_policy, classification_status,
                   created_utc, updated_utc,
                   is_package, e_tag, c_tag, created_datetime,
                   parent_reference_path, folder_child_count,
                   sharepoint_web_id, sharepoint_list_item_id,
                   file_hashes_json, package_json_redacted,
                   remote_item_json_redacted, first_seen_utc, last_seen_utc,
                   project_key, match_confidence, match_status, review_required,
                   review_reason, match_signals_json,
                   parent_folder_name,
                   last_modified_by_display_name, last_modified_by_user_id,
                   last_modified_by_email, last_modified_by_application_display_name,
                   last_modified_by_raw_json
            FROM construction_drive_items
            WHERE source_id = ? AND drive_item_id = ?
            """,
            (source_id, drive_item_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        record = dict(zip(_DRIVE_ITEM_KEYS, row, strict=True))
        for bool_field in ("is_folder", "is_file", "deleted", "is_package", "review_required"):
            record[bool_field] = bool(record[bool_field])
        return record

    def list_drive_items(
        self,
        *,
        source_id: str,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Iterate canonical V5 ``construction_drive_items`` rows for a source.

        Used by the V2↔V5 drive-item bridge to enumerate V5 rows without
        creating a write path. ``limit`` is optional; callers handling
        bridge sweeps should pass a row-count cap to avoid unbounded reads.
        """
        sql = (
            "SELECT source_id, drive_id, drive_item_id, parent_drive_item_id, "
            "site_id, list_id, list_item_id, name, path, web_url, "
            "is_folder, is_file, file_extension, mime_type, size_bytes, "
            "last_modified_datetime, deleted, quick_xor_hash, "
            "project_number_detected, document_type_detected, "
            "indexing_policy, classification_status, "
            "created_utc, updated_utc, "
            "is_package, e_tag, c_tag, created_datetime, "
            "parent_reference_path, folder_child_count, "
            "sharepoint_web_id, sharepoint_list_item_id, "
            "file_hashes_json, package_json_redacted, "
            "remote_item_json_redacted, first_seen_utc, last_seen_utc, "
            "project_key, match_confidence, match_status, review_required, "
            "review_reason, match_signals_json, "
            "parent_folder_name, "
            "last_modified_by_display_name, last_modified_by_user_id, "
            "last_modified_by_email, last_modified_by_application_display_name, "
            "last_modified_by_raw_json "
            "FROM construction_drive_items WHERE source_id = ? "
            "ORDER BY drive_item_id"
        )
        params: tuple[Any, ...] = (source_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (source_id, int(limit))
        conn = get_connection(self._db_path)
        out: list[dict[str, Any]] = []
        for row in conn.execute(sql, params).fetchall():
            record = dict(zip(_DRIVE_ITEM_KEYS, row, strict=True))
            for bool_field in ("is_folder", "is_file", "deleted", "is_package", "review_required"):
                record[bool_field] = bool(record[bool_field])
            out.append(record)
        return out

    # --- per-file project matching (V17) ------------------------------------

    def update_drive_item_project_match(
        self,
        *,
        source_id: str,
        drive_item_id: str,
        project_key: Optional[str] = None,
        project_number_detected: Optional[str] = None,
        match_confidence: Optional[str] = None,
        match_status: Optional[str] = None,
        review_required: bool = False,
        review_reason: Optional[str] = None,
        match_signals_json: Optional[str] = None,
    ) -> None:
        """Update the V17 project-match fields of an existing drive_item row."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                UPDATE construction_drive_items
                   SET project_key = ?,
                       project_number_detected = ?,
                       match_confidence = ?,
                       match_status = ?,
                       review_required = ?,
                       review_reason = ?,
                       match_signals_json = ?,
                       updated_utc = ?
                 WHERE source_id = ? AND drive_item_id = ?
                """,
                (
                    project_key,
                    project_number_detected,
                    match_confidence,
                    match_status,
                    1 if review_required else 0,
                    review_reason,
                    match_signals_json,
                    _utc_now(),
                    source_id,
                    drive_item_id,
                ),
            )

    def list_drive_item_project_matches(
        self,
        *,
        project_key: Optional[str] = None,
        source_id: Optional[str] = None,
        review_required: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Report-only view of the V17 project-match fields per drive item."""
        conn = get_connection(self._db_path)
        sql = (
            "SELECT source_id, drive_item_id, name, path, project_key, "
            "project_number_detected, match_confidence, match_status, "
            "review_required, review_reason, match_signals_json "
            "FROM construction_drive_items WHERE 1=1"
        )
        params: list[Any] = []
        if project_key is not None:
            sql += " AND project_key = ?"
            params.append(project_key)
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        if review_required is not None:
            sql += " AND review_required = ?"
            params.append(1 if review_required else 0)
        sql += " ORDER BY drive_item_id LIMIT ?"
        params.append(int(limit))
        keys = (
            "source_id",
            "drive_item_id",
            "name",
            "path",
            "project_key",
            "project_number_detected",
            "match_confidence",
            "match_status",
            "review_required",
            "review_reason",
            "match_signals_json",
        )
        rows = [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]
        for r in rows:
            r["review_required"] = bool(r["review_required"])
        return rows

    # --- file ingestion decisions (V18) -------------------------------------

    def insert_file_ingestion_decision(
        self,
        *,
        decision_id: str,
        source_id: str,
        drive_item_id: str,
        drive_id: Optional[str] = None,
        project_key: Optional[str] = None,
        project_number_detected: Optional[str] = None,
        document_type_detected: Optional[str] = None,
        ingestion_disposition: str,
        review_required: bool = False,
        review_reason: Optional[str] = None,
        extraction_allowed: bool = False,
        download_allowed: bool = False,
        reason_codes_json: Optional[str] = None,
    ) -> None:
        """Upsert one ingestion-eligibility decision. The schema CHECK rejects any
        review-required row that also allows extraction."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_file_ingestion_decisions
                    (decision_id, source_id, drive_id, drive_item_id, project_key,
                     project_number_detected, document_type_detected,
                     ingestion_disposition, review_required, review_reason,
                     extraction_allowed, download_allowed, reason_codes_json, decided_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, drive_item_id) DO UPDATE SET
                    drive_id = excluded.drive_id,
                    project_key = excluded.project_key,
                    project_number_detected = excluded.project_number_detected,
                    document_type_detected = excluded.document_type_detected,
                    ingestion_disposition = excluded.ingestion_disposition,
                    review_required = excluded.review_required,
                    review_reason = excluded.review_reason,
                    extraction_allowed = excluded.extraction_allowed,
                    download_allowed = excluded.download_allowed,
                    reason_codes_json = excluded.reason_codes_json,
                    decided_utc = excluded.decided_utc
                """,
                (
                    decision_id,
                    source_id,
                    drive_id,
                    drive_item_id,
                    project_key,
                    project_number_detected,
                    document_type_detected,
                    ingestion_disposition,
                    1 if review_required else 0,
                    review_reason,
                    1 if extraction_allowed else 0,
                    1 if download_allowed else 0,
                    reason_codes_json,
                    _utc_now(),
                ),
            )

    def list_file_ingestion_decisions(
        self,
        *,
        source_id: Optional[str] = None,
        project_key: Optional[str] = None,
        review_required: Optional[bool] = None,
        disposition: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = (
            "SELECT decision_id, source_id, drive_id, drive_item_id, project_key, "
            "project_number_detected, document_type_detected, ingestion_disposition, "
            "review_required, review_reason, extraction_allowed, download_allowed, "
            "reason_codes_json, decided_utc "
            "FROM construction_file_ingestion_decisions WHERE 1=1"
        )
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        if project_key is not None:
            sql += " AND project_key = ?"
            params.append(project_key)
        if review_required is not None:
            sql += " AND review_required = ?"
            params.append(1 if review_required else 0)
        if disposition is not None:
            sql += " AND ingestion_disposition = ?"
            params.append(disposition)
        sql += " ORDER BY drive_item_id LIMIT ?"
        params.append(int(limit))
        keys = (
            "decision_id",
            "source_id",
            "drive_id",
            "drive_item_id",
            "project_key",
            "project_number_detected",
            "document_type_detected",
            "ingestion_disposition",
            "review_required",
            "review_reason",
            "extraction_allowed",
            "download_allowed",
            "reason_codes_json",
            "decided_utc",
        )
        rows = [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]
        for r in rows:
            for b in ("review_required", "extraction_allowed", "download_allowed"):
                r[b] = bool(r[b])
        return rows

    # --- controlled download + extraction receipts (V19) --------------------

    def insert_download_receipt(
        self,
        *,
        receipt_id: str,
        source_id: str,
        drive_item_id: str,
        drive_id: Optional[str] = None,
        project_key: Optional[str] = None,
        mode: str,
        download_attempted: bool = False,
        download_completed: bool = False,
        bytes_written: Optional[int] = None,
        sha256: Optional[str] = None,
        cache_path_redacted: Optional[str] = None,
        cache_deleted_after_parse: bool = False,
        status: str,
        error_redacted: Optional[str] = None,
    ) -> None:
        """Persist a controlled-download receipt. The schema CHECK forbids a raw
        download URL or a vault-copied source file (both locked to 0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_graph_download_receipts
                    (receipt_id, source_id, drive_id, drive_item_id, project_key, mode,
                     download_attempted, download_completed, bytes_written, sha256,
                     cache_path_redacted, cache_deleted_after_parse, status,
                     error_redacted, created_utc, raw_download_url_persisted,
                     source_file_copied_to_vault)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    receipt_id,
                    source_id,
                    drive_id,
                    drive_item_id,
                    project_key,
                    mode,
                    1 if download_attempted else 0,
                    1 if download_completed else 0,
                    bytes_written,
                    sha256,
                    cache_path_redacted,
                    1 if cache_deleted_after_parse else 0,
                    status,
                    error_redacted,
                    _utc_now(),
                ),
            )

    def list_download_receipts(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = (
            "SELECT receipt_id, source_id, drive_id, drive_item_id, project_key, mode, "
            "download_attempted, download_completed, bytes_written, sha256, "
            "cache_path_redacted, cache_deleted_after_parse, status, error_redacted, "
            "created_utc, raw_download_url_persisted, source_file_copied_to_vault "
            "FROM construction_graph_download_receipts WHERE 1=1"
        )
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        sql += " ORDER BY created_utc DESC LIMIT ?"
        params.append(int(limit))
        keys = (
            "receipt_id",
            "source_id",
            "drive_id",
            "drive_item_id",
            "project_key",
            "mode",
            "download_attempted",
            "download_completed",
            "bytes_written",
            "sha256",
            "cache_path_redacted",
            "cache_deleted_after_parse",
            "status",
            "error_redacted",
            "created_utc",
            "raw_download_url_persisted",
            "source_file_copied_to_vault",
        )
        rows = [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]
        for r in rows:
            for b in (
                "download_attempted",
                "download_completed",
                "cache_deleted_after_parse",
                "raw_download_url_persisted",
                "source_file_copied_to_vault",
            ):
                r[b] = bool(r[b])
        return rows

    def insert_file_extraction_run(
        self,
        *,
        extraction_id: str,
        source_id: str,
        drive_item_id: str,
        drive_id: Optional[str] = None,
        project_key: Optional[str] = None,
        parser_name: str,
        parser_version: str,
        content_hash: Optional[str] = None,
        extraction_status: str,
        text_excerpt_redacted: Optional[str] = None,
        char_count: int = 0,
        review_required: bool = False,
        error_redacted: Optional[str] = None,
    ) -> None:
        """Persist a bounded-extraction run. The schema CHECK forbids full source
        text (full_text_persisted locked to 0); only a redacted excerpt is stored."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_file_extraction_runs
                    (extraction_id, source_id, drive_id, drive_item_id, project_key,
                     parser_name, parser_version, content_hash, extraction_status,
                     text_excerpt_redacted, char_count, full_text_persisted,
                     review_required, error_redacted, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    extraction_id,
                    source_id,
                    drive_id,
                    drive_item_id,
                    project_key,
                    parser_name,
                    parser_version,
                    content_hash,
                    extraction_status,
                    text_excerpt_redacted,
                    char_count,
                    1 if review_required else 0,
                    error_redacted,
                    _utc_now(),
                ),
            )

    def list_file_extraction_runs(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = (
            "SELECT extraction_id, source_id, drive_id, drive_item_id, project_key, "
            "parser_name, parser_version, content_hash, extraction_status, "
            "text_excerpt_redacted, char_count, full_text_persisted, review_required, "
            "error_redacted, created_utc "
            "FROM construction_file_extraction_runs WHERE 1=1"
        )
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        sql += " ORDER BY created_utc DESC LIMIT ?"
        params.append(int(limit))
        keys = (
            "extraction_id",
            "source_id",
            "drive_id",
            "drive_item_id",
            "project_key",
            "parser_name",
            "parser_version",
            "content_hash",
            "extraction_status",
            "text_excerpt_redacted",
            "char_count",
            "full_text_persisted",
            "review_required",
            "error_redacted",
            "created_utc",
        )
        rows = [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]
        for r in rows:
            r["full_text_persisted"] = bool(r["full_text_persisted"])
            r["review_required"] = bool(r["review_required"])
        return rows

    # --- canonical project identity (V5) ------------------------------------

    def upsert_project_identity(
        self,
        *,
        project_key: str,
        hb_project_number: Optional[str] = None,
        project_name_raw: Optional[str] = None,
        project_name_normalized: Optional[str] = None,
        is_active: bool = True,
        procore_project_id: Optional[str] = None,
        project_stage: Optional[str] = None,
        last_seen_utc: Optional[str] = None,
        last_validated_utc: Optional[str] = None,
        match_status: Optional[str] = None,
        match_confidence: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_project_identity
                    (project_key, hb_project_number, project_name_raw,
                     project_name_normalized, is_active, procore_project_id,
                     project_stage, last_seen_utc, last_validated_utc,
                     match_status, match_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_key) DO UPDATE SET
                    hb_project_number = excluded.hb_project_number,
                    project_name_raw = excluded.project_name_raw,
                    project_name_normalized = excluded.project_name_normalized,
                    is_active = excluded.is_active,
                    procore_project_id = excluded.procore_project_id,
                    project_stage = excluded.project_stage,
                    last_seen_utc = excluded.last_seen_utc,
                    last_validated_utc = excluded.last_validated_utc,
                    match_status = excluded.match_status,
                    match_confidence = excluded.match_confidence
                """,
                (
                    project_key,
                    hb_project_number,
                    project_name_raw,
                    project_name_normalized,
                    1 if is_active else 0,
                    procore_project_id,
                    project_stage,
                    last_seen_utc,
                    last_validated_utc,
                    match_status,
                    match_confidence,
                ),
            )

    def get_project_identity(self, project_key: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT project_key, hb_project_number, project_name_raw,
                   project_name_normalized, is_active, procore_project_id,
                   project_stage, last_seen_utc, last_validated_utc,
                   match_status, match_confidence
            FROM construction_project_identity
            WHERE project_key = ?
            """,
            (project_key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "project_key",
            "hb_project_number",
            "project_name_raw",
            "project_name_normalized",
            "is_active",
            "procore_project_id",
            "project_stage",
            "last_seen_utc",
            "last_validated_utc",
            "match_status",
            "match_confidence",
        )
        record = dict(zip(keys, row, strict=True))
        record["is_active"] = bool(record["is_active"])
        return record

    # --- canonical project-source matches (V5) ------------------------------

    def upsert_project_source_match(
        self,
        *,
        project_key: str,
        source_id: str,
        match_method: str,
        match_confidence: str,
        review_required: bool = False,
    ) -> int:
        """Upsert a project↔source match. Returns the row id."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO construction_project_source_matches
                    (project_key, source_id, match_method, match_confidence,
                     review_required, created_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_key, source_id) DO UPDATE SET
                    match_method = excluded.match_method,
                    match_confidence = excluded.match_confidence,
                    review_required = excluded.review_required
                RETURNING id
                """,
                (
                    project_key,
                    source_id,
                    match_method,
                    match_confidence,
                    1 if review_required else 0,
                    _utc_now(),
                ),
            )
            row = cur.fetchone()
            return int(row[0])

    def list_project_source_matches(
        self,
        *,
        project_key: Optional[str] = None,
        review_required: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = """
            SELECT id, project_key, source_id, match_method, match_confidence,
                   review_required, created_utc
            FROM construction_project_source_matches
            WHERE 1=1
        """
        params: list[Any] = []
        if project_key is not None:
            sql += " AND project_key = ?"
            params.append(project_key)
        if review_required is not None:
            sql += " AND review_required = ?"
            params.append(1 if review_required else 0)
        sql += " ORDER BY id LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = (
            "id",
            "project_key",
            "source_id",
            "match_method",
            "match_confidence",
            "review_required",
            "created_utc",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]
        for r in rows:
            r["review_required"] = bool(r["review_required"])
        return rows

    # --- project keyword registry (V40 / Prompt 05 UI-05) -------------------
    # User-managed training config for project matching explain. Never stores
    # raw content, subjects, paths, or tokens. Folder-name exclusions enforced
    # at the analytics service layer (construction_project_keyword_registry is
    # additive; V1-V39 untouched).

    def upsert_project_keyword_registry_entry(
        self,
        *,
        keyword_id: str,
        project_key: str,
        keyword_normalized: str,
        keyword_class: str = "phrase",
        strength: str = "normal",
        registry_status: str = "enabled",
        provenance: str,
        provenance_ref_hash: Optional[str] = None,
        notes_redacted: Optional[str] = None,
    ) -> None:
        """Upsert a project keyword training entry.

        keyword_id is a stable opaque id (hash-derived by caller).
        keyword_hash for (project, hash) uniqueness is derived here from the
        normalized term. Guard columns default via schema CHECK=0.
        """
        if not keyword_id or not project_key or not keyword_normalized:
            raise ValueError("keyword_id, project_key, and keyword_normalized are required")
        kw_hash = hash_value(keyword_normalized) or ""
        now = _utc_now()
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_project_keyword_registry
                    (keyword_id, project_key, keyword_hash, keyword_normalized,
                     keyword_class, strength, registry_status, provenance,
                     provenance_ref_hash, notes_redacted, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(keyword_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    keyword_hash = excluded.keyword_hash,
                    keyword_normalized = excluded.keyword_normalized,
                    keyword_class = excluded.keyword_class,
                    strength = excluded.strength,
                    registry_status = excluded.registry_status,
                    provenance = excluded.provenance,
                    provenance_ref_hash = excluded.provenance_ref_hash,
                    notes_redacted = excluded.notes_redacted,
                    updated_utc = ?
                """,
                (
                    keyword_id,
                    project_key,
                    kw_hash,
                    keyword_normalized,
                    keyword_class,
                    strength,
                    registry_status,
                    provenance,
                    provenance_ref_hash,
                    notes_redacted,
                    now,
                    now,
                    now,
                ),
            )

    def get_project_keyword_registry_entry(self, keyword_id: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT keyword_id, project_key, keyword_hash, keyword_normalized,
                   keyword_class, strength, registry_status, provenance,
                   provenance_ref_hash, notes_redacted, created_utc, updated_utc,
                   last_applied_utc
            FROM construction_project_keyword_registry
            WHERE keyword_id = ?
            """,
            (keyword_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "keyword_id",
            "project_key",
            "keyword_hash",
            "keyword_normalized",
            "keyword_class",
            "strength",
            "registry_status",
            "provenance",
            "provenance_ref_hash",
            "notes_redacted",
            "created_utc",
            "updated_utc",
            "last_applied_utc",
        )
        return dict(zip(keys, row, strict=True))

    def list_project_keyword_registry(
        self,
        *,
        project_key: str,
        registry_status: Optional[str] = None,
        strength: Optional[str] = None,
        provenance: Optional[str] = None,
        include_excluded: bool = False,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """List keywords for a project.

        When registry_status is None and include_excluded=False, returns
        enabled + disabled (excludes 'excluded' rows). Primary loader for
        matchers should pass registry_status='enabled'.
        """
        conn = get_connection(self._db_path)
        sql = """
            SELECT keyword_id, project_key, keyword_hash, keyword_normalized,
                   keyword_class, strength, registry_status, provenance,
                   provenance_ref_hash, notes_redacted, created_utc, updated_utc,
                   last_applied_utc
            FROM construction_project_keyword_registry
            WHERE project_key = ?
        """
        params: list[Any] = [project_key]
        if registry_status is not None:
            sql += " AND registry_status = ?"
            params.append(registry_status)
        elif not include_excluded:
            sql += " AND registry_status != 'excluded'"
        if strength is not None:
            sql += " AND strength = ?"
            params.append(strength)
        if provenance is not None:
            sql += " AND provenance = ?"
            params.append(provenance)
        sql += " ORDER BY strength DESC, keyword_normalized ASC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = (
            "keyword_id",
            "project_key",
            "keyword_hash",
            "keyword_normalized",
            "keyword_class",
            "strength",
            "registry_status",
            "provenance",
            "provenance_ref_hash",
            "notes_redacted",
            "created_utc",
            "updated_utc",
            "last_applied_utc",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def set_project_keyword_registry_status(
        self,
        *,
        keyword_id: str,
        registry_status: str,
    ) -> None:
        """Update status (enabled | disabled | excluded) for an existing entry."""
        if registry_status not in {"enabled", "disabled", "excluded"}:
            raise ValueError("invalid registry_status")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                UPDATE construction_project_keyword_registry
                SET registry_status = ?, updated_utc = ?
                WHERE keyword_id = ?
                """,
                (registry_status, _utc_now(), keyword_id),
            )

    def delete_project_keyword_registry_entry(self, keyword_id: str) -> None:
        """Hard delete a keyword entry (prefer status=disabled/excluded for audit)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                "DELETE FROM construction_project_keyword_registry WHERE keyword_id = ?",
                (keyword_id,),
            )

    # --- canonical document cards (V5) --------------------------------------

    def upsert_document_card(
        self,
        *,
        card_id: str,
        source_id: str,
        drive_item_id: Optional[str] = None,
        project_key: Optional[str] = None,
        document_type: Optional[str] = None,
        status: str = "candidate",
        confidence: Optional[float] = None,
        needs_review: bool = True,
        card_path: Optional[str] = None,
        # Phase 07C (V24) safe fields — hashed/redacted/bounded only. The six
        # raw/url/payload/copy/writeback guard columns are never written here and
        # stay at their CHECK(... = 0) defaults. NOT-NULL V24 columns default to
        # their schema defaults so legacy callers are unaffected.
        document_card_id: Optional[str] = None,
        drive_id_hash: Optional[str] = None,
        drive_item_id_hash: Optional[str] = None,
        project_number_hash: Optional[str] = None,
        title_hash: Optional[str] = None,
        title_redacted: Optional[str] = None,
        file_extension: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_class: str = "unknown",
        source_path_hash: Optional[str] = None,
        source_path_token_hashes_json: Optional[str] = None,
        last_modified_datetime: Optional[str] = None,
        source_reference_json: Optional[str] = None,
        review_status: str = "pending",
        review_required: bool = False,
        review_reasons_json: Optional[str] = None,
        extraction_eligibility: str = "not_evaluated",
        confidence_class: str = "unknown",
        guardrail_flags_json: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_document_cards
                    (card_id, source_id, drive_item_id, project_key,
                     document_type, status, confidence, needs_review, card_path,
                     created_utc, updated_utc,
                     document_card_id, drive_id_hash, drive_item_id_hash,
                     project_number_hash, title_hash, title_redacted, file_extension,
                     mime_type, size_class, source_path_hash,
                     source_path_token_hashes_json, last_modified_datetime,
                     source_reference_json, review_status, review_required,
                     review_reasons_json, extraction_eligibility, confidence_class,
                     guardrail_flags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    source_id = excluded.source_id,
                    drive_item_id = excluded.drive_item_id,
                    project_key = excluded.project_key,
                    document_type = excluded.document_type,
                    status = excluded.status,
                    confidence = excluded.confidence,
                    needs_review = excluded.needs_review,
                    card_path = excluded.card_path,
                    updated_utc = excluded.updated_utc,
                    document_card_id = excluded.document_card_id,
                    drive_id_hash = excluded.drive_id_hash,
                    drive_item_id_hash = excluded.drive_item_id_hash,
                    project_number_hash = excluded.project_number_hash,
                    title_hash = excluded.title_hash,
                    title_redacted = excluded.title_redacted,
                    file_extension = excluded.file_extension,
                    mime_type = excluded.mime_type,
                    size_class = excluded.size_class,
                    source_path_hash = excluded.source_path_hash,
                    source_path_token_hashes_json = excluded.source_path_token_hashes_json,
                    last_modified_datetime = excluded.last_modified_datetime,
                    source_reference_json = excluded.source_reference_json,
                    review_status = excluded.review_status,
                    review_required = excluded.review_required,
                    review_reasons_json = excluded.review_reasons_json,
                    extraction_eligibility = excluded.extraction_eligibility,
                    confidence_class = excluded.confidence_class,
                    guardrail_flags_json = excluded.guardrail_flags_json
                """,
                (
                    card_id,
                    source_id,
                    drive_item_id,
                    project_key,
                    document_type,
                    status,
                    confidence,
                    1 if needs_review else 0,
                    card_path,
                    _utc_now(),
                    _utc_now(),
                    document_card_id,
                    drive_id_hash,
                    drive_item_id_hash,
                    project_number_hash,
                    title_hash,
                    title_redacted,
                    file_extension,
                    mime_type,
                    size_class,
                    source_path_hash,
                    source_path_token_hashes_json,
                    last_modified_datetime,
                    source_reference_json,
                    review_status,
                    1 if review_required else 0,
                    review_reasons_json,
                    extraction_eligibility,
                    confidence_class,
                    guardrail_flags_json,
                ),
            )

    def get_document_card(self, card_id: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT * FROM construction_document_cards WHERE card_id = ?",
            (card_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = [d[0] for d in cur.description]
        record = dict(zip(keys, row, strict=True))
        if "needs_review" in record:
            record["needs_review"] = bool(record["needs_review"])
        if "review_required" in record:
            record["review_required"] = bool(record["review_required"])
        return record

    def count_document_cards(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM construction_document_cards")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def distinct_inventory_source_keys(self) -> list[str]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT DISTINCT source_key FROM construction_drive_item_inventory ORDER BY source_key"
        )
        return [r[0] for r in cur.fetchall()]

    def list_document_cards(self) -> list[dict[str, Any]]:
        """List the safe fields of every document card (for classification/matching)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT card_id, document_card_id, source_id, drive_item_id, file_extension,
                   mime_type, project_key, project_number_hash, document_type,
                   source_path_token_hashes_json, review_status, review_required,
                   extraction_eligibility, size_class
            FROM construction_document_cards
            ORDER BY card_id
            """
        )
        keys = (
            "card_id",
            "document_card_id",
            "source_id",
            "drive_item_id",
            "file_extension",
            "mime_type",
            "project_key",
            "project_number_hash",
            "document_type",
            "source_path_token_hashes_json",
            "review_status",
            "review_required",
            "extraction_eligibility",
            "size_class",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # --- Phase 07C document classification candidates (V24) -----------------

    def upsert_document_classification_candidate(
        self,
        *,
        candidate_id: str,
        document_card_id: str,
        document_type: str,
        classifier_name: str,
        signal_class: str,
        confidence: float,
        confidence_class: str,
        signals_json: Optional[str] = None,
        review_required: bool = False,
        promotion_status: str = "candidate",
    ) -> None:
        """Upsert an advisory document classification candidate (V24). Idempotent by
        candidate_id. The raw_document_text / raw_prompt / raw_response /
        external_writeback guard CHECK columns are never written here — the schema
        defaults (all 0) hold. No raw document text/prompt/response is accepted; only
        the document type, signal class, confidence, and hashed/typed signal evidence
        round-trip through ``signals_json``.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_document_classification_candidates
                    (candidate_id, document_card_id, document_type, classifier_name,
                     signal_class, confidence, confidence_class, signals_json,
                     review_required, promotion_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    document_card_id = excluded.document_card_id,
                    document_type = excluded.document_type,
                    classifier_name = excluded.classifier_name,
                    signal_class = excluded.signal_class,
                    confidence = excluded.confidence,
                    confidence_class = excluded.confidence_class,
                    signals_json = excluded.signals_json,
                    review_required = excluded.review_required,
                    promotion_status = excluded.promotion_status
                """,
                (
                    candidate_id,
                    document_card_id,
                    document_type,
                    classifier_name,
                    signal_class,
                    confidence,
                    confidence_class,
                    signals_json,
                    1 if review_required else 0,
                    promotion_status,
                    _utc_now(),
                ),
            )

    def count_document_classification_candidates(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM construction_document_classification_candidates")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    # --- Phase 07C document project match candidates (V24) ------------------

    def upsert_document_project_match_candidate(
        self,
        *,
        candidate_id: str,
        document_card_id: str,
        project_key: str,
        candidate_type: str,
        confidence: float,
        confidence_class: str,
        signals_json: Optional[str] = None,
        deterministic: bool = False,
        model_proposed: bool = False,
        review_required: bool = True,
        promotion_status: str = "candidate",
    ) -> None:
        """Upsert an advisory document->project match candidate (V24). Idempotent by
        candidate_id. The raw_document_text / external_writeback guard CHECK columns
        are never written here — the schema defaults (both 0) hold. No raw path/name/URL
        is accepted; only the project key, candidate type, confidence, and
        hashed/typed signal evidence round-trip through ``signals_json``.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_document_project_match_candidates
                    (candidate_id, document_card_id, project_key, candidate_type,
                     confidence, confidence_class, deterministic, model_proposed,
                     review_required, promotion_status, signals_json, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    document_card_id = excluded.document_card_id,
                    project_key = excluded.project_key,
                    candidate_type = excluded.candidate_type,
                    confidence = excluded.confidence,
                    confidence_class = excluded.confidence_class,
                    deterministic = excluded.deterministic,
                    model_proposed = excluded.model_proposed,
                    review_required = excluded.review_required,
                    promotion_status = excluded.promotion_status,
                    signals_json = excluded.signals_json
                """,
                (
                    candidate_id,
                    document_card_id,
                    project_key,
                    candidate_type,
                    confidence,
                    confidence_class,
                    1 if deterministic else 0,
                    1 if model_proposed else 0,
                    1 if review_required else 0,
                    promotion_status,
                    signals_json,
                    _utc_now(),
                ),
            )

    def count_document_project_match_candidates(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM construction_document_project_match_candidates")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def list_document_classification_candidates(self) -> list[dict[str, Any]]:
        """List the safe fields of every document classification candidate (V24)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT candidate_id, document_card_id, document_type, confidence_class,
                   review_required, promotion_status
            FROM construction_document_classification_candidates
            ORDER BY candidate_id
            """
        )
        keys = (
            "candidate_id",
            "document_card_id",
            "document_type",
            "confidence_class",
            "review_required",
            "promotion_status",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # --- Phase 07C document->record relationship candidates (V24) -----------

    def upsert_document_relationship_candidate(
        self,
        *,
        candidate_id: str,
        document_card_id: str,
        target_system: str,
        target_record_type: str,
        target_record_key_hash: str,
        relationship_type: str,
        candidate_type: str,
        confidence: float,
        confidence_class: str,
        source_reference_json: Optional[str] = None,
        signals_json: Optional[str] = None,
        review_required: bool = True,
        promotion_status: str = "candidate",
    ) -> None:
        """Upsert an advisory document->record relationship candidate (V24). Idempotent
        by candidate_id. The raw_document_text / raw_prompt / raw_response /
        external_writeback guard CHECK columns are never written here — the schema
        defaults (all 0) hold. No raw document text / path / URL / record body is
        accepted; the target record is identified only by a hashed key, and only
        hashed/typed evidence round-trips through signals_json / source_reference_json.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_document_relationship_candidates
                    (candidate_id, document_card_id, target_system, target_record_type,
                     target_record_key_hash, relationship_type, candidate_type,
                     confidence, confidence_class, source_reference_json, signals_json,
                     review_required, promotion_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    document_card_id = excluded.document_card_id,
                    target_system = excluded.target_system,
                    target_record_type = excluded.target_record_type,
                    target_record_key_hash = excluded.target_record_key_hash,
                    relationship_type = excluded.relationship_type,
                    candidate_type = excluded.candidate_type,
                    confidence = excluded.confidence,
                    confidence_class = excluded.confidence_class,
                    source_reference_json = excluded.source_reference_json,
                    signals_json = excluded.signals_json,
                    review_required = excluded.review_required,
                    promotion_status = excluded.promotion_status
                """,
                (
                    candidate_id,
                    document_card_id,
                    target_system,
                    target_record_type,
                    target_record_key_hash,
                    relationship_type,
                    candidate_type,
                    confidence,
                    confidence_class,
                    source_reference_json,
                    signals_json,
                    1 if review_required else 0,
                    promotion_status,
                    _utc_now(),
                ),
            )

    def count_document_relationship_candidates(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM construction_document_relationship_candidates")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def list_document_project_match_candidates(self) -> list[dict[str, Any]]:
        """List the safe fields of every document->project match candidate (V24)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT candidate_id, document_card_id, project_key, candidate_type,
                   confidence_class, review_required
            FROM construction_document_project_match_candidates
            ORDER BY candidate_id
            """
        )
        keys = (
            "candidate_id",
            "document_card_id",
            "project_key",
            "candidate_type",
            "confidence_class",
            "review_required",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_document_relationship_candidates(self) -> list[dict[str, Any]]:
        """List the safe fields of every document->record relationship candidate (V24)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT candidate_id, document_card_id, target_system, target_record_type,
                   candidate_type, confidence_class, review_required
            FROM construction_document_relationship_candidates
            ORDER BY candidate_id
            """
        )
        keys = (
            "candidate_id",
            "document_card_id",
            "target_system",
            "target_record_type",
            "candidate_type",
            "confidence_class",
            "review_required",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_document_relationship_candidates_full(self) -> list[dict[str, Any]]:
        """List the safe full field set of every document->record relationship candidate
        (V24) needed by the 07D cross-source substrate normalizer. The target record is a
        hashed key and source_reference_json carries hashed/typed evidence only — no raw
        document text / path / URL ever round-trips here."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT candidate_id, document_card_id, target_system, target_record_type,
                   target_record_key_hash, relationship_type, candidate_type,
                   confidence, confidence_class, review_required, source_reference_json
            FROM construction_document_relationship_candidates
            ORDER BY candidate_id
            """
        )
        keys = (
            "candidate_id",
            "document_card_id",
            "target_system",
            "target_record_type",
            "target_record_key_hash",
            "relationship_type",
            "candidate_type",
            "confidence",
            "confidence_class",
            "review_required",
            "source_reference_json",
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["review_required"] = bool(record["review_required"])
            record["source_reference_json"] = self._load_json(record["source_reference_json"])
            results.append(record)
        return results

    # --- Phase 07D cross-source relationship substrate (V25) ----------------

    def upsert_cross_source_relationship_candidate(
        self,
        *,
        candidate_id: str,
        source_family: str,
        source_record_type: str,
        source_record_ref: str,
        target_family: str,
        target_record_type: str,
        target_record_ref: str,
        relationship_type: str,
        confidence_score: float,
        confidence_class: str,
        source_reference_json: str,
        project_key: Optional[str] = None,
        deterministic: bool = False,
        model_proposed: bool = False,
        sensitive_high_impact: bool = False,
        review_required: bool = True,
        promotion_status: str = "candidate",
        signals_json: Optional[str] = None,
        evidence_trail_id: Optional[str] = None,
    ) -> None:
        """Upsert a unified cross-source relationship candidate (V25). Idempotent by
        candidate_id (a deterministic hash of the source/target/relationship edge, which
        also matches the table's UNIQUE edge key). The eight no-raw / no-writeback guard
        CHECK columns are never written — the schema defaults (all 0) hold. Record refs are
        local stable identifiers or existing hashes; only hashed/typed/enum evidence
        round-trips through signals_json / source_reference_json."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO cross_source_relationship_candidates
                    (candidate_id, project_key, source_family, source_record_type,
                     source_record_ref, target_family, target_record_type, target_record_ref,
                     relationship_type, confidence_score, confidence_class, deterministic,
                     model_proposed, sensitive_high_impact, review_required, promotion_status,
                     signals_json, source_reference_json, evidence_trail_id, created_utc,
                     updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    source_family = excluded.source_family,
                    source_record_type = excluded.source_record_type,
                    source_record_ref = excluded.source_record_ref,
                    target_family = excluded.target_family,
                    target_record_type = excluded.target_record_type,
                    target_record_ref = excluded.target_record_ref,
                    relationship_type = excluded.relationship_type,
                    confidence_score = excluded.confidence_score,
                    confidence_class = excluded.confidence_class,
                    deterministic = excluded.deterministic,
                    model_proposed = excluded.model_proposed,
                    sensitive_high_impact = excluded.sensitive_high_impact,
                    review_required = excluded.review_required,
                    promotion_status = excluded.promotion_status,
                    signals_json = excluded.signals_json,
                    source_reference_json = excluded.source_reference_json,
                    evidence_trail_id = excluded.evidence_trail_id,
                    updated_utc = excluded.updated_utc
                """,
                (
                    candidate_id,
                    project_key,
                    source_family,
                    source_record_type,
                    source_record_ref,
                    target_family,
                    target_record_type,
                    target_record_ref,
                    relationship_type,
                    confidence_score,
                    confidence_class,
                    1 if deterministic else 0,
                    1 if model_proposed else 0,
                    1 if sensitive_high_impact else 0,
                    1 if review_required else 0,
                    promotion_status,
                    signals_json,
                    source_reference_json,
                    evidence_trail_id,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def count_cross_source_relationship_candidates(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM cross_source_relationship_candidates")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    _CROSS_SOURCE_CANDIDATE_KEYS: tuple[str, ...] = (
        "candidate_id",
        "project_key",
        "source_family",
        "source_record_type",
        "source_record_ref",
        "target_family",
        "target_record_type",
        "target_record_ref",
        "relationship_type",
        "confidence_score",
        "confidence_class",
        "deterministic",
        "model_proposed",
        "sensitive_high_impact",
        "review_required",
        "promotion_status",
        "signals_json",
        "source_reference_json",
        "evidence_trail_id",
    )

    def list_cross_source_relationship_candidates(
        self,
        *,
        project_key: Optional[str] = None,
        review_required: Optional[bool] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List unified cross-source relationship candidates (V25) with optional filters.
        Returns safe identifier/hash/enum fields only; JSON columns are decoded."""
        keys = self._CROSS_SOURCE_CANDIDATE_KEYS
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if review_required is not None:
            clauses.append("review_required = ?")
            params.append(1 if review_required else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM cross_source_relationship_candidates "
            f"{where} ORDER BY confidence_score DESC, candidate_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for json_field in ("signals_json", "source_reference_json"):
                record[json_field] = self._load_json(record[json_field])
            for bool_field in (
                "deterministic",
                "model_proposed",
                "sensitive_high_impact",
                "review_required",
            ):
                record[bool_field] = bool(record[bool_field])
            results.append(record)
        return results

    def upsert_source_evidence_trail(
        self,
        *,
        evidence_trail_id: str,
        evidence_kind: str,
        source_refs_json: str,
        confidence_class: str,
        project_key: Optional[str] = None,
        relationship_candidate_id: Optional[str] = None,
        review_required: bool = False,
        stale_unknown_flags_json: Optional[str] = None,
    ) -> None:
        """Upsert a redacted source evidence trail (V25). Idempotent by evidence_trail_id.
        source_refs_json holds compact local identifiers / hashes only — never a raw body,
        signed URL, or download URL. Guard CHECK columns keep their schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO source_evidence_trails
                    (evidence_trail_id, project_key, evidence_kind, relationship_candidate_id,
                     source_refs_json, confidence_class, review_required,
                     stale_unknown_flags_json, generated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_trail_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    evidence_kind = excluded.evidence_kind,
                    relationship_candidate_id = excluded.relationship_candidate_id,
                    source_refs_json = excluded.source_refs_json,
                    confidence_class = excluded.confidence_class,
                    review_required = excluded.review_required,
                    stale_unknown_flags_json = excluded.stale_unknown_flags_json
                """,
                (
                    evidence_trail_id,
                    project_key,
                    evidence_kind,
                    relationship_candidate_id,
                    source_refs_json,
                    confidence_class,
                    1 if review_required else 0,
                    stale_unknown_flags_json,
                    _utc_now(),
                ),
            )

    def count_source_evidence_trails(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM source_evidence_trails")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def list_source_evidence_trails(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List redacted source evidence trails (V25). Safe fields only; JSON decoded."""
        keys = (
            "evidence_trail_id",
            "project_key",
            "evidence_kind",
            "relationship_candidate_id",
            "source_refs_json",
            "confidence_class",
            "review_required",
            "stale_unknown_flags_json",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM source_evidence_trails {where} "
            "ORDER BY evidence_trail_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for json_field in ("source_refs_json", "stale_unknown_flags_json"):
                record[json_field] = self._load_json(record[json_field])
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def upsert_cross_source_relationship(
        self,
        *,
        relationship_id: str,
        source_family: str,
        source_record_type: str,
        source_record_ref: str,
        target_family: str,
        target_record_type: str,
        target_record_ref: str,
        relationship_type: str,
        confidence_class: str,
        source_reference_json: str,
        candidate_id: Optional[str] = None,
        project_key: Optional[str] = None,
        promotion_status: str = "promoted",
        promoted_by: str = "deterministic",
        review_required: bool = False,
        signals_json: Optional[str] = None,
        evidence_trail_id: Optional[str] = None,
    ) -> None:
        """Upsert a promoted/confirmed cross-source relationship (V25). Idempotent by
        relationship_id. Ships for Phase 07D Prompt 04's policy-gated promotion path; the
        Prompt 03 substrate builder never calls this (no auto-promotion). Guard CHECK
        columns keep their schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO cross_source_relationships
                    (relationship_id, candidate_id, project_key, source_family,
                     source_record_type, source_record_ref, target_family, target_record_type,
                     target_record_ref, relationship_type, confidence_class, promotion_status,
                     promoted_by, review_required, signals_json, source_reference_json,
                     evidence_trail_id, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relationship_id) DO UPDATE SET
                    candidate_id = excluded.candidate_id,
                    project_key = excluded.project_key,
                    source_family = excluded.source_family,
                    source_record_type = excluded.source_record_type,
                    source_record_ref = excluded.source_record_ref,
                    target_family = excluded.target_family,
                    target_record_type = excluded.target_record_type,
                    target_record_ref = excluded.target_record_ref,
                    relationship_type = excluded.relationship_type,
                    confidence_class = excluded.confidence_class,
                    promotion_status = excluded.promotion_status,
                    promoted_by = excluded.promoted_by,
                    review_required = excluded.review_required,
                    signals_json = excluded.signals_json,
                    source_reference_json = excluded.source_reference_json,
                    evidence_trail_id = excluded.evidence_trail_id,
                    updated_utc = excluded.updated_utc
                """,
                (
                    relationship_id,
                    candidate_id,
                    project_key,
                    source_family,
                    source_record_type,
                    source_record_ref,
                    target_family,
                    target_record_type,
                    target_record_ref,
                    relationship_type,
                    confidence_class,
                    promotion_status,
                    promoted_by,
                    1 if review_required else 0,
                    signals_json,
                    source_reference_json,
                    evidence_trail_id,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def count_cross_source_relationships(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM cross_source_relationships")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    _CROSS_SOURCE_RELATIONSHIP_KEYS: tuple[str, ...] = (
        "relationship_id",
        "candidate_id",
        "project_key",
        "source_family",
        "source_record_type",
        "source_record_ref",
        "target_family",
        "target_record_type",
        "target_record_ref",
        "relationship_type",
        "confidence_class",
        "promotion_status",
        "promoted_by",
        "review_required",
        "signals_json",
        "source_reference_json",
        "evidence_trail_id",
    )

    def list_cross_source_relationships(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List promoted cross-source relationships (V25). Safe identifier/enum fields only;
        JSON columns decoded. The eight guard CHECK columns are not selected."""
        keys = self._CROSS_SOURCE_RELATIONSHIP_KEYS
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM cross_source_relationships {where} "
            "ORDER BY relationship_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for json_field in ("signals_json", "source_reference_json"):
                record[json_field] = self._load_json(record[json_field])
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    # --- Phase 07D Prompt 06 meeting-prep brief materialization (V25) ---------

    def upsert_meeting_prep_brief_run(
        self,
        *,
        brief_run_id: str,
        project_key: str,
        mode: str,
        lookahead_days: int,
        status: str,
        event_index_id: Optional[str] = None,
        sections_written: int = 0,
        review_required_count: int = 0,
    ) -> None:
        """Upsert a meeting-prep brief run (V25). Idempotent by brief_run_id (a deterministic
        hash of project_key + lookahead). ``mode`` is 'dry_run' or 'apply'. Guard CHECK
        columns keep their schema defaults (0); no raw content is written."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO meeting_prep_brief_runs
                    (brief_run_id, project_key, event_index_id, mode, lookahead_days, status,
                     sections_written, review_required_count, generated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(brief_run_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    event_index_id = excluded.event_index_id,
                    mode = excluded.mode,
                    lookahead_days = excluded.lookahead_days,
                    status = excluded.status,
                    sections_written = excluded.sections_written,
                    review_required_count = excluded.review_required_count,
                    generated_utc = excluded.generated_utc
                """,
                (
                    brief_run_id,
                    project_key,
                    event_index_id,
                    mode,
                    lookahead_days,
                    status,
                    sections_written,
                    review_required_count,
                    _utc_now(),
                ),
            )

    def upsert_meeting_prep_brief_section(
        self,
        *,
        section_id: str,
        brief_run_id: str,
        section_kind: str,
        section_redacted: str,
        confidence_class: str,
        evidence_trail_id: Optional[str] = None,
        review_required: bool = False,
        stale_unknown_flags_json: Optional[str] = None,
    ) -> None:
        """Upsert a meeting-prep brief section (V25). Idempotent by section_id (a deterministic
        hash of brief_run_id + section_kind). section_redacted holds compact counts / enums /
        local identifiers only — never a raw body, document text, calendar payload, URL, or
        token. Guard CHECK columns keep their schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO meeting_prep_brief_sections
                    (section_id, brief_run_id, section_kind, section_redacted, evidence_trail_id,
                     confidence_class, review_required, stale_unknown_flags_json, generated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(section_id) DO UPDATE SET
                    brief_run_id = excluded.brief_run_id,
                    section_kind = excluded.section_kind,
                    section_redacted = excluded.section_redacted,
                    evidence_trail_id = excluded.evidence_trail_id,
                    confidence_class = excluded.confidence_class,
                    review_required = excluded.review_required,
                    stale_unknown_flags_json = excluded.stale_unknown_flags_json,
                    generated_utc = excluded.generated_utc
                """,
                (
                    section_id,
                    brief_run_id,
                    section_kind,
                    section_redacted,
                    evidence_trail_id,
                    confidence_class,
                    1 if review_required else 0,
                    stale_unknown_flags_json,
                    _utc_now(),
                ),
            )

    def list_meeting_prep_brief_runs(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List meeting-prep brief runs (V25). Safe fields only."""
        keys = (
            "brief_run_id",
            "project_key",
            "event_index_id",
            "mode",
            "lookahead_days",
            "status",
            "sections_written",
            "review_required_count",
            "generated_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM meeting_prep_brief_runs {where} "
            "ORDER BY brief_run_id LIMIT ?",
            tuple(params),
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_meeting_prep_brief_sections(
        self,
        *,
        brief_run_id: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List meeting-prep brief sections (V25). Safe fields only; JSON decoded."""
        keys = (
            "section_id",
            "brief_run_id",
            "section_kind",
            "section_redacted",
            "evidence_trail_id",
            "confidence_class",
            "review_required",
            "stale_unknown_flags_json",
            "generated_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if brief_run_id is not None:
            clauses.append("brief_run_id = ?")
            params.append(brief_run_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM meeting_prep_brief_sections {where} "
            "ORDER BY section_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["stale_unknown_flags_json"] = self._load_json(record["stale_unknown_flags_json"])
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def count_meeting_prep_brief_runs(self) -> int:
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT COUNT(*) FROM meeting_prep_brief_runs").fetchone()
        return int(row[0]) if row else 0

    def count_meeting_prep_brief_sections(self) -> int:
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT COUNT(*) FROM meeting_prep_brief_sections").fetchone()
        return int(row[0]) if row else 0

    # --- Phase 07D Prompt 07 project issue history (V25) ----------------------

    def upsert_project_issue_history_item(
        self,
        *,
        issue_family_id: str,
        project_key: str,
        status: str,
        source_families_json: str,
        confidence_class: str,
        issue_kind: Optional[str] = None,
        age_days: int = 0,
        latest_activity_utc: Optional[str] = None,
        evidence_trail_id: Optional[str] = None,
        review_required: bool = False,
        stale_unknown_flags_json: Optional[str] = None,
    ) -> None:
        """Upsert a project issue-history family (V25). Idempotent by issue_family_id (a
        deterministic hash of the anchor source record). status is a normalized bounded token;
        source_families_json / stale_unknown_flags_json carry families/flags only — never a raw
        body, document text, calendar payload, status payload, URL, or token. Guard CHECK
        columns keep their schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO project_issue_history_items
                    (issue_family_id, project_key, issue_kind, status, age_days,
                     latest_activity_utc, source_families_json, evidence_trail_id,
                     confidence_class, review_required, stale_unknown_flags_json,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_family_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    issue_kind = excluded.issue_kind,
                    status = excluded.status,
                    age_days = excluded.age_days,
                    latest_activity_utc = excluded.latest_activity_utc,
                    source_families_json = excluded.source_families_json,
                    evidence_trail_id = excluded.evidence_trail_id,
                    confidence_class = excluded.confidence_class,
                    review_required = excluded.review_required,
                    stale_unknown_flags_json = excluded.stale_unknown_flags_json,
                    updated_utc = excluded.updated_utc
                """,
                (
                    issue_family_id,
                    project_key,
                    issue_kind,
                    status,
                    age_days,
                    latest_activity_utc,
                    source_families_json,
                    evidence_trail_id,
                    confidence_class,
                    1 if review_required else 0,
                    stale_unknown_flags_json,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def list_project_issue_history_items(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List project issue-history families (V25). Safe fields only; JSON decoded."""
        keys = (
            "issue_family_id",
            "project_key",
            "issue_kind",
            "status",
            "age_days",
            "latest_activity_utc",
            "source_families_json",
            "evidence_trail_id",
            "confidence_class",
            "review_required",
            "stale_unknown_flags_json",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM project_issue_history_items {where} "
            "ORDER BY issue_family_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for json_field in ("source_families_json", "stale_unknown_flags_json"):
                record[json_field] = self._load_json(record[json_field])
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def count_project_issue_history_items(self) -> int:
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT COUNT(*) FROM project_issue_history_items").fetchone()
        return int(row[0]) if row else 0

    # --- Phase 07D Prompt 08 risk digest (V25) -------------------------------

    def list_procore_action_signals(
        self,
        *,
        project_key: Optional[str] = None,
        signal_status: Optional[str] = None,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        """List Procore action signals (V7) — safe identifier/enum fields only (never
        title_redacted / summary_redacted / metadata_json free-text)."""
        keys = (
            "action_signal_id",
            "project_key",
            "record_key",
            "endpoint_id",
            "signal_type",
            "signal_status",
            "importance",
            "due_at_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if signal_status is not None:
            clauses.append("signal_status = ?")
            params.append(signal_status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM procore_action_signals {where} "
            "ORDER BY action_signal_id LIMIT ?",
            tuple(params),
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_procore_action_signals_for_ranking(
        self,
        *,
        project_key: Optional[str] = None,
        signal_status: Optional[str] = None,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        """List Procore action signals with the extra fields the daily-brief ranker needs.

        Adds owner/source-change/observation timestamps to the safe-enum set so ranking can compute
        owner-linked / source-change-linked / recent. Still excludes free-text
        (title_redacted / summary_redacted / metadata_json). Callers MUST convert ``owner_entity_key``
        and ``source_change_event_id`` to booleans before emitting any output — the raw values are
        ranking inputs only and must never appear in a digest payload.
        """
        keys = (
            "action_signal_id",
            "project_key",
            "record_key",
            "endpoint_id",
            "signal_type",
            "signal_status",
            "importance",
            "due_at_utc",
            "owner_entity_key",
            "source_change_event_id",
            "first_detected_at_utc",
            "last_seen_at_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if signal_status is not None:
            clauses.append("signal_status = ?")
            params.append(signal_status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM procore_action_signals {where} "
            "ORDER BY action_signal_id LIMIT ?",
            tuple(params),
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def upsert_project_risk_digest_item(
        self,
        *,
        risk_digest_id: str,
        project_key: str,
        risk_indicator_type: str,
        risk_source_class: str,
        summary_redacted: str,
        confidence_class: str,
        evidence_trail_id: Optional[str] = None,
        review_required: bool = False,
        stale_unknown_flags_json: Optional[str] = None,
    ) -> None:
        """Upsert a project risk-digest item (V25). Idempotent by risk_digest_id (a
        deterministic hash of project + risk_source_class + risk_indicator_type).
        summary_redacted holds compact counts / enums / category tokens / endpoint names only —
        never a raw body, document text, status payload, URL, or token. Guard CHECK columns keep
        their schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO project_risk_digest_items
                    (risk_digest_id, project_key, risk_indicator_type, risk_source_class,
                     summary_redacted, evidence_trail_id, confidence_class, review_required,
                     stale_unknown_flags_json, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(risk_digest_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    risk_indicator_type = excluded.risk_indicator_type,
                    risk_source_class = excluded.risk_source_class,
                    summary_redacted = excluded.summary_redacted,
                    evidence_trail_id = excluded.evidence_trail_id,
                    confidence_class = excluded.confidence_class,
                    review_required = excluded.review_required,
                    stale_unknown_flags_json = excluded.stale_unknown_flags_json,
                    updated_utc = excluded.updated_utc
                """,
                (
                    risk_digest_id,
                    project_key,
                    risk_indicator_type,
                    risk_source_class,
                    summary_redacted,
                    evidence_trail_id,
                    confidence_class,
                    1 if review_required else 0,
                    stale_unknown_flags_json,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def list_project_risk_digest_items(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List project risk-digest items (V25). Safe fields only; JSON decoded."""
        keys = (
            "risk_digest_id",
            "project_key",
            "risk_indicator_type",
            "risk_source_class",
            "summary_redacted",
            "evidence_trail_id",
            "confidence_class",
            "review_required",
            "stale_unknown_flags_json",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM project_risk_digest_items {where} "
            "ORDER BY risk_digest_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["stale_unknown_flags_json"] = self._load_json(record["stale_unknown_flags_json"])
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def count_project_risk_digest_items(self) -> int:
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT COUNT(*) FROM project_risk_digest_items").fetchone()
        return int(row[0]) if row else 0

    # --- Phase 07D Prompt 09 aging & exposure reporting (V25) ----------------

    def upsert_aging_exposure_report_item(
        self,
        *,
        aging_item_id: str,
        project_key: str,
        record_family: str,
        record_ref: str,
        status: str,
        threshold_band: str,
        age_days: int = 0,
        stale_flag: bool = False,
        missing_status_flag: bool = False,
        evidence_trail_id: Optional[str] = None,
        confidence_class: Optional[str] = None,
        review_required: bool = False,
    ) -> None:
        """Upsert an aging/exposure report item (V25). Idempotent by aging_item_id (a
        deterministic hash of project + record_family + record_ref, matching the UNIQUE key).
        record_ref is a local stable record key; status is a normalized bounded token — never a
        raw body, status payload, financial amount, URL, or token. Guard CHECK columns keep their
        schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO aging_exposure_report_items
                    (aging_item_id, project_key, record_family, record_ref, status, age_days,
                     threshold_band, stale_flag, missing_status_flag, evidence_trail_id,
                     confidence_class, review_required, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(aging_item_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    record_family = excluded.record_family,
                    record_ref = excluded.record_ref,
                    status = excluded.status,
                    age_days = excluded.age_days,
                    threshold_band = excluded.threshold_band,
                    stale_flag = excluded.stale_flag,
                    missing_status_flag = excluded.missing_status_flag,
                    evidence_trail_id = excluded.evidence_trail_id,
                    confidence_class = excluded.confidence_class,
                    review_required = excluded.review_required,
                    updated_utc = excluded.updated_utc
                """,
                (
                    aging_item_id,
                    project_key,
                    record_family,
                    record_ref,
                    status,
                    age_days,
                    threshold_band,
                    1 if stale_flag else 0,
                    1 if missing_status_flag else 0,
                    evidence_trail_id,
                    confidence_class,
                    1 if review_required else 0,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def list_aging_exposure_report_items(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List aging/exposure report items (V25). Safe fields only."""
        keys = (
            "aging_item_id",
            "project_key",
            "record_family",
            "record_ref",
            "status",
            "age_days",
            "threshold_band",
            "stale_flag",
            "missing_status_flag",
            "evidence_trail_id",
            "confidence_class",
            "review_required",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM aging_exposure_report_items {where} "
            "ORDER BY aging_item_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for bool_field in ("stale_flag", "missing_status_flag", "review_required"):
                record[bool_field] = bool(record[bool_field])
            results.append(record)
        return results

    def count_aging_exposure_report_items(self) -> int:
        conn = get_connection(self._db_path)
        row = conn.execute("SELECT COUNT(*) FROM aging_exposure_report_items").fetchone()
        return int(row[0]) if row else 0

    # --- Phase 07D Prompt 11 cross-source intelligence Obsidian runs (V25) ----

    def upsert_cross_source_intelligence_obsidian_run(
        self,
        *,
        obsidian_run_id: str,
        mode: str,
        output_kind: str,
        status: str,
        project_key: Optional[str] = None,
        notes_written: int = 0,
        review_required_count: int = 0,
        error_redacted: Optional[str] = None,
    ) -> None:
        """Upsert a cross-source-intelligence Obsidian run record (V25). Idempotent by
        obsidian_run_id. ``mode`` is 'dry_run' or 'apply'. Carries only counts / enums — no raw
        content. Guard CHECK columns keep their schema defaults (0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO cross_source_intelligence_obsidian_runs
                    (obsidian_run_id, project_key, mode, output_kind, notes_written,
                     review_required_count, status, error_redacted, generated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(obsidian_run_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    mode = excluded.mode,
                    output_kind = excluded.output_kind,
                    notes_written = excluded.notes_written,
                    review_required_count = excluded.review_required_count,
                    status = excluded.status,
                    error_redacted = excluded.error_redacted,
                    generated_utc = excluded.generated_utc
                """,
                (
                    obsidian_run_id,
                    project_key,
                    mode,
                    output_kind,
                    notes_written,
                    review_required_count,
                    status,
                    error_redacted,
                    _utc_now(),
                ),
            )

    def list_cross_source_intelligence_obsidian_runs(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """List cross-source-intelligence Obsidian run records (V25). Safe fields only."""
        keys = (
            "obsidian_run_id",
            "project_key",
            "mode",
            "output_kind",
            "notes_written",
            "review_required_count",
            "status",
            "error_redacted",
            "generated_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM cross_source_intelligence_obsidian_runs {where} "
            "ORDER BY generated_utc DESC, obsidian_run_id LIMIT ?",
            tuple(params),
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def count_cross_source_intelligence_obsidian_runs(self) -> int:
        conn = get_connection(self._db_path)
        row = conn.execute(
            "SELECT COUNT(*) FROM cross_source_intelligence_obsidian_runs"
        ).fetchone()
        return int(row[0]) if row else 0

    # --- Phase 07D Prompt 04 normalization source readers --------------------

    def list_procore_record_edges(
        self,
        *,
        project_key: Optional[str] = None,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        """List Procore-native record edges (V7) — safe identifier fields only (no
        metadata_json free-text). Keys are stable internal Procore identifiers / hashes."""
        keys = (
            "edge_id",
            "project_key",
            "from_record_key",
            "to_record_key",
            "to_entity_key",
            "edge_type",
            "source_endpoint_id",
            "confidence",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM procore_record_edges {where} ORDER BY edge_id LIMIT ?",
            tuple(params),
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_relationship_resolution_queue(
        self,
        *,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        """List relationship-resolution-queue edges (V20) — safe fields only (no
        evidence_redacted free-text). Carries the row's confidence_class verbatim."""
        keys = (
            "relationship_id",
            "from_canonical_record_id",
            "to_canonical_record_id",
            "from_source_system",
            "to_source_system",
            "relationship_type",
            "relationship_status",
            "confidence_class",
            "confidence",
            "review_required",
            "promotion_status",
        )
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM relationship_resolution_queue "
            "ORDER BY relationship_id LIMIT ?",
            (limit,),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def resolve_source_record_project_key(
        self, source_system: str, source_primary_key: str
    ) -> Optional[str]:
        """Look up the canonical project_key for a (source_system, source_primary_key) via
        source_system_record_map (V20). Returns None when no mapping exists (the map may be
        empty, in which case cross-family project_key alignment is a safe no-op)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT project_key FROM source_system_record_map "
            "WHERE source_system = ? AND source_primary_key = ? LIMIT 1",
            (source_system, source_primary_key),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None

    # --- Phase 07C document intelligence previews (V24) --------------------

    def upsert_document_intelligence_preview(
        self,
        *,
        preview_id: str,
        project_key: Optional[str],
        preview_kind: str,
        confidence_class: str,
        preview_redacted: Optional[str] = None,
        warnings_json: Optional[str] = None,
        document_card_id: Optional[str] = None,
        review_required: bool = False,
    ) -> None:
        """Upsert a project-level document-intelligence preview (V24). Idempotent by
        preview_id. The raw_document_text / raw_prompt / raw_response / external_writeback
        guard CHECK columns are never written here — the schema defaults (all 0) hold.
        ``preview_redacted`` must be a bounded, counts-only summary; no raw document text,
        name, path, URL, prompt, or response is accepted.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_document_intelligence_previews
                    (preview_id, project_key, document_card_id, preview_kind,
                     preview_redacted, warnings_json, confidence_class, review_required,
                     generated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(preview_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    document_card_id = excluded.document_card_id,
                    preview_kind = excluded.preview_kind,
                    preview_redacted = excluded.preview_redacted,
                    warnings_json = excluded.warnings_json,
                    confidence_class = excluded.confidence_class,
                    review_required = excluded.review_required,
                    generated_utc = excluded.generated_utc
                """,
                (
                    preview_id,
                    project_key,
                    document_card_id,
                    preview_kind,
                    preview_redacted,
                    warnings_json,
                    confidence_class,
                    1 if review_required else 0,
                    _utc_now(),
                ),
            )

    def count_document_intelligence_previews(self) -> int:
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM construction_document_intelligence_previews")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def list_document_intelligence_previews(
        self, *, project_key: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List the document-intelligence previews (V24), optionally one project."""
        conn = get_connection(self._db_path)
        sql = (
            "SELECT preview_id, project_key, preview_kind, preview_redacted, warnings_json, "
            "confidence_class, review_required, generated_utc "
            "FROM construction_document_intelligence_previews"
        )
        params: tuple[Any, ...] = ()
        if project_key is not None:
            sql += " WHERE project_key = ?"
            params = (project_key,)
        sql += " ORDER BY project_key"
        cur = conn.execute(sql, params)
        keys = (
            "preview_id",
            "project_key",
            "preview_kind",
            "preview_redacted",
            "warnings_json",
            "confidence_class",
            "review_required",
            "generated_utc",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def count_procore_live_records(self, *, project_key: str, endpoint_id: str) -> int:
        """Read-only count of canonical Procore live records for a project + endpoint.

        Thin delegate to the Procore repository (same SQLite DB) so the document
        relationship builder can gate candidates on the project actually having
        records of the aligned record type — without reaching across to raw Procore
        payloads.
        """
        from hb_assistant.store import procore_repositories

        return procore_repositories.count_procore_live_records(
            project_key=project_key, endpoint_id=endpoint_id, db_path=self._db_path
        )

    # --- Phase 07C controlled extraction eligibility (V24 card column) ------

    def update_document_card_extraction_eligibility(
        self,
        *,
        card_id: str,
        extraction_eligibility: str,
    ) -> None:
        """Set the controlled-extraction disposition on an existing document card.

        Touches ONLY the ``extraction_eligibility`` column (+ ``updated_utc``); the
        guard CHECK columns and every content/identity field are left untouched. The
        column CHECK constraint rejects any value outside the six-value enum
        (not_evaluated / metadata_only / eligible / manual_approval_required /
        blocked / skipped), so the caller must emit one of those. No download, parse,
        or raw-text persistence is involved — this records a disposition only.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                UPDATE construction_document_cards
                   SET extraction_eligibility = ?,
                       updated_utc = ?
                 WHERE card_id = ?
                """,
                (extraction_eligibility, _utc_now(), card_id),
            )

    # --- canonical processing receipts (V5) ---------------------------------

    def insert_processing_receipt(
        self,
        *,
        receipt_id: str,
        source_id: str,
        operation: str,
        status: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_processing_receipts
                    (receipt_id, source_id, operation, status, detail_json,
                     generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    source_id,
                    operation,
                    status,
                    self._dump_json(detail),
                    _utc_now(),
                ),
            )

    def list_processing_receipts(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = """
            SELECT receipt_id, source_id, operation, status, generated_at,
                   detail_json
            FROM construction_processing_receipts
            WHERE 1=1
        """
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        sql += " ORDER BY generated_at DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = ("receipt_id", "source_id", "operation", "status", "generated_at", "detail_json")
        rows = [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]
        for r in rows:
            r["detail"] = self._load_json(r.pop("detail_json"))
        return rows

    # --- graph link resolution (V16) ----------------------------------------

    def insert_link_resolution(
        self,
        *,
        resolution_id: str,
        source_id: Optional[str] = None,
        redacted_url: Optional[str] = None,
        hostname: Optional[str] = None,
        normalized_path: Optional[str] = None,
        url_fingerprint: Optional[str] = None,
        share_token_fingerprint: Optional[str] = None,
        resolution_method: Optional[str] = None,
        status: str,
        site_id: Optional[str] = None,
        drive_id: Optional[str] = None,
        drive_item_id: Optional[str] = None,
        folder_item_id: Optional[str] = None,
        parent_drive_id: Optional[str] = None,
        parent_drive_item_id: Optional[str] = None,
        list_id: Optional[str] = None,
        list_item_id: Optional[str] = None,
        web_url: Optional[str] = None,
        name: Optional[str] = None,
        item_kind: Optional[str] = None,
        error_redacted: Optional[str] = None,
    ) -> None:
        """Persist one redacted link-resolution row. The raw tokenized URL is
        never stored (the schema CHECK locks raw_tokenized_url_persisted = 0)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_graph_link_resolution
                    (resolution_id, source_id, redacted_url, hostname,
                     normalized_path, url_fingerprint, share_token_fingerprint,
                     resolution_method, status, site_id, drive_id, drive_item_id,
                     folder_item_id, parent_drive_id, parent_drive_item_id,
                     list_id, list_item_id, web_url, name, item_kind,
                     error_redacted, raw_tokenized_url_persisted, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    resolution_id,
                    source_id,
                    redacted_url,
                    hostname,
                    normalized_path,
                    url_fingerprint,
                    share_token_fingerprint,
                    resolution_method,
                    status,
                    site_id,
                    drive_id,
                    drive_item_id,
                    folder_item_id,
                    parent_drive_id,
                    parent_drive_item_id,
                    list_id,
                    list_item_id,
                    web_url,
                    name,
                    item_kind,
                    error_redacted,
                    _utc_now(),
                ),
            )

    def list_link_resolutions(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = """
            SELECT resolution_id, source_id, redacted_url, hostname,
                   normalized_path, url_fingerprint, share_token_fingerprint,
                   resolution_method, status, site_id, drive_id, drive_item_id,
                   folder_item_id, parent_drive_id, parent_drive_item_id,
                   list_id, list_item_id, web_url, name, item_kind,
                   error_redacted, raw_tokenized_url_persisted, created_utc
            FROM construction_graph_link_resolution
            WHERE 1=1
        """
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        sql += " ORDER BY created_utc DESC LIMIT ?"
        params.append(limit)
        keys = (
            "resolution_id",
            "source_id",
            "redacted_url",
            "hostname",
            "normalized_path",
            "url_fingerprint",
            "share_token_fingerprint",
            "resolution_method",
            "status",
            "site_id",
            "drive_id",
            "drive_item_id",
            "folder_item_id",
            "parent_drive_id",
            "parent_drive_item_id",
            "list_id",
            "list_item_id",
            "web_url",
            "name",
            "item_kind",
            "error_redacted",
            "raw_tokenized_url_persisted",
            "created_utc",
        )
        return [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]

    # --- canonical sync errors (V5) -----------------------------------------

    def insert_sync_error(
        self,
        *,
        source_id: Optional[str],
        operation: str,
        error_class: str,
        error_redacted: Optional[str] = None,
    ) -> int:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO construction_sync_errors
                    (source_id, operation, error_class, error_redacted,
                     occurred_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source_id, operation, error_class, error_redacted, _utc_now()),
            )
            return int(cur.lastrowid)

    def resolve_sync_error(self, error_id: int) -> bool:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                "UPDATE construction_sync_errors SET resolved_utc = ? WHERE id = ?",
                (_utc_now(), error_id),
            )
            return cur.rowcount > 0

    def list_sync_errors(
        self,
        *,
        source_id: Optional[str] = None,
        include_resolved: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        sql = """
            SELECT id, source_id, operation, error_class, error_redacted,
                   occurred_utc, resolved_utc
            FROM construction_sync_errors
            WHERE 1=1
        """
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id = ?"
            params.append(source_id)
        if not include_resolved:
            sql += " AND resolved_utc IS NULL"
        sql += " ORDER BY occurred_utc DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, tuple(params))
        keys = (
            "id",
            "source_id",
            "operation",
            "error_class",
            "error_redacted",
            "occurred_utc",
            "resolved_utc",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # --- email-intelligence deferred state singleton (V5) -------------------

    def set_email_intelligence_deferred_state(
        self,
        *,
        mail_read_all_granted: bool,
        mail_readwrite_all_granted: bool,
        mailbox_writeback_allowed: bool = False,
        persist_full_body: bool = False,
    ) -> None:
        if mailbox_writeback_allowed is not False:
            raise ValueError(
                "mailbox_writeback_allowed must be False — Phase 02 mailbox stays "
                "read-only even when Mail.ReadWrite.All is granted"
            )
        if persist_full_body is not False:
            raise ValueError(
                "persist_full_body must be False — Phase 02 never persists full mailbox bodies"
            )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_email_intelligence_deferred_state
                    (id, mail_read_all_granted, mail_readwrite_all_granted,
                     mailbox_writeback_allowed, persist_full_body, updated_utc)
                VALUES (1, ?, ?, 0, 0, ?)
                ON CONFLICT(id) DO UPDATE SET
                    mail_read_all_granted = excluded.mail_read_all_granted,
                    mail_readwrite_all_granted = excluded.mail_readwrite_all_granted,
                    updated_utc = excluded.updated_utc
                """,
                (
                    1 if mail_read_all_granted else 0,
                    1 if mail_readwrite_all_granted else 0,
                    _utc_now(),
                ),
            )

    def get_email_intelligence_deferred_state(self) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT id, mail_read_all_granted, mail_readwrite_all_granted,
                   mailbox_writeback_allowed, persist_full_body, updated_utc
            FROM construction_email_intelligence_deferred_state
            WHERE id = 1
            """,
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "id",
            "mail_read_all_granted",
            "mail_readwrite_all_granted",
            "mailbox_writeback_allowed",
            "persist_full_body",
            "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        for bool_field in (
            "mail_read_all_granted",
            "mail_readwrite_all_granted",
            "mailbox_writeback_allowed",
            "persist_full_body",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    # =====================================================================
    # V10: Phase 06 operational email intelligence — ACTIVE policy singleton +
    # mailbox source registry. Additive over V1-V9; the V5 deferred-state row is
    # left untouched as preserved historical evidence. Adapter-level guardrails
    # reject any read-only / no-mutation / no-full-body / no-source-copy /
    # no-attachment-download / metadata-only / pilot-only-backfill violation
    # before the SQL CHECKs ever fire.
    # =====================================================================

    # --- active email-intelligence policy singleton (V10) -------------------

    def set_email_intelligence_active_policy(
        self,
        *,
        policy_phase: str,
        default_lookback_days: int = 30,
        low_confidence_threshold: float = 0.75,
        ollama_enabled_for_email_intelligence: bool = True,
        mailbox_mode: str = "read_only",
        writeback_allowed: bool = False,
        mailbox_mutation_allowed: bool = False,
        full_archive_crawl: bool = False,
        source_copy_to_vault: bool = False,
        full_email_body_in_obsidian: bool = False,
        attachment_content_download_by_default: bool = False,
        metadata_only_by_default: bool = True,
        review_required_for_sensitive: bool = True,
        initial_backfill_mode: str = "pilot_projects_only",
        ollama_invalid_json_routes_to_review: bool = True,
    ) -> None:
        if mailbox_mode != "read_only":
            raise ValueError("mailbox_mode must be 'read_only' — Phase 06 mailbox stays read-only")
        for flag_name, flag_value in (
            ("writeback_allowed", writeback_allowed),
            ("mailbox_mutation_allowed", mailbox_mutation_allowed),
            ("full_archive_crawl", full_archive_crawl),
            ("source_copy_to_vault", source_copy_to_vault),
            ("full_email_body_in_obsidian", full_email_body_in_obsidian),
            ("attachment_content_download_by_default", attachment_content_download_by_default),
        ):
            if flag_value is not False:
                raise ValueError(
                    f"{flag_name} must be False — Phase 06 email intelligence is "
                    "read-only and metadata-only"
                )
        if metadata_only_by_default is not True:
            raise ValueError("metadata_only_by_default must be True in Phase 06")
        if review_required_for_sensitive is not True:
            raise ValueError("review_required_for_sensitive must be True in Phase 06")
        if initial_backfill_mode != "pilot_projects_only":
            raise ValueError(
                "initial_backfill_mode must be 'pilot_projects_only' — no full "
                "mailbox backfill in Phase 06"
            )
        if ollama_invalid_json_routes_to_review is not True:
            raise ValueError("ollama_invalid_json_routes_to_review must be True in Phase 06")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_intelligence_active_policy
                    (id, policy_phase, mailbox_mode, writeback_allowed,
                     mailbox_mutation_allowed, full_archive_crawl, source_copy_to_vault,
                     full_email_body_in_obsidian, attachment_content_download_by_default,
                     metadata_only_by_default, review_required_for_sensitive,
                     initial_backfill_mode, ollama_invalid_json_routes_to_review,
                     default_lookback_days, ollama_enabled_for_email_intelligence,
                     low_confidence_threshold, updated_utc)
                VALUES (1, ?, 'read_only', 0, 0, 0, 0, 0, 0, 1, 1,
                        'pilot_projects_only', 1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    policy_phase = excluded.policy_phase,
                    default_lookback_days = excluded.default_lookback_days,
                    ollama_enabled_for_email_intelligence = excluded.ollama_enabled_for_email_intelligence,
                    low_confidence_threshold = excluded.low_confidence_threshold,
                    updated_utc = excluded.updated_utc
                """,
                (
                    policy_phase,
                    default_lookback_days,
                    1 if ollama_enabled_for_email_intelligence else 0,
                    low_confidence_threshold,
                    _utc_now(),
                ),
            )

    def get_email_intelligence_active_policy(self) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT id, policy_phase, mailbox_mode, writeback_allowed,
                   mailbox_mutation_allowed, full_archive_crawl, source_copy_to_vault,
                   full_email_body_in_obsidian, attachment_content_download_by_default,
                   metadata_only_by_default, review_required_for_sensitive,
                   initial_backfill_mode, ollama_invalid_json_routes_to_review,
                   default_lookback_days, ollama_enabled_for_email_intelligence,
                   low_confidence_threshold, updated_utc
            FROM email_intelligence_active_policy
            WHERE id = 1
            """,
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "id",
            "policy_phase",
            "mailbox_mode",
            "writeback_allowed",
            "mailbox_mutation_allowed",
            "full_archive_crawl",
            "source_copy_to_vault",
            "full_email_body_in_obsidian",
            "attachment_content_download_by_default",
            "metadata_only_by_default",
            "review_required_for_sensitive",
            "initial_backfill_mode",
            "ollama_invalid_json_routes_to_review",
            "default_lookback_days",
            "ollama_enabled_for_email_intelligence",
            "low_confidence_threshold",
            "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        for bool_field in (
            "writeback_allowed",
            "mailbox_mutation_allowed",
            "full_archive_crawl",
            "source_copy_to_vault",
            "full_email_body_in_obsidian",
            "attachment_content_download_by_default",
            "metadata_only_by_default",
            "review_required_for_sensitive",
            "ollama_invalid_json_routes_to_review",
            "ollama_enabled_for_email_intelligence",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    # --- mailbox source registry (V10) --------------------------------------

    def upsert_email_source_location(
        self,
        *,
        source_id: str,
        mailbox_owner_hash: str,
        folder_role: str,
        folder_display_name: Optional[str] = None,
        folder_id: Optional[str] = None,
        mailbox_display_name_redacted: Optional[str] = None,
        mailbox_user_principal_name_hash: Optional[str] = None,
        source_system: str = "outlook",
        include_in_sync: bool = True,
        sync_mode: str = "bounded_lookback",
        default_lookback_days: int = 30,
        read_only: bool = True,
        mailbox_mutation_allowed: bool = False,
        full_archive_crawl_allowed: bool = False,
        source_copy_to_vault_allowed: bool = False,
        full_email_body_in_obsidian_allowed: bool = False,
    ) -> None:
        if read_only is not True:
            raise ValueError("email_source_locations.read_only must be True (no mailbox writeback)")
        for flag_name, flag_value in (
            ("mailbox_mutation_allowed", mailbox_mutation_allowed),
            ("full_archive_crawl_allowed", full_archive_crawl_allowed),
            ("source_copy_to_vault_allowed", source_copy_to_vault_allowed),
            ("full_email_body_in_obsidian_allowed", full_email_body_in_obsidian_allowed),
        ):
            if flag_value is not False:
                raise ValueError(f"email_source_locations.{flag_name} must be False")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_source_locations
                    (source_id, source_system, mailbox_owner_hash,
                     mailbox_display_name_redacted, mailbox_user_principal_name_hash,
                     folder_id, folder_display_name, folder_role, include_in_sync,
                     sync_mode, default_lookback_days, read_only,
                     mailbox_mutation_allowed, full_archive_crawl_allowed,
                     source_copy_to_vault_allowed, full_email_body_in_obsidian_allowed,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 0, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_system = excluded.source_system,
                    mailbox_owner_hash = excluded.mailbox_owner_hash,
                    mailbox_display_name_redacted = excluded.mailbox_display_name_redacted,
                    mailbox_user_principal_name_hash = excluded.mailbox_user_principal_name_hash,
                    folder_id = excluded.folder_id,
                    folder_display_name = excluded.folder_display_name,
                    folder_role = excluded.folder_role,
                    include_in_sync = excluded.include_in_sync,
                    sync_mode = excluded.sync_mode,
                    default_lookback_days = excluded.default_lookback_days,
                    updated_utc = excluded.updated_utc
                """,
                (
                    source_id,
                    source_system,
                    mailbox_owner_hash,
                    mailbox_display_name_redacted,
                    mailbox_user_principal_name_hash,
                    folder_id,
                    folder_display_name,
                    folder_role,
                    1 if include_in_sync else 0,
                    sync_mode,
                    default_lookback_days,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    @staticmethod
    def _email_source_location_keys() -> tuple[str, ...]:
        return (
            "source_id",
            "source_system",
            "mailbox_owner_hash",
            "mailbox_display_name_redacted",
            "mailbox_user_principal_name_hash",
            "folder_id",
            "folder_display_name",
            "folder_role",
            "include_in_sync",
            "sync_mode",
            "default_lookback_days",
            "read_only",
            "mailbox_mutation_allowed",
            "full_archive_crawl_allowed",
            "source_copy_to_vault_allowed",
            "full_email_body_in_obsidian_allowed",
            "created_utc",
            "updated_utc",
        )

    def get_email_source_location(self, source_id: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        keys = self._email_source_location_keys()
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_source_locations WHERE source_id = ?",
            (source_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        record = dict(zip(keys, row, strict=True))
        for bool_field in (
            "include_in_sync",
            "read_only",
            "mailbox_mutation_allowed",
            "full_archive_crawl_allowed",
            "source_copy_to_vault_allowed",
            "full_email_body_in_obsidian_allowed",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    def list_email_source_locations(
        self,
        *,
        mailbox_owner_hash: Optional[str] = None,
        include_in_sync: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        keys = self._email_source_location_keys()
        clauses: list[str] = []
        params: list[Any] = []
        if mailbox_owner_hash is not None:
            clauses.append("mailbox_owner_hash = ?")
            params.append(mailbox_owner_hash)
        if include_in_sync is not None:
            clauses.append("include_in_sync = ?")
            params.append(1 if include_in_sync else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_source_locations {where} "
            "ORDER BY folder_role, source_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for bool_field in (
                "include_in_sync",
                "read_only",
                "mailbox_mutation_allowed",
                "full_archive_crawl_allowed",
                "source_copy_to_vault_allowed",
                "full_email_body_in_obsidian_allowed",
            ):
                record[bool_field] = bool(record[bool_field])
            results.append(record)
        return results

    # --- V11 operational email intelligence (Phase 06) ----------------------
    # Read-only, metadata-only data plane the email pipeline writes to. Every
    # mutating helper raises ValueError before SQL on any no-mutation /
    # no-full-body / no-attachment-content-download flag (defense in depth
    # beneath the V11 CHECK constraints). No full email body is ever stored.

    def upsert_email_sync_state(
        self,
        *,
        source_id: str,
        folder_id: str,
        sync_mode: str,
        lookback_days: int = 30,
        last_successful_sync_utc: Optional[str] = None,
        last_attempted_sync_utc: Optional[str] = None,
        latest_received_datetime: Optional[str] = None,
        latest_sent_datetime: Optional[str] = None,
        delta_token_fingerprint: Optional[str] = None,
        delta_token_supported: bool = False,
        sync_status: str = "pending",
        error_redacted: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_sync_state
                    (source_id, folder_id, sync_mode, lookback_days,
                     last_successful_sync_utc, last_attempted_sync_utc,
                     latest_received_datetime, latest_sent_datetime,
                     delta_token_fingerprint, delta_token_supported, sync_status,
                     error_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, folder_id) DO UPDATE SET
                    sync_mode = excluded.sync_mode,
                    lookback_days = excluded.lookback_days,
                    last_successful_sync_utc = excluded.last_successful_sync_utc,
                    last_attempted_sync_utc = excluded.last_attempted_sync_utc,
                    latest_received_datetime = excluded.latest_received_datetime,
                    latest_sent_datetime = excluded.latest_sent_datetime,
                    delta_token_fingerprint = excluded.delta_token_fingerprint,
                    delta_token_supported = excluded.delta_token_supported,
                    sync_status = excluded.sync_status,
                    error_redacted = excluded.error_redacted
                """,
                (
                    source_id,
                    folder_id,
                    sync_mode,
                    lookback_days,
                    last_successful_sync_utc,
                    last_attempted_sync_utc,
                    latest_received_datetime,
                    latest_sent_datetime,
                    delta_token_fingerprint,
                    1 if delta_token_supported else 0,
                    sync_status,
                    error_redacted,
                ),
            )

    def get_email_sync_state(self, *, source_id: str, folder_id: str) -> Optional[dict[str, Any]]:
        keys = (
            "source_id",
            "folder_id",
            "sync_mode",
            "lookback_days",
            "last_successful_sync_utc",
            "last_attempted_sync_utc",
            "latest_received_datetime",
            "latest_sent_datetime",
            "delta_token_fingerprint",
            "delta_token_supported",
            "sync_status",
            "error_redacted",
        )
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_sync_state WHERE source_id = ? AND folder_id = ?",
            (source_id, folder_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        record = dict(zip(keys, row, strict=True))
        record["delta_token_supported"] = bool(record["delta_token_supported"])
        return record

    def insert_email_crawl_run(
        self,
        *,
        run_id: str,
        source_id: str,
        mode: str,
        lookback_days: int,
        started_utc: Optional[str] = None,
        status: str = "running",
        project_key: Optional[str] = None,
        project_number: Optional[str] = None,
        dry_run: bool = True,
        mailbox_mutation_attempted: bool = False,
        full_body_persisted: bool = False,
        attachment_content_downloaded: bool = False,
    ) -> None:
        self._reject_email_mutation_flags(
            mailbox_mutation_attempted=mailbox_mutation_attempted,
            full_body_persisted=full_body_persisted,
            attachment_content_downloaded=attachment_content_downloaded,
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_crawl_runs
                    (run_id, source_id, project_key, project_number, mode, dry_run,
                     lookback_days, started_utc, mailbox_mutation_attempted,
                     full_body_persisted, attachment_content_downloaded, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                """,
                (
                    run_id,
                    source_id,
                    project_key,
                    project_number,
                    mode,
                    1 if dry_run else 0,
                    lookback_days,
                    started_utc or _utc_now(),
                    status,
                ),
            )

    def complete_email_crawl_run(
        self,
        *,
        run_id: str,
        status: str,
        completed_utc: Optional[str] = None,
        folders_seen: int = 0,
        messages_seen: int = 0,
        messages_in_scope: int = 0,
        messages_indexed: int = 0,
        messages_skipped: int = 0,
        relationship_candidates_created: int = 0,
        review_items_created: int = 0,
        error_redacted: Optional[str] = None,
    ) -> bool:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                UPDATE email_crawl_runs SET
                    status = ?,
                    completed_utc = ?,
                    folders_seen = ?,
                    messages_seen = ?,
                    messages_in_scope = ?,
                    messages_indexed = ?,
                    messages_skipped = ?,
                    relationship_candidates_created = ?,
                    review_items_created = ?,
                    error_redacted = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    completed_utc or _utc_now(),
                    folders_seen,
                    messages_seen,
                    messages_in_scope,
                    messages_indexed,
                    messages_skipped,
                    relationship_candidates_created,
                    review_items_created,
                    error_redacted,
                    run_id,
                ),
            )
            return cur.rowcount > 0

    def apply_project_email_discover_batch(
        self,
        *,
        matches: list[dict[str, Any]],
        owner_hash: Optional[str],
        op_id: str,
        requested_project: Optional[str] = None,
        messages_scanned: int = 0,
        matched_messages: int = 0,
        signal_counts: Optional[dict[str, int]] = None,
        failure_injector: Callable[[str, Optional[str], Optional[str]], None] | None = None,
    ) -> int:
        """Apply a batch of project email discover matches (messages+recipients+matches + crawl/processing_receipt + sync_state) in ONE SQLite transaction.

        This fixes all-project connection lifecycle/churn (when project_key=None yields many pilot descriptors):
        caller collects instead of per-item _persist_match; batch opens 1 conn + 1 tx for all upserts + receipt.
        On write failure the batch rolls back and attempts a failed receipt (redacted diag only) + failed crawl
        in separate tx. Diagnostics are metadata-only (op, message_id_hash, project_key, exc_type).

        Mirrors apply_calendar_index_batch robustness (post-148). Re-uses SQL patterns from upsert_email_* but
        inlines executes on the shared conn (separate conn/tx methods cannot participate in outer tx).
        Guardrails preserved: no raw body, no mutation, metadata_only, CHECKs, no M365 writeback.
        """

        signal_counts = signal_counts or {}

        def _diag(
            operation: str,
            exc: BaseException,
            *,
            message_id: Optional[str] = None,
            project_key: Optional[str] = None,
        ) -> dict[str, Any]:
            return {
                "message_id_hash": hash_value(message_id) if message_id else None,
                "project_key": project_key,
                "operation": operation,
                "exception_type": type(exc).__name__,
                "message": str(exc)[:120],
            }

        def _inject(
            operation: str,
            message_id: Optional[str] = None,
            project_key: Optional[str] = None,
        ) -> None:
            if failure_injector is not None:
                failure_injector(operation, message_id, project_key)

        def _persist_failed_receipt(diagnostic: dict[str, Any]) -> None:
            conn2 = get_connection(self._db_path)
            with transaction(conn2):
                now2 = _utc_now()
                conn2.execute(
                    """
                    INSERT INTO email_processing_receipts
                        (receipt_id, run_id, message_id, project_key, operation, status,
                         detail_json, mailbox_mutation_attempted, full_body_persisted,
                         attachment_content_downloaded, generated_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                    """,
                    (
                        f"{op_id}:discover:failed",
                        op_id,
                        None,
                        requested_project,
                        "project_discovery",
                        "failed",
                        self._dump_json(
                            {
                                "diagnostic": diagnostic,
                                "messages_scanned": messages_scanned,
                                "matched_messages": matched_messages,
                                "signal_counts": signal_counts,
                            }
                        ),
                        now2,
                    ),
                )
                # best-effort failed crawl markers for sources involved (redacted)
                sources = diagnostic.get("_sources") or []
                for sid in sources:
                    crid = f"{op_id}:{sid}:failed"
                    conn2.execute(
                        """
                        INSERT INTO email_crawl_runs
                            (run_id, source_id, project_key, project_number, mode, dry_run,
                             lookback_days, started_utc, completed_utc, folders_seen,
                             messages_seen, messages_in_scope, messages_indexed,
                             messages_skipped, relationship_candidates_created,
                             review_items_created, mailbox_mutation_attempted,
                             full_body_persisted, attachment_content_downloaded, status,
                             error_redacted)
                        VALUES (?, ?, ?, ?, 'project_discover', 0, 0, ?, ?, 0, ?, ?, 0, 0, 0, 0, 0, 0, 0, 'failed', ?)
                        """,
                        (
                            crid,
                            sid,
                            requested_project,
                            None,
                            now2,
                            now2,
                            messages_scanned,
                            messages_scanned,
                            f"{diagnostic.get('operation')}:{diagnostic.get('exception_type')}",
                        ),
                    )

        # precompute for failed path (visible outside try)
        sources_seen: list[str] = sorted(
            {m.get("source_id") for m in matches if m.get("source_id")}
        )

        self._reject_email_mutation_flags(
            mailbox_mutation_attempted=False,
            full_body_persisted=False,
            attachment_content_downloaded=False,
        )

        conn = get_connection(self._db_path)
        persisted = 0
        operation = "email_discover_batch"
        mid: Optional[str] = None
        pk: Optional[str] = None
        try:
            with transaction(conn):
                now = _utc_now()
                touched_folders: set[tuple[str, str]] = set()
                for item in matches:
                    mid = item.get("message_id")
                    pk = item.get("project_key")
                    fields = item.get("fields") or {}
                    recips = item.get("recipients") or []
                    sigs = item.get("signals") or []
                    sid = item.get("source_id")
                    fid = item.get("folder_id")
                    if sid and fid:
                        touched_folders.add((sid, fid))

                    # guards (same as upsert_email_message); use .get( , default) because normalize_message
                    # does not emit the full/mutation keys (relies on upsert defaults); absent -> treat as False.
                    if fields.get("full_body_persisted", False) is not False:
                        raise ValueError(
                            "email_messages.full_body_persisted must be False — Phase 06 "
                            "never persists full email bodies"
                        )
                    if fields.get("mailbox_mutation_allowed", False) is not False:
                        raise ValueError(
                            "email_messages.mailbox_mutation_allowed must be False — Phase 06 "
                            "mailbox stays read-only"
                        )
                    if fields.get("extraction_policy", "metadata_only") != "metadata_only":
                        raise ValueError(
                            "email_messages.extraction_policy must be 'metadata_only' in Phase 06"
                        )

                    operation = "email_message_upsert"
                    _inject(operation, mid, pk)
                    conn.execute(
                        """
                        INSERT INTO email_messages
                            (message_id, internet_message_id, conversation_id, thread_key,
                             source_id, folder_id, folder_display_name, subject_redacted,
                             subject_hash, sender_name_redacted, sender_address_hash,
                             sender_domain, to_recipient_count, cc_recipient_count,
                             bcc_recipient_count, received_datetime, sent_datetime,
                             last_modified_datetime, has_attachments, importance,
                             categories_metadata_json, sensitivity_metadata, web_link,
                             body_preview_hash, body_preview_excerpt_redacted, body_checked,
                             body_mention_detected, project_number_detected,
                             project_match_confidence, sensitivity_classification,
                             extraction_policy, review_required, full_body_persisted,
                             mailbox_mutation_allowed, indexed_utc, updated_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'metadata_only', ?, 0, 0, ?, ?)
                        ON CONFLICT(message_id) DO UPDATE SET
                            internet_message_id = excluded.internet_message_id,
                            conversation_id = excluded.conversation_id,
                            thread_key = excluded.thread_key,
                            source_id = excluded.source_id,
                            folder_id = excluded.folder_id,
                            folder_display_name = excluded.folder_display_name,
                            subject_redacted = excluded.subject_redacted,
                            subject_hash = excluded.subject_hash,
                            sender_name_redacted = excluded.sender_name_redacted,
                            sender_address_hash = excluded.sender_address_hash,
                            sender_domain = excluded.sender_domain,
                            to_recipient_count = excluded.to_recipient_count,
                            cc_recipient_count = excluded.cc_recipient_count,
                            bcc_recipient_count = excluded.bcc_recipient_count,
                            received_datetime = excluded.received_datetime,
                            sent_datetime = excluded.sent_datetime,
                            last_modified_datetime = excluded.last_modified_datetime,
                            has_attachments = excluded.has_attachments,
                            importance = excluded.importance,
                            categories_metadata_json = excluded.categories_metadata_json,
                            sensitivity_metadata = excluded.sensitivity_metadata,
                            web_link = excluded.web_link,
                            body_preview_hash = excluded.body_preview_hash,
                            body_preview_excerpt_redacted = excluded.body_preview_excerpt_redacted,
                            body_checked = excluded.body_checked,
                            body_mention_detected = excluded.body_mention_detected,
                            project_number_detected = excluded.project_number_detected,
                            project_match_confidence = excluded.project_match_confidence,
                            sensitivity_classification = excluded.sensitivity_classification,
                            review_required = excluded.review_required,
                            updated_utc = excluded.updated_utc
                        """,
                        (
                            fields.get("message_id") or mid,
                            fields.get("internet_message_id"),
                            fields.get("conversation_id"),
                            fields.get("thread_key"),
                            fields.get("source_id"),
                            fields.get("folder_id"),
                            fields.get("folder_display_name"),
                            fields.get("subject_redacted"),
                            fields.get("subject_hash"),
                            fields.get("sender_name_redacted"),
                            fields.get("sender_address_hash"),
                            fields.get("sender_domain"),
                            fields.get("to_recipient_count", 0),
                            fields.get("cc_recipient_count", 0),
                            fields.get("bcc_recipient_count", 0),
                            fields.get("received_datetime"),
                            fields.get("sent_datetime"),
                            fields.get("last_modified_datetime"),
                            1 if fields.get("has_attachments") else 0,
                            fields.get("importance"),
                            self._dump_json(fields.get("categories_metadata")),
                            fields.get("sensitivity_metadata"),
                            fields.get("web_link"),
                            fields.get("body_preview_hash"),
                            fields.get("body_preview_excerpt_redacted"),
                            1 if fields.get("body_checked") else 0,
                            1 if fields.get("body_mention_detected") else 0,
                            fields.get("project_number_detected"),
                            fields.get("project_match_confidence"),
                            fields.get("sensitivity_classification"),
                            1 if fields.get("review_required") else 0,
                            now,
                            now,
                        ),
                    )

                    for r in recips:
                        operation = "email_recipient_add"
                        _inject(operation, mid, pk)
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO email_message_recipients
                                (message_id, recipient_role, display_name_redacted, address_hash,
                                 domain, is_bobby, known_project_participant, created_utc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                mid,
                                r.get("recipient_role"),
                                r.get("display_name_redacted"),
                                r.get("address_hash"),
                                r.get("domain"),
                                1 if r.get("is_bobby") else 0,
                                1 if r.get("known_project_participant") else 0,
                                now,
                            ),
                        )

                    for s in sigs:
                        operation = "email_project_match_upsert"
                        _inject(operation, mid, pk)
                        conn.execute(
                            """
                            INSERT INTO email_project_matches
                                (match_id, message_id, project_key, project_number,
                                 project_name_normalized, match_signal, match_value_hash,
                                 confidence, review_required, evidence_redacted, created_utc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(message_id, project_key, match_signal) DO UPDATE SET
                                project_number = excluded.project_number,
                                project_name_normalized = excluded.project_name_normalized,
                                match_value_hash = excluded.match_value_hash,
                                confidence = excluded.confidence,
                                review_required = excluded.review_required,
                                evidence_redacted = excluded.evidence_redacted
                            """,
                            (
                                f"{mid}:{pk}:{s.get('name')}",
                                mid,
                                pk,
                                item.get("project_number"),
                                item.get("project_name_normalized"),
                                s.get("name"),
                                s.get("match_value_hash"),
                                s.get("confidence"),
                                1 if s.get("review_required") else 0,
                                s.get("evidence_redacted"),
                                now,
                            ),
                        )

                    persisted += 1

                # sync_state last_attempted + status for touched folders (in same tx)
                for sid, fid in touched_folders:
                    operation = "email_sync_state_upsert"
                    _inject(operation, None, pk)
                    conn.execute(
                        """
                        INSERT INTO email_sync_state
                            (source_id, folder_id, sync_mode, lookback_days,
                             last_successful_sync_utc, last_attempted_sync_utc,
                             latest_received_datetime, latest_sent_datetime,
                             delta_token_fingerprint, delta_token_supported, sync_status,
                             error_redacted)
                        VALUES (?, ?, 'project_discover', 30, NULL, ?, NULL, NULL, NULL, 0, 'completed', NULL)
                        ON CONFLICT(source_id, folder_id) DO UPDATE SET
                            last_attempted_sync_utc = excluded.last_attempted_sync_utc,
                            sync_status = excluded.sync_status
                        """,
                        (sid, fid, now),
                    )

                # crawl run markers per source involved (mode=project_discover for audit trail)
                for sid in sources_seen:
                    crun_id = f"{op_id}:{sid}"
                    operation = "email_crawl_run_insert"
                    _inject(operation)
                    conn.execute(
                        """
                        INSERT INTO email_crawl_runs
                            (run_id, source_id, project_key, project_number, mode, dry_run,
                             lookback_days, started_utc, completed_utc, folders_seen,
                             messages_seen, messages_in_scope, messages_indexed,
                             messages_skipped, relationship_candidates_created,
                             review_items_created, mailbox_mutation_attempted,
                             full_body_persisted, attachment_content_downloaded, status,
                             error_redacted)
                        VALUES (?, ?, ?, ?, 'project_discover', 0, 0, ?, ?, 0, ?, ?, 0, 0, 0, 0, 0, 0, 0, 'completed', NULL)
                        """,
                        (
                            crun_id,
                            sid,
                            requested_project,
                            None,
                            now,
                            now,
                            messages_scanned,
                            messages_scanned,
                        ),
                    )

                # processing receipt (ok) inside the tx (safe even if 0 matches)
                operation = "email_processing_receipt"
                _inject(operation)
                conn.execute(
                    """
                    INSERT INTO email_processing_receipts
                        (receipt_id, run_id, message_id, project_key, operation, status,
                         detail_json, mailbox_mutation_attempted, full_body_persisted,
                         attachment_content_downloaded, generated_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                    """,
                    (
                        f"{op_id}:discover",
                        op_id,
                        None,
                        requested_project,
                        "project_discovery",
                        "ok",
                        self._dump_json(
                            {
                                "messages_scanned": messages_scanned,
                                "matched_messages": matched_messages,
                                "signal_counts": signal_counts,
                            }
                        ),
                        now,
                    ),
                )
        except Exception as exc:
            diagnostic = _diag(
                operation,
                exc,
                message_id=mid,
                project_key=pk,
            )
            diagnostic["_sources"] = sources_seen
            with contextlib.suppress(Exception):
                _persist_failed_receipt(diagnostic)
            raise EmailDiscoverBatchApplyError(diagnostic) from exc
        return persisted

    @staticmethod
    def _email_message_keys() -> tuple[str, ...]:
        return (
            "message_id",
            "internet_message_id",
            "conversation_id",
            "thread_key",
            "source_id",
            "folder_id",
            "folder_display_name",
            "subject_redacted",
            "subject_hash",
            "sender_name_redacted",
            "sender_address_hash",
            "sender_domain",
            "to_recipient_count",
            "cc_recipient_count",
            "bcc_recipient_count",
            "received_datetime",
            "sent_datetime",
            "last_modified_datetime",
            "has_attachments",
            "importance",
            "categories_metadata_json",
            "sensitivity_metadata",
            "web_link",
            "body_preview_hash",
            "body_preview_excerpt_redacted",
            "body_checked",
            "body_mention_detected",
            "project_number_detected",
            "project_match_confidence",
            "sensitivity_classification",
            "extraction_policy",
            "review_required",
            "full_body_persisted",
            "mailbox_mutation_allowed",
            "indexed_utc",
            "updated_utc",
        )

    def upsert_email_message(
        self,
        *,
        message_id: str,
        thread_key: str,
        source_id: str,
        internet_message_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        folder_display_name: Optional[str] = None,
        subject_redacted: Optional[str] = None,
        subject_hash: Optional[str] = None,
        sender_name_redacted: Optional[str] = None,
        sender_address_hash: Optional[str] = None,
        sender_domain: Optional[str] = None,
        to_recipient_count: int = 0,
        cc_recipient_count: int = 0,
        bcc_recipient_count: int = 0,
        received_datetime: Optional[str] = None,
        sent_datetime: Optional[str] = None,
        last_modified_datetime: Optional[str] = None,
        has_attachments: bool = False,
        importance: Optional[str] = None,
        categories_metadata: Optional[list[Any]] = None,
        sensitivity_metadata: Optional[str] = None,
        web_link: Optional[str] = None,
        body_preview_hash: Optional[str] = None,
        body_preview_excerpt_redacted: Optional[str] = None,
        body_checked: bool = False,
        body_mention_detected: bool = False,
        project_number_detected: Optional[str] = None,
        project_match_confidence: Optional[float] = None,
        sensitivity_classification: Optional[str] = None,
        extraction_policy: str = "metadata_only",
        review_required: bool = False,
        full_body_persisted: bool = False,
        mailbox_mutation_allowed: bool = False,
    ) -> None:
        if full_body_persisted is not False:
            raise ValueError(
                "email_messages.full_body_persisted must be False — Phase 06 "
                "never persists full email bodies"
            )
        if mailbox_mutation_allowed is not False:
            raise ValueError(
                "email_messages.mailbox_mutation_allowed must be False — Phase 06 "
                "mailbox stays read-only"
            )
        if extraction_policy != "metadata_only":
            raise ValueError("email_messages.extraction_policy must be 'metadata_only' in Phase 06")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_messages
                    (message_id, internet_message_id, conversation_id, thread_key,
                     source_id, folder_id, folder_display_name, subject_redacted,
                     subject_hash, sender_name_redacted, sender_address_hash,
                     sender_domain, to_recipient_count, cc_recipient_count,
                     bcc_recipient_count, received_datetime, sent_datetime,
                     last_modified_datetime, has_attachments, importance,
                     categories_metadata_json, sensitivity_metadata, web_link,
                     body_preview_hash, body_preview_excerpt_redacted, body_checked,
                     body_mention_detected, project_number_detected,
                     project_match_confidence, sensitivity_classification,
                     extraction_policy, review_required, full_body_persisted,
                     mailbox_mutation_allowed, indexed_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'metadata_only', ?, 0, 0, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    internet_message_id = excluded.internet_message_id,
                    conversation_id = excluded.conversation_id,
                    thread_key = excluded.thread_key,
                    source_id = excluded.source_id,
                    folder_id = excluded.folder_id,
                    folder_display_name = excluded.folder_display_name,
                    subject_redacted = excluded.subject_redacted,
                    subject_hash = excluded.subject_hash,
                    sender_name_redacted = excluded.sender_name_redacted,
                    sender_address_hash = excluded.sender_address_hash,
                    sender_domain = excluded.sender_domain,
                    to_recipient_count = excluded.to_recipient_count,
                    cc_recipient_count = excluded.cc_recipient_count,
                    bcc_recipient_count = excluded.bcc_recipient_count,
                    received_datetime = excluded.received_datetime,
                    sent_datetime = excluded.sent_datetime,
                    last_modified_datetime = excluded.last_modified_datetime,
                    has_attachments = excluded.has_attachments,
                    importance = excluded.importance,
                    categories_metadata_json = excluded.categories_metadata_json,
                    sensitivity_metadata = excluded.sensitivity_metadata,
                    web_link = excluded.web_link,
                    body_preview_hash = excluded.body_preview_hash,
                    body_preview_excerpt_redacted = excluded.body_preview_excerpt_redacted,
                    body_checked = excluded.body_checked,
                    body_mention_detected = excluded.body_mention_detected,
                    project_number_detected = excluded.project_number_detected,
                    project_match_confidence = excluded.project_match_confidence,
                    sensitivity_classification = excluded.sensitivity_classification,
                    review_required = excluded.review_required,
                    updated_utc = excluded.updated_utc
                """,
                (
                    message_id,
                    internet_message_id,
                    conversation_id,
                    thread_key,
                    source_id,
                    folder_id,
                    folder_display_name,
                    subject_redacted,
                    subject_hash,
                    sender_name_redacted,
                    sender_address_hash,
                    sender_domain,
                    to_recipient_count,
                    cc_recipient_count,
                    bcc_recipient_count,
                    received_datetime,
                    sent_datetime,
                    last_modified_datetime,
                    1 if has_attachments else 0,
                    importance,
                    self._dump_json(categories_metadata),
                    sensitivity_metadata,
                    web_link,
                    body_preview_hash,
                    body_preview_excerpt_redacted,
                    1 if body_checked else 0,
                    1 if body_mention_detected else 0,
                    project_number_detected,
                    project_match_confidence,
                    sensitivity_classification,
                    1 if review_required else 0,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def get_email_message(self, message_id: str) -> Optional[dict[str, Any]]:
        keys = self._email_message_keys()
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_messages WHERE message_id = ?",
            (message_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._email_message_row_to_record(keys, row)

    def list_email_messages(
        self,
        *,
        project_number_detected: Optional[str] = None,
        review_required: Optional[bool] = None,
        thread_key: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        keys = self._email_message_keys()
        clauses: list[str] = []
        params: list[Any] = []
        if project_number_detected is not None:
            clauses.append("project_number_detected = ?")
            params.append(project_number_detected)
        if review_required is not None:
            clauses.append("review_required = ?")
            params.append(1 if review_required else 0)
        if thread_key is not None:
            clauses.append("thread_key = ?")
            params.append(thread_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_messages {where} "
            "ORDER BY received_datetime DESC, message_id LIMIT ?",
            tuple(params),
        )
        return [self._email_message_row_to_record(keys, row) for row in cur.fetchall()]

    @staticmethod
    def _email_message_row_to_record(keys: tuple[str, ...], row: Any) -> dict[str, Any]:
        record = dict(zip(keys, row, strict=True))
        record["categories_metadata"] = ConstructionStore._load_json(
            record.pop("categories_metadata_json")
        )
        for bool_field in (
            "has_attachments",
            "body_checked",
            "body_mention_detected",
            "review_required",
            "full_body_persisted",
            "mailbox_mutation_allowed",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    # --- advisory email model classifications (V14) -------------------------

    def upsert_email_model_classification(
        self,
        *,
        classification_id: str,
        message_id: str,
        model_name: str,
        schema_version: str,
        classification_status: str,
        conversation_id: Optional[str] = None,
        project_key: Optional[str] = None,
        model_version: Optional[str] = None,
        project_match_confidence: Optional[float] = None,
        topic_labels: Optional[list[str]] = None,
        relationship_candidates: Optional[list[dict[str, Any]]] = None,
        risk_flags: Optional[list[str]] = None,
        sensitive_categories: Optional[list[str]] = None,
        review_required: bool = False,
        review_reasons: Optional[list[str]] = None,
    ) -> None:
        """Upsert an advisory email model classification (V14). Idempotent by
        (message_id, model_name, schema_version). Model output is advisory-only:
        the advisory_only / plaintext_body_persisted / raw_prompt_persisted /
        raw_response_persisted CHECK columns are never written here — schema
        defaults (1/0/0/0) hold them. No raw body, prompt, or response is
        accepted; only labels/flags/hashes round-trip through the *_json
        columns."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_model_classifications
                    (classification_id, message_id, conversation_id, project_key,
                     model_name, model_version, schema_version, classification_status,
                     project_match_confidence, topic_labels_json,
                     relationship_candidates_json, risk_flags_json,
                     sensitive_categories_json, review_required, review_reasons_json,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, model_name, schema_version) DO UPDATE SET
                    classification_id = excluded.classification_id,
                    conversation_id = excluded.conversation_id,
                    project_key = excluded.project_key,
                    model_version = excluded.model_version,
                    classification_status = excluded.classification_status,
                    project_match_confidence = excluded.project_match_confidence,
                    topic_labels_json = excluded.topic_labels_json,
                    relationship_candidates_json = excluded.relationship_candidates_json,
                    risk_flags_json = excluded.risk_flags_json,
                    sensitive_categories_json = excluded.sensitive_categories_json,
                    review_required = excluded.review_required,
                    review_reasons_json = excluded.review_reasons_json,
                    updated_utc = excluded.updated_utc
                """,
                (
                    classification_id,
                    message_id,
                    conversation_id,
                    project_key,
                    model_name,
                    model_version,
                    schema_version,
                    classification_status,
                    project_match_confidence,
                    self._dump_json(topic_labels),
                    self._dump_json(relationship_candidates),
                    self._dump_json(risk_flags),
                    self._dump_json(sensitive_categories),
                    1 if review_required else 0,
                    self._dump_json(review_reasons),
                    _utc_now(),
                    _utc_now(),
                ),
            )

    _EMAIL_MODEL_CLASSIFICATION_KEYS: tuple[str, ...] = (
        "classification_id",
        "message_id",
        "conversation_id",
        "project_key",
        "model_name",
        "model_version",
        "schema_version",
        "classification_status",
        "project_match_confidence",
        "topic_labels_json",
        "relationship_candidates_json",
        "risk_flags_json",
        "sensitive_categories_json",
        "review_required",
        "review_reasons_json",
        "advisory_only",
        "plaintext_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "created_utc",
        "updated_utc",
    )

    @staticmethod
    def _email_model_classification_row_to_record(row: Any) -> dict[str, Any]:
        keys = ConstructionStore._EMAIL_MODEL_CLASSIFICATION_KEYS
        record = dict(zip(keys, row, strict=True))
        for json_field, out_field in (
            ("topic_labels_json", "topic_labels"),
            ("relationship_candidates_json", "relationship_candidates"),
            ("risk_flags_json", "risk_flags"),
            ("sensitive_categories_json", "sensitive_categories"),
            ("review_reasons_json", "review_reasons"),
        ):
            record[out_field] = ConstructionStore._load_json(record.pop(json_field))
        for bool_field in (
            "review_required",
            "advisory_only",
            "plaintext_body_persisted",
            "raw_prompt_persisted",
            "raw_response_persisted",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    def get_email_model_classification(
        self,
        *,
        message_id: str,
        model_name: str,
        schema_version: str,
    ) -> Optional[dict[str, Any]]:
        """Fetch a single advisory email model classification by its unique key
        (message_id, model_name, schema_version). JSON columns are decoded to
        lists/dicts and the advisory/guard flags returned as booleans. Returns
        None if absent."""
        keys = self._EMAIL_MODEL_CLASSIFICATION_KEYS
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_model_classifications "
            "WHERE message_id = ? AND model_name = ? AND schema_version = ?",
            (message_id, model_name, schema_version),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._email_model_classification_row_to_record(row)

    def list_email_model_classifications(
        self,
        *,
        project_key: Optional[str] = None,
        message_id: Optional[str] = None,
        review_required: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List advisory email model classifications (V14), newest first, with
        optional project/message/review filters. Same decoding as
        get_email_model_classification."""
        keys = self._EMAIL_MODEL_CLASSIFICATION_KEYS
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if message_id is not None:
            clauses.append("message_id = ?")
            params.append(message_id)
        if review_required is not None:
            clauses.append("review_required = ?")
            params.append(1 if review_required else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_model_classifications {where} "
            "ORDER BY created_utc DESC, classification_id LIMIT ?",
            tuple(params),
        )
        return [self._email_model_classification_row_to_record(row) for row in cur.fetchall()]

    def add_email_message_recipient(
        self,
        *,
        message_id: str,
        recipient_role: str,
        address_hash: Optional[str] = None,
        display_name_redacted: Optional[str] = None,
        domain: Optional[str] = None,
        is_bobby: bool = False,
        known_project_participant: bool = False,
    ) -> bool:
        """Idempotent insert keyed by (message_id, recipient_role, address_hash).

        Returns True if a new recipient row was inserted, False if it already
        existed (INSERT OR IGNORE on the UNIQUE constraint). Recipient identity
        is fully determined by the hashed address + role, so re-seeing the same
        recipient is a no-op rather than an update.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO email_message_recipients
                    (message_id, recipient_role, display_name_redacted, address_hash,
                     domain, is_bobby, known_project_participant, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    recipient_role,
                    display_name_redacted,
                    address_hash,
                    domain,
                    1 if is_bobby else 0,
                    1 if known_project_participant else 0,
                    _utc_now(),
                ),
            )
            return cur.rowcount > 0

    def list_email_message_recipients(self, message_id: str) -> list[dict[str, Any]]:
        keys = (
            "id",
            "message_id",
            "recipient_role",
            "display_name_redacted",
            "address_hash",
            "domain",
            "is_bobby",
            "known_project_participant",
            "created_utc",
        )
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_message_recipients "
            "WHERE message_id = ? ORDER BY recipient_role, id",
            (message_id,),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["is_bobby"] = bool(record["is_bobby"])
            record["known_project_participant"] = bool(record["known_project_participant"])
            results.append(record)
        return results

    def upsert_email_message_attachment(
        self,
        *,
        attachment_key: str,
        message_id: str,
        attachment_id: Optional[str] = None,
        name_redacted: Optional[str] = None,
        name_hash: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        is_inline: bool = False,
        sharepoint_or_onedrive_link_detected: bool = False,
        linked_drive_item_id: Optional[str] = None,
        sensitivity_hint: Optional[str] = None,
        review_required: bool = False,
        metadata_only: bool = True,
        content_downloaded: bool = False,
    ) -> None:
        if metadata_only is not True:
            raise ValueError("email_message_attachments.metadata_only must be True in Phase 06")
        if content_downloaded is not False:
            raise ValueError(
                "email_message_attachments.content_downloaded must be False — "
                "Phase 06 never downloads attachment content by default"
            )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_message_attachments
                    (attachment_key, message_id, attachment_id, name_redacted,
                     name_hash, content_type, size_bytes, is_inline, metadata_only,
                     content_downloaded, sharepoint_or_onedrive_link_detected,
                     linked_drive_item_id, sensitivity_hint, review_required,
                     created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(attachment_key) DO UPDATE SET
                    message_id = excluded.message_id,
                    attachment_id = excluded.attachment_id,
                    name_redacted = excluded.name_redacted,
                    name_hash = excluded.name_hash,
                    content_type = excluded.content_type,
                    size_bytes = excluded.size_bytes,
                    is_inline = excluded.is_inline,
                    sharepoint_or_onedrive_link_detected =
                        excluded.sharepoint_or_onedrive_link_detected,
                    linked_drive_item_id = excluded.linked_drive_item_id,
                    sensitivity_hint = excluded.sensitivity_hint,
                    review_required = excluded.review_required
                """,
                (
                    attachment_key,
                    message_id,
                    attachment_id,
                    name_redacted,
                    name_hash,
                    content_type,
                    size_bytes,
                    1 if is_inline else 0,
                    1 if sharepoint_or_onedrive_link_detected else 0,
                    linked_drive_item_id,
                    sensitivity_hint,
                    1 if review_required else 0,
                    _utc_now(),
                ),
            )

    def upsert_email_project_match(
        self,
        *,
        match_id: str,
        message_id: str,
        match_signal: str,
        confidence: float,
        project_key: Optional[str] = None,
        project_number: Optional[str] = None,
        project_name_normalized: Optional[str] = None,
        match_value_hash: Optional[str] = None,
        review_required: bool = False,
        evidence_redacted: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_project_matches
                    (match_id, message_id, project_key, project_number,
                     project_name_normalized, match_signal, match_value_hash,
                     confidence, review_required, evidence_redacted, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, project_key, match_signal) DO UPDATE SET
                    project_number = excluded.project_number,
                    project_name_normalized = excluded.project_name_normalized,
                    match_value_hash = excluded.match_value_hash,
                    confidence = excluded.confidence,
                    review_required = excluded.review_required,
                    evidence_redacted = excluded.evidence_redacted
                """,
                (
                    match_id,
                    message_id,
                    project_key,
                    project_number,
                    project_name_normalized,
                    match_signal,
                    match_value_hash,
                    confidence,
                    1 if review_required else 0,
                    evidence_redacted,
                    _utc_now(),
                ),
            )

    def upsert_email_relationship_candidate(
        self,
        *,
        candidate_id: str,
        message_id: str,
        candidate_type: str,
        match_signal: str,
        confidence: float,
        project_key: Optional[str] = None,
        target_source_system: Optional[str] = None,
        target_table: Optional[str] = None,
        target_key: Optional[str] = None,
        review_required: bool = False,
        evidence_redacted: Optional[str] = None,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_relationship_candidates
                    (candidate_id, message_id, project_key, candidate_type,
                     target_source_system, target_table, target_key, match_signal,
                     confidence, evidence_redacted, review_required, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, candidate_type, target_table, target_key,
                            match_signal) DO UPDATE SET
                    project_key = excluded.project_key,
                    target_source_system = excluded.target_source_system,
                    confidence = excluded.confidence,
                    evidence_redacted = excluded.evidence_redacted,
                    review_required = excluded.review_required
                """,
                (
                    candidate_id,
                    message_id,
                    project_key,
                    candidate_type,
                    target_source_system,
                    target_table,
                    target_key,
                    match_signal,
                    confidence,
                    evidence_redacted,
                    1 if review_required else 0,
                    _utc_now(),
                ),
            )

    def list_email_project_matches(
        self,
        *,
        project_key: Optional[str] = None,
        message_id: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        keys = (
            "match_id",
            "message_id",
            "project_key",
            "project_number",
            "project_name_normalized",
            "match_signal",
            "match_value_hash",
            "confidence",
            "review_required",
            "evidence_redacted",
            "created_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if message_id is not None:
            clauses.append("message_id = ?")
            params.append(message_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_project_matches {where} "
            "ORDER BY confidence DESC, match_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def list_email_relationship_candidates(
        self,
        *,
        project_key: Optional[str] = None,
        message_id: Optional[str] = None,
        candidate_type: Optional[str] = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        keys = (
            "candidate_id",
            "message_id",
            "project_key",
            "candidate_type",
            "target_source_system",
            "target_table",
            "target_key",
            "match_signal",
            "confidence",
            "evidence_redacted",
            "review_required",
            "created_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if message_id is not None:
            clauses.append("message_id = ?")
            params.append(message_id)
        if candidate_type is not None:
            clauses.append("candidate_type = ?")
            params.append(candidate_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_relationship_candidates {where} "
            "ORDER BY candidate_type, candidate_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["review_required"] = bool(record["review_required"])
            results.append(record)
        return results

    def upsert_email_thread_summary(
        self,
        *,
        thread_key: str,
        project_key: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message_count: int = 0,
        first_message_datetime: Optional[str] = None,
        last_message_datetime: Optional[str] = None,
        participants_hash: Optional[list[Any]] = None,
        summary_redacted: Optional[str] = None,
        summary_policy: str = "metadata_and_preview_only",
        review_required: bool = False,
        model_used: Optional[str] = None,
        model_output_validated: bool = False,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_thread_summaries
                    (thread_key, project_key, conversation_id, message_count,
                     first_message_datetime, last_message_datetime,
                     participants_hash_json, summary_redacted, summary_policy,
                     review_required, model_used, model_output_validated,
                     generated_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_key) DO UPDATE SET
                    project_key = excluded.project_key,
                    conversation_id = excluded.conversation_id,
                    message_count = excluded.message_count,
                    first_message_datetime = excluded.first_message_datetime,
                    last_message_datetime = excluded.last_message_datetime,
                    participants_hash_json = excluded.participants_hash_json,
                    summary_redacted = excluded.summary_redacted,
                    summary_policy = excluded.summary_policy,
                    review_required = excluded.review_required,
                    model_used = excluded.model_used,
                    model_output_validated = excluded.model_output_validated,
                    updated_utc = excluded.updated_utc
                """,
                (
                    thread_key,
                    project_key,
                    conversation_id,
                    message_count,
                    first_message_datetime,
                    last_message_datetime,
                    self._dump_json(participants_hash),
                    summary_redacted,
                    summary_policy,
                    1 if review_required else 0,
                    model_used,
                    1 if model_output_validated else 0,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    _EMAIL_THREAD_SUMMARY_KEYS: tuple[str, ...] = (
        "thread_key",
        "project_key",
        "conversation_id",
        "message_count",
        "first_message_datetime",
        "last_message_datetime",
        "participants_hash_json",
        "summary_redacted",
        "summary_policy",
        "review_required",
        "model_used",
        "model_output_validated",
        "generated_utc",
        "updated_utc",
    )

    @staticmethod
    def _email_thread_summary_row_to_record(row: Any) -> dict[str, Any]:
        keys = ConstructionStore._EMAIL_THREAD_SUMMARY_KEYS
        record = dict(zip(keys, row, strict=True))
        record["participants_hash"] = ConstructionStore._load_json(
            record.pop("participants_hash_json")
        )
        for bool_field in ("review_required", "model_output_validated"):
            record[bool_field] = bool(record[bool_field])
        return record

    def get_email_thread_summary(self, thread_key: str) -> Optional[dict[str, Any]]:
        """Fetch a single email thread summary by thread_key; None if absent.
        JSON columns are decoded and bool flags returned as booleans."""
        keys = self._EMAIL_THREAD_SUMMARY_KEYS
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_thread_summaries WHERE thread_key = ?",
            (thread_key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._email_thread_summary_row_to_record(row)

    def list_email_thread_summaries(
        self,
        *,
        project_key: Optional[str] = None,
        review_required: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List email thread summaries (newest first) with optional filters."""
        keys = self._EMAIL_THREAD_SUMMARY_KEYS
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if review_required is not None:
            clauses.append("review_required = ?")
            params.append(1 if review_required else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_thread_summaries {where} "
            "ORDER BY last_message_datetime DESC, thread_key LIMIT ?",
            tuple(params),
        )
        return [self._email_thread_summary_row_to_record(row) for row in cur.fetchall()]

    def insert_email_thread_summary_materialization_run(
        self,
        *,
        run_id: str,
        mode: str,
        project_key: Optional[str] = None,
        started_at_utc: Optional[str] = None,
        status: str = "running",
    ) -> None:
        """Open a Phase 07B thread-summary materialization run receipt (V23). The
        raw_body / raw_prompt / raw_response / external_writeback CHECK columns stay
        at their 0 default."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_thread_summary_materialization_runs
                    (run_id, mode, started_at_utc, project_key, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, mode, started_at_utc or _utc_now(), project_key, status),
            )

    def complete_email_thread_summary_materialization_run(
        self,
        *,
        run_id: str,
        status: str,
        completed_at_utc: Optional[str] = None,
        threads_considered: int = 0,
        threads_summarized: int = 0,
        review_required_count: int = 0,
        error_redacted: Optional[str] = None,
    ) -> bool:
        """Finalize a thread-summary materialization run receipt with counters
        (redacted error only)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                UPDATE email_thread_summary_materialization_runs SET
                    status = ?, completed_at_utc = ?, threads_considered = ?,
                    threads_summarized = ?, review_required_count = ?, error_redacted = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    completed_at_utc or _utc_now(),
                    threads_considered,
                    threads_summarized,
                    review_required_count,
                    error_redacted,
                    run_id,
                ),
            )
            return cur.rowcount > 0

    def enqueue_email_review_item(
        self,
        *,
        review_id: str,
        message_id: str,
        category: str,
        sensitivity: str,
        reason: str,
        suggested_action: str,
        confidence: float,
        project_key: Optional[str] = None,
        status: str = "open",
        body_capture_eligible: bool = False,
        encrypted_body_capture_allowed: bool = False,
        review_required_before_body_use: bool = False,
        body_capture_decision_json: Optional[str] = None,
    ) -> bool:
        """Idempotent enqueue keyed by (message_id, category, reason).

        Returns True if a new review item was inserted, False if it already
        existed (INSERT OR IGNORE on the UNIQUE constraint). The V13 body-capture
        decision columns are written too (no plaintext body — refs/flags only).
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO email_review_queue
                    (review_id, message_id, project_key, category, sensitivity,
                     reason, suggested_action, confidence, status, routed_utc,
                     body_capture_eligible, encrypted_body_capture_allowed,
                     review_required_before_body_use, body_capture_decision_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    message_id,
                    project_key,
                    category,
                    sensitivity,
                    reason,
                    suggested_action,
                    confidence,
                    status,
                    _utc_now(),
                    1 if body_capture_eligible else 0,
                    1 if encrypted_body_capture_allowed else 0,
                    1 if review_required_before_body_use else 0,
                    body_capture_decision_json,
                ),
            )
            return cur.rowcount > 0

    def list_email_review_queue(
        self,
        *,
        project_key: Optional[str] = None,
        status: Optional[str] = "open",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        keys = (
            "review_id",
            "message_id",
            "project_key",
            "category",
            "sensitivity",
            "reason",
            "suggested_action",
            "confidence",
            "status",
            "routed_utc",
            "resolved_utc",
            "body_capture_eligible",
            "encrypted_body_capture_allowed",
            "review_required_before_body_use",
            "body_capture_decision_json",
        )
        bool_keys = (
            "body_capture_eligible",
            "encrypted_body_capture_allowed",
            "review_required_before_body_use",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_review_queue {where} "
            "ORDER BY routed_utc DESC, review_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            for bk in bool_keys:
                record[bk] = bool(record[bk])
            results.append(record)
        return results

    def count_email_review_queue(
        self,
        *,
        project_key: Optional[str] = None,
        status: Optional[str] = "open",
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        conn = get_connection(self._db_path)
        cur = conn.execute(f"SELECT COUNT(*) FROM email_review_queue {where}", tuple(params))
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def insert_email_processing_receipt(
        self,
        *,
        receipt_id: str,
        operation: str,
        status: str,
        run_id: Optional[str] = None,
        message_id: Optional[str] = None,
        project_key: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
        mailbox_mutation_attempted: bool = False,
        full_body_persisted: bool = False,
        attachment_content_downloaded: bool = False,
    ) -> None:
        self._reject_email_mutation_flags(
            mailbox_mutation_attempted=mailbox_mutation_attempted,
            full_body_persisted=full_body_persisted,
            attachment_content_downloaded=attachment_content_downloaded,
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_processing_receipts
                    (receipt_id, run_id, message_id, project_key, operation, status,
                     detail_json, mailbox_mutation_attempted, full_body_persisted,
                     attachment_content_downloaded, generated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                """,
                (
                    receipt_id,
                    run_id,
                    message_id,
                    project_key,
                    operation,
                    status,
                    self._dump_json(detail),
                    _utc_now(),
                ),
            )

    def list_email_processing_receipts(
        self,
        *,
        run_id: Optional[str] = None,
        message_id: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        keys = (
            "receipt_id",
            "run_id",
            "message_id",
            "project_key",
            "operation",
            "status",
            "detail_json",
            "mailbox_mutation_attempted",
            "full_body_persisted",
            "attachment_content_downloaded",
            "generated_utc",
        )
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if message_id is not None:
            clauses.append("message_id = ?")
            params.append(message_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_processing_receipts {where} "
            "ORDER BY generated_utc DESC, receipt_id LIMIT ?",
            tuple(params),
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            record = dict(zip(keys, row, strict=True))
            record["detail"] = self._load_json(record.pop("detail_json"))
            for bool_field in (
                "mailbox_mutation_attempted",
                "full_body_persisted",
                "attachment_content_downloaded",
            ):
                record[bool_field] = bool(record[bool_field])
            results.append(record)
        return results

    @staticmethod
    def _reject_email_mutation_flags(
        *,
        mailbox_mutation_attempted: bool,
        full_body_persisted: bool,
        attachment_content_downloaded: bool,
    ) -> None:
        if mailbox_mutation_attempted is not False:
            raise ValueError(
                "mailbox_mutation_attempted must be False — Phase 06 mailbox is read-only"
            )
        if full_body_persisted is not False:
            raise ValueError(
                "full_body_persisted must be False — Phase 06 never persists full bodies"
            )
        if attachment_content_downloaded is not False:
            raise ValueError(
                "attachment_content_downloaded must be False — Phase 06 never "
                "downloads attachment content by default"
            )

    # --- V12 encrypted full-body vault refs (Phase 06 Prompt 08A) -----------
    # Stores ONLY a deterministic encrypted_full_body_ref + hash/length/metadata.
    # There is no plaintext parameter and no plaintext column; the body lives
    # encrypted in the text vault outside the repo. All plaintext / obsidian /
    # evidence / log persistence flags are forced 0 (and CHECK-locked at the DB).

    def upsert_email_body_vault_ref(
        self,
        *,
        message_id: str,
        encrypted_full_body_ref: str,
        body_hash: str,
        body_length: int,
        extraction_policy: str,
        internet_message_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        body_content_type: Optional[str] = None,
        review_required: bool = False,
        sensitivity_classification: Optional[str] = None,
    ) -> None:
        if not encrypted_full_body_ref:
            raise ValueError("encrypted_full_body_ref must be a non-empty vault reference")
        if not body_hash:
            raise ValueError("body_hash must be a non-empty hash")
        if body_length <= 0:
            raise ValueError("body_length must be positive (record a no-body status elsewhere)")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_message_body_vault_refs
                    (message_id, internet_message_id, conversation_id, body_content_type,
                     body_hash, body_length, encrypted_full_body_ref, encryption_method,
                     plaintext_persisted, obsidian_body_persisted, evidence_body_persisted,
                     log_body_persisted, extraction_policy, review_required,
                     sensitivity_classification, encrypted_at_utc, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'fernet_text_vault', 0, 0, 0, 0, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    internet_message_id = excluded.internet_message_id,
                    conversation_id = excluded.conversation_id,
                    body_content_type = excluded.body_content_type,
                    body_hash = excluded.body_hash,
                    body_length = excluded.body_length,
                    encrypted_full_body_ref = excluded.encrypted_full_body_ref,
                    extraction_policy = excluded.extraction_policy,
                    review_required = excluded.review_required,
                    sensitivity_classification = excluded.sensitivity_classification,
                    encrypted_at_utc = excluded.encrypted_at_utc,
                    updated_utc = excluded.updated_utc
                """,
                (
                    message_id,
                    internet_message_id,
                    conversation_id,
                    body_content_type,
                    body_hash,
                    body_length,
                    encrypted_full_body_ref,
                    extraction_policy,
                    1 if review_required else 0,
                    sensitivity_classification,
                    _utc_now(),
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def get_email_body_vault_ref(self, message_id: str) -> Optional[dict[str, Any]]:
        """Return the encrypted-body metadata for a message (never plaintext)."""
        keys = (
            "message_id",
            "internet_message_id",
            "conversation_id",
            "body_content_type",
            "body_hash",
            "body_length",
            "encrypted_full_body_ref",
            "encrypted_at_utc",
            "encryption_method",
            "plaintext_persisted",
            "obsidian_body_persisted",
            "evidence_body_persisted",
            "log_body_persisted",
            "extraction_policy",
            "review_required",
            "sensitivity_classification",
            "created_utc",
            "updated_utc",
        )
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_message_body_vault_refs WHERE message_id = ?",
            (message_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        record = dict(zip(keys, row, strict=True))
        for bool_field in (
            "plaintext_persisted",
            "obsidian_body_persisted",
            "evidence_body_persisted",
            "log_body_persisted",
            "review_required",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    # --- Phase 10A raw content tables (Prompt 03/04 email+calendar raw ingestion) ---
    # Plaintext raw bodies (when policy email_calendar / include flag) live ONLY here.
    # These are exempt from the Phase 10 13-guard CHECK columns (the designated holders).
    # Idempotent upserts; callers (indexer) enforce policy and bounded budgets.

    def upsert_email_message_raw_content(
        self,
        *,
        raw_email_id: str,
        message_id_hash: str,
        internet_message_id_hash: Optional[str] = None,
        conversation_id_hash: Optional[str] = None,
        source_ref_hash: Optional[str] = None,
        project_key: Optional[str] = None,
        subject: Optional[str] = None,
        body_preview: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        from_name: Optional[str] = None,
        from_address: Optional[str] = None,
        to_recipients_json: str = "[]",
        cc_recipients_json: str = "[]",
        bcc_recipients_json: str = "[]",
        sent_at_utc: Optional[str] = None,
        received_at_utc: Optional[str] = None,
        has_attachments: int = 0,
        attachment_metadata_json: str = "[]",
        source_quality: Optional[str] = None,
        payload_hash: Optional[str] = None,
        raw_capture_run_id: Optional[str] = None,
        source_record_ref: Optional[str] = None,
        source_record_id: Optional[int] = None,
        source_updated_at_utc: Optional[str] = None,
        raw_content_schema_version: str = "email_raw_v1",
        raw_sidecar_json: Optional[str] = None,
    ) -> None:
        # Source-quality precedence (V49): a strictly lower-quality re-capture updates only
        # provenance/last-seen metadata and NEVER downgrades local-private body content.
        from hb_assistant.construction.email_calendar.source_quality import (
            classify_email,
            rank_case_sql,
        )

        if source_quality is None:
            source_quality = classify_email(
                body_text=body_text, body_html=body_html, body_preview=body_preview
            )
        if payload_hash is None:
            payload_hash = hashlib.sha256(
                "|".join(
                    str(p or "")
                    for p in (subject, body_text, body_html, body_preview, to_recipients_json)
                ).encode("utf-8", "replace")
            ).hexdigest()
        guard = (
            f"(({rank_case_sql('excluded.source_quality')}) "
            f">= ({rank_case_sql('email_message_raw_content.source_quality')}))"
        )

        def keep(col: str) -> str:
            return (
                f"{col} = CASE WHEN {guard} THEN excluded.{col} "
                f"ELSE email_message_raw_content.{col} END"
            )

        content_cols = [
            "subject",
            "body_preview",
            "body_text",
            "body_html",
            "from_name",
            "from_address",
            "to_recipients_json",
            "cc_recipients_json",
            "bcc_recipients_json",
            "has_attachments",
            "attachment_metadata_json",
            "source_quality",
            "payload_hash",
            "raw_sidecar_json",
        ]
        meta_cols = [
            "message_id_hash",
            "internet_message_id_hash",
            "conversation_id_hash",
            "source_ref_hash",
            "project_key",
            "sent_at_utc",
            "received_at_utc",
            "raw_capture_run_id",
            "source_record_ref",
            "source_record_id",
            "source_updated_at_utc",
            "raw_content_schema_version",
        ]
        set_clause = ",\n                    ".join(
            [keep(c) for c in content_cols]
            + [f"{c} = excluded.{c}" for c in meta_cols]
            + ["updated_utc = excluded.updated_utc"]
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                f"""
                INSERT INTO email_message_raw_content
                    (raw_email_id, message_id_hash, internet_message_id_hash,
                     conversation_id_hash, source_ref_hash, project_key,
                     subject, body_preview, body_text, body_html,
                     from_name, from_address,
                     to_recipients_json, cc_recipients_json, bcc_recipients_json,
                     sent_at_utc, received_at_utc, has_attachments,
                     attachment_metadata_json, source_quality, payload_hash,
                     raw_capture_run_id, source_record_ref, source_record_id,
                     source_updated_at_utc, raw_content_schema_version, raw_sidecar_json,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(raw_email_id) DO UPDATE SET
                    {set_clause}
                """,
                (
                    raw_email_id,
                    message_id_hash,
                    internet_message_id_hash,
                    conversation_id_hash,
                    source_ref_hash,
                    project_key,
                    subject,
                    body_preview,
                    body_text,
                    body_html,
                    from_name,
                    from_address,
                    to_recipients_json,
                    cc_recipients_json,
                    bcc_recipients_json,
                    sent_at_utc,
                    received_at_utc,
                    has_attachments,
                    attachment_metadata_json,
                    source_quality,
                    payload_hash,
                    raw_capture_run_id,
                    source_record_ref,
                    source_record_id,
                    source_updated_at_utc,
                    raw_content_schema_version,
                    raw_sidecar_json,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def upsert_email_thread_raw_context(
        self,
        *,
        raw_thread_context_id: str,
        thread_ref: str,
        conversation_id_hash: Optional[str] = None,
        project_key: Optional[str] = None,
        message_count: int = 0,
        participant_count: int = 0,
        thread_subject: Optional[str] = None,
        messages_json: str = "[]",
        source_refs_json: str = "[]",
        model_ready: int = 1,
        source_quality: Optional[str] = None,
        payload_hash: Optional[str] = None,
        raw_capture_run_id: Optional[str] = None,
        raw_content_schema_version: str = "email_thread_raw_v1",
    ) -> None:
        if source_quality is None:
            from hb_assistant.construction.email_calendar.source_quality import classify_thread

            try:
                members = json.loads(messages_json) if messages_json else []
            except (json.JSONDecodeError, TypeError):
                members = []
            quals: list[str] = []
            for m in members if isinstance(members, list) else []:
                if isinstance(m, dict) and (m.get("body_text") or m.get("body_html")):
                    quals.append("graph_full_body")
            source_quality = classify_thread(quals)
        if payload_hash is None:
            payload_hash = hashlib.sha256(
                "|".join(str(p or "") for p in (thread_ref, thread_subject, messages_json)).encode(
                    "utf-8", "replace"
                )
            ).hexdigest()
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_thread_raw_context
                    (raw_thread_context_id, thread_ref, conversation_id_hash,
                     project_key, message_count, participant_count,
                     thread_subject, messages_json, source_refs_json,
                     model_ready, source_quality, payload_hash, raw_capture_run_id,
                     raw_content_schema_version, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_ref) DO UPDATE SET
                    raw_thread_context_id = excluded.raw_thread_context_id,
                    conversation_id_hash = excluded.conversation_id_hash,
                    project_key = excluded.project_key,
                    message_count = excluded.message_count,
                    participant_count = excluded.participant_count,
                    thread_subject = excluded.thread_subject,
                    messages_json = excluded.messages_json,
                    source_refs_json = excluded.source_refs_json,
                    model_ready = excluded.model_ready,
                    source_quality = excluded.source_quality,
                    payload_hash = excluded.payload_hash,
                    raw_capture_run_id = excluded.raw_capture_run_id,
                    raw_content_schema_version = excluded.raw_content_schema_version,
                    updated_utc = excluded.updated_utc
                """,
                (
                    raw_thread_context_id,
                    thread_ref,
                    conversation_id_hash,
                    project_key,
                    message_count,
                    participant_count,
                    thread_subject,
                    messages_json,
                    source_refs_json,
                    model_ready,
                    source_quality,
                    payload_hash,
                    raw_capture_run_id,
                    raw_content_schema_version,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def record_raw_content_access_event(
        self,
        *,
        source_family: str,
        endpoint_or_command: str,
        source_ref_hash: Optional[str] = None,
        raw_content_included: int = 1,
        purpose: Optional[str] = None,
    ) -> str:
        """Append a raw-content access-audit event (V42 table; no raw body is ever stored).
        Returns the generated event id."""
        event_id = f"rcae-{uuid.uuid4().hex}"
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO raw_content_access_events
                    (access_event_id, source_family, source_ref_hash,
                     endpoint_or_command, raw_content_included, purpose, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    source_family,
                    source_ref_hash,
                    endpoint_or_command,
                    int(raw_content_included),
                    purpose,
                    _utc_now(),
                ),
            )
        return event_id

    def record_email_calendar_raw_ingestion_run(
        self,
        *,
        run_id: str,
        source_family: str,
        mode: str,
        items_seen: int = 0,
        items_attempted_raw: int = 0,
        items_raw_persisted: int = 0,
        source_quality_distribution_json: str = "{}",
        status: str = "ok",
        error_redacted: Optional[str] = None,
    ) -> None:
        """Persist a bounded raw-ingestion run receipt (counts + source-quality distribution;
        never raw bodies). Guard columns keep raw_body_emitted / external_writeback at 0."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO email_calendar_raw_ingestion_runs
                    (run_id, source_family, mode, started_utc, completed_utc,
                     items_seen, items_attempted_raw, items_raw_persisted,
                     source_quality_distribution_json, status, error_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    completed_utc = excluded.completed_utc,
                    items_seen = excluded.items_seen,
                    items_attempted_raw = excluded.items_attempted_raw,
                    items_raw_persisted = excluded.items_raw_persisted,
                    source_quality_distribution_json = excluded.source_quality_distribution_json,
                    status = excluded.status,
                    error_redacted = excluded.error_redacted
                """,
                (
                    run_id,
                    source_family,
                    mode,
                    _utc_now(),
                    _utc_now(),
                    items_seen,
                    items_attempted_raw,
                    items_raw_persisted,
                    source_quality_distribution_json,
                    status,
                    error_redacted,
                ),
            )

    def list_email_message_raw_content(
        self, *, project_key: Optional[str] = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """List raw email message content rows (Phase 10A). Project filter optional.
        JSON columns (recipients, attachment meta) are parsed to lists for callers.
        """
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT raw_email_id, message_id_hash, internet_message_id_hash,
                   conversation_id_hash, source_ref_hash, project_key,
                   subject, body_preview, body_text, body_html,
                   from_name, from_address,
                   to_recipients_json, cc_recipients_json, bcc_recipients_json,
                   sent_at_utc, received_at_utc, has_attachments,
                   attachment_metadata_json, created_utc, updated_utc
            FROM email_message_raw_content {where}
            ORDER BY received_at_utc DESC, message_id_hash
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "raw_email_id",
            "message_id_hash",
            "internet_message_id_hash",
            "conversation_id_hash",
            "source_ref_hash",
            "project_key",
            "subject",
            "body_preview",
            "body_text",
            "body_html",
            "from_name",
            "from_address",
            "to_recipients_json",
            "cc_recipients_json",
            "bcc_recipients_json",
            "sent_at_utc",
            "received_at_utc",
            "has_attachments",
            "attachment_metadata_json",
            "created_utc",
            "updated_utc",
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            rec = dict(zip(keys, row, strict=True))
            # Parse JSON fields for convenience (callers can treat as strings too)
            for jk in (
                "to_recipients_json",
                "cc_recipients_json",
                "bcc_recipients_json",
                "attachment_metadata_json",
            ):
                try:
                    rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
                except Exception:
                    rec[jk.replace("_json", "")] = []
            results.append(rec)
        return results

    def get_email_message_raw_content(
        self, *, message_id_hash: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Fetch a single raw email row by message_id_hash (the PK for the raw table).
        Returns None if not present. Used by email endpoints etc.
        """
        if not message_id_hash:
            return None
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT raw_email_id, message_id_hash, internet_message_id_hash, "
            "conversation_id_hash, source_ref_hash, project_key, subject, body_preview, body_text, body_html, "
            "from_name, from_address, to_recipients_json, cc_recipients_json, bcc_recipients_json, "
            "sent_at_utc, received_at_utc, has_attachments, attachment_metadata_json, "
            "created_utc, updated_utc "
            "FROM email_message_raw_content WHERE message_id_hash = ?",
            (message_id_hash,),
        )
        row = cur.fetchone()
        if not row:
            return None
        keys = (
            "raw_email_id",
            "message_id_hash",
            "internet_message_id_hash",
            "conversation_id_hash",
            "source_ref_hash",
            "project_key",
            "subject",
            "body_preview",
            "body_text",
            "body_html",
            "from_name",
            "from_address",
            "to_recipients_json",
            "cc_recipients_json",
            "bcc_recipients_json",
            "sent_at_utc",
            "received_at_utc",
            "has_attachments",
            "attachment_metadata_json",
            "created_utc",
            "updated_utc",
        )
        rec = dict(zip(keys, row, strict=True))
        for jk in (
            "to_recipients_json",
            "cc_recipients_json",
            "bcc_recipients_json",
            "attachment_metadata_json",
        ):
            try:
                rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
            except Exception:
                rec[jk.replace("_json", "")] = []
        return rec

    def list_email_thread_raw_context(
        self, *, project_key: Optional[str] = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """List raw email thread context rows (Phase 10A). Project filter optional.
        JSON columns (messages, source refs) are parsed to lists.
        """
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT raw_thread_context_id, thread_ref, conversation_id_hash,
                   project_key, message_count, participant_count,
                   thread_subject, messages_json, source_refs_json,
                   model_ready, created_utc, updated_utc
            FROM email_thread_raw_context {where}
            ORDER BY thread_subject, thread_ref
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "raw_thread_context_id",
            "thread_ref",
            "conversation_id_hash",
            "project_key",
            "message_count",
            "participant_count",
            "thread_subject",
            "messages_json",
            "source_refs_json",
            "model_ready",
            "created_utc",
            "updated_utc",
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            rec = dict(zip(keys, row, strict=True))
            for jk in ("messages_json", "source_refs_json"):
                try:
                    rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
                except Exception:
                    rec[jk.replace("_json", "")] = []
            results.append(rec)
        return results

    def get_email_thread_raw_context(
        self, *, thread_ref: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Fetch a single raw thread context by thread_ref.
        Returns None if not present.
        """
        if not thread_ref:
            return None
        conn = get_connection(self._db_path)
        cur = conn.execute(
            "SELECT raw_thread_context_id, thread_ref, conversation_id_hash, "
            "project_key, message_count, participant_count, thread_subject, "
            "messages_json, source_refs_json, model_ready, created_utc, updated_utc "
            "FROM email_thread_raw_context WHERE thread_ref = ?",
            (thread_ref,),
        )
        row = cur.fetchone()
        if not row:
            return None
        keys = (
            "raw_thread_context_id",
            "thread_ref",
            "conversation_id_hash",
            "project_key",
            "message_count",
            "participant_count",
            "thread_subject",
            "messages_json",
            "source_refs_json",
            "model_ready",
            "created_utc",
            "updated_utc",
        )
        rec = dict(zip(keys, row, strict=True))
        for jk in ("messages_json", "source_refs_json"):
            try:
                rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
            except Exception:
                rec[jk.replace("_json", "")] = []
        return rec

    def upsert_calendar_event_raw_content(
        self,
        *,
        raw_calendar_event_id: str,
        graph_event_id_hash: str,
        event_index_id: Optional[str] = None,
        source_ref_hash: Optional[str] = None,
        project_key: Optional[str] = None,
        subject: Optional[str] = None,
        body_preview: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        location_display: Optional[str] = None,
        organizer_name: Optional[str] = None,
        organizer_email: Optional[str] = None,
        attendees_json: str = "[]",
        online_meeting_provider: Optional[str] = None,
        join_url: Optional[str] = None,
        recurrence_json: Optional[str] = None,
        start_datetime_utc: Optional[str] = None,
        end_datetime_utc: Optional[str] = None,
        source_quality: Optional[str] = None,
        payload_hash: Optional[str] = None,
        raw_capture_run_id: Optional[str] = None,
        source_record_ref: Optional[str] = None,
        source_record_id: Optional[int] = None,
        source_updated_at_utc: Optional[str] = None,
        raw_content_schema_version: str = "calendar_raw_v1",
        join_url_policy: str = "local_db_only",
        raw_sidecar_json: Optional[str] = None,
    ) -> None:
        # Source-quality precedence (V49): a strictly lower-quality re-capture updates only
        # provenance metadata and never downgrades local-private event/agenda content. The
        # join URL is retained locally under join_url_policy and never emitted outward.
        from hb_assistant.construction.email_calendar.source_quality import (
            classify_calendar,
            rank_case_sql,
        )

        if source_quality is None:
            source_quality = classify_calendar(
                body_text=body_text, body_html=body_html, body_preview=body_preview
            )
        if payload_hash is None:
            payload_hash = hashlib.sha256(
                "|".join(
                    str(p or "")
                    for p in (subject, body_text, body_html, attendees_json, recurrence_json)
                ).encode("utf-8", "replace")
            ).hexdigest()
        guard = (
            f"(({rank_case_sql('excluded.source_quality')}) "
            f">= ({rank_case_sql('calendar_event_raw_content.source_quality')}))"
        )

        def keep(col: str) -> str:
            return (
                f"{col} = CASE WHEN {guard} THEN excluded.{col} "
                f"ELSE calendar_event_raw_content.{col} END"
            )

        content_cols = [
            "subject",
            "body_preview",
            "body_text",
            "body_html",
            "location_display",
            "organizer_name",
            "organizer_email",
            "attendees_json",
            "online_meeting_provider",
            "join_url",
            "recurrence_json",
            "source_quality",
            "payload_hash",
            "raw_sidecar_json",
        ]
        meta_cols = [
            "event_index_id",
            "graph_event_id_hash",
            "source_ref_hash",
            "project_key",
            "start_datetime_utc",
            "end_datetime_utc",
            "raw_capture_run_id",
            "source_record_ref",
            "source_record_id",
            "source_updated_at_utc",
            "raw_content_schema_version",
            "join_url_policy",
        ]
        set_clause = ",\n                    ".join(
            [keep(c) for c in content_cols]
            + [f"{c} = excluded.{c}" for c in meta_cols]
            + ["updated_utc = excluded.updated_utc"]
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                f"""
                INSERT INTO calendar_event_raw_content
                    (raw_calendar_event_id, event_index_id, graph_event_id_hash,
                     source_ref_hash, project_key,
                     subject, body_preview, body_text, body_html,
                     location_display, organizer_name, organizer_email,
                     attendees_json, online_meeting_provider, join_url,
                     recurrence_json, start_datetime_utc, end_datetime_utc,
                     source_quality, payload_hash, raw_capture_run_id,
                     source_record_ref, source_record_id, source_updated_at_utc,
                     raw_content_schema_version, join_url_policy, raw_sidecar_json,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(raw_calendar_event_id) DO UPDATE SET
                    {set_clause}
                """,
                (
                    raw_calendar_event_id,
                    event_index_id,
                    graph_event_id_hash,
                    source_ref_hash,
                    project_key,
                    subject,
                    body_preview,
                    body_text,
                    body_html,
                    location_display,
                    organizer_name,
                    organizer_email,
                    attendees_json,
                    online_meeting_provider,
                    join_url,
                    recurrence_json,
                    start_datetime_utc,
                    end_datetime_utc,
                    source_quality,
                    payload_hash,
                    raw_capture_run_id,
                    source_record_ref,
                    source_record_id,
                    source_updated_at_utc,
                    raw_content_schema_version,
                    join_url_policy,
                    raw_sidecar_json,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def list_calendar_event_raw_content(
        self, *, project_key: Optional[str] = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT raw_calendar_event_id, event_index_id, graph_event_id_hash,
                   source_ref_hash, project_key, subject, body_preview,
                   body_text, body_html, location_display, organizer_name,
                   organizer_email, attendees_json, online_meeting_provider,
                   join_url, recurrence_json, start_datetime_utc, end_datetime_utc,
                   created_utc, updated_utc
            FROM calendar_event_raw_content {where}
            ORDER BY start_datetime_utc DESC, raw_calendar_event_id
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "raw_calendar_event_id",
            "event_index_id",
            "graph_event_id_hash",
            "source_ref_hash",
            "project_key",
            "subject",
            "body_preview",
            "body_text",
            "body_html",
            "location_display",
            "organizer_name",
            "organizer_email",
            "attendees_json",
            "online_meeting_provider",
            "join_url",
            "recurrence_json",
            "start_datetime_utc",
            "end_datetime_utc",
            "created_utc",
            "updated_utc",
        )
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            rec = dict(zip(keys, row, strict=True))
            # Parse JSON fields for convenience (callers can treat as strings too)
            for jk in ("attendees_json", "recurrence_json"):
                try:
                    rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
                except Exception:
                    rec[jk.replace("_json", "")] = []
            results.append(rec)
        return results

    def list_calendar_structured_subjects(
        self, *, project_key: Optional[str] = None, limit: int = 100000
    ) -> list[dict[str, Any]]:
        """Real subject/location per event from the V49 structured projection (preferred substrate).

        Returns only the safe scalar fields used for deterministic project/category resolution
        (``event_index_id``, ``subject``, ``location_display``, ``source_quality``) — never body
        text, join URLs, or attendee arrays. ``calendar_raw_event_structured`` carries its own
        ``event_index_id`` so no join is needed. Used by calendar-prep to prefer structured rows
        over the raw landing for resolution; the raw landing remains the fallback when a given
        event has not yet been projected.
        """
        conn = get_connection(self._db_path)
        clauses: list[str] = ["event_index_id IS NOT NULL"]
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        where = f"WHERE {' AND '.join(clauses)}"
        params.append(limit)
        try:
            cur = conn.execute(
                f"""
                SELECT event_index_id, subject, location_display, project_key, source_quality
                FROM calendar_raw_event_structured {where}
                ORDER BY start_datetime_utc DESC, event_index_id
                LIMIT ?
                """,
                tuple(params),
            )
        except sqlite3.Error:
            return []
        keys = ("event_index_id", "subject", "location_display", "project_key", "source_quality")
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def email_followup_readiness_counts(self) -> dict[str, int]:
        """Raw-free row counts for the email/follow-up readiness data-gap surface.

        Returns ``COUNT(*)`` for the email raw/structured substrate and the downstream follow-up
        layers. Used to decide whether email raw content is available while the follow-up/task
        layers are empty (a data gap), without emitting any raw values. Missing tables count as 0.
        """
        conn = get_connection(self._db_path)

        def _n(table: str) -> int:
            try:
                return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                return 0

        return {
            "email_message_raw_content": _n("email_message_raw_content"),
            "email_thread_raw_context": _n("email_thread_raw_context"),
            "email_raw_message_structured": _n("email_raw_message_structured"),
            "email_raw_thread_structured": _n("email_raw_thread_structured"),
            "email_followup_enrichments": _n("email_followup_enrichments"),
            "task_candidates": _n("task_candidates"),
            "commitment_candidates": _n("commitment_candidates"),
            "follow_up_watch_items": _n("follow_up_watch_items"),
        }

    def get_calendar_event_raw_content(
        self,
        *,
        event_index_id: Optional[str] = None,
        graph_event_id_hash: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Fetch a single raw calendar row by stable key (event_index_id or graph hash).
        Returns None if not present. Used for meeting-prep packet enrichment etc.
        """
        if not event_index_id and not graph_event_id_hash:
            return None
        conn = get_connection(self._db_path)
        if graph_event_id_hash:
            cur = conn.execute(
                "SELECT raw_calendar_event_id, event_index_id, graph_event_id_hash, "
                "source_ref_hash, project_key, subject, body_preview, body_text, body_html, "
                "location_display, organizer_name, organizer_email, attendees_json, "
                "online_meeting_provider, join_url, recurrence_json, start_datetime_utc, end_datetime_utc "
                "FROM calendar_event_raw_content WHERE graph_event_id_hash = ?",
                (graph_event_id_hash,),
            )
        else:
            cur = conn.execute(
                "SELECT raw_calendar_event_id, event_index_id, graph_event_id_hash, "
                "source_ref_hash, project_key, subject, body_preview, body_text, body_html, "
                "location_display, organizer_name, organizer_email, attendees_json, "
                "online_meeting_provider, join_url, recurrence_json, start_datetime_utc, end_datetime_utc "
                "FROM calendar_event_raw_content WHERE event_index_id = ?",
                (event_index_id,),
            )
        row = cur.fetchone()
        if not row:
            return None
        keys = (
            "raw_calendar_event_id",
            "event_index_id",
            "graph_event_id_hash",
            "source_ref_hash",
            "project_key",
            "subject",
            "body_preview",
            "body_text",
            "body_html",
            "location_display",
            "organizer_name",
            "organizer_email",
            "attendees_json",
            "online_meeting_provider",
            "join_url",
            "recurrence_json",
            "start_datetime_utc",
            "end_datetime_utc",
        )
        rec = dict(zip(keys, row, strict=True))
        for jk in ("attendees_json", "recurrence_json"):
            try:
                rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
            except Exception:
                rec[jk.replace("_json", "")] = []
        return rec

    # -------------------------------------------------------------------------
    # --- V49 structured projection read accessors (Pass 2) ---
    # Generic PRAGMA-driven SELECT * helpers + typed getters/listers for the
    # final structured projection tables. Consumers reach these via the
    # email_calendar.read_models precedence-aware selectors, never raw JSON.
    # -------------------------------------------------------------------------

    def _structured_select_one(
        self, table: str, where_col: str, where_val: Any
    ) -> Optional[dict[str, Any]]:
        if not where_val:
            return None
        conn = get_connection(self._db_path)
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            if not cols:
                return None
            row = conn.execute(
                f"SELECT {', '.join(cols)} FROM {table} WHERE {where_col} = ? LIMIT 1",
                (where_val,),
            ).fetchone()
        except sqlite3.Error:
            return None
        return dict(zip(cols, row, strict=True)) if row else None

    def _structured_select_all(
        self,
        table: str,
        *,
        where_col: Optional[str] = None,
        where_val: Any = None,
        limit: int = 1000,
        order_by: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        conn = get_connection(self._db_path)
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            if not cols:
                return []
            sql = f"SELECT {', '.join(cols)} FROM {table}"
            params: list[Any] = []
            if where_col is not None and where_val is not None:
                sql += f" WHERE {where_col} = ?"
                params.append(where_val)
            if order_by:
                sql += f" ORDER BY {order_by}"
            sql += " LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error:
            return []
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def get_email_message_structured(
        self, *, message_id_hash: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        return self._structured_select_one(
            "email_raw_message_structured", "message_id_hash", message_id_hash
        )

    def list_email_message_structured(
        self, *, project_key: Optional[str] = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        return self._structured_select_all(
            "email_raw_message_structured",
            where_col="project_key" if project_key else None,
            where_val=project_key,
            limit=limit,
            order_by="received_at_utc DESC",
        )

    def list_email_message_recipients_structured(
        self, *, parent_projection_id: str
    ) -> list[dict[str, Any]]:
        return self._structured_select_all(
            "email_raw_message_recipients_structured",
            where_col="parent_projection_id",
            where_val=parent_projection_id,
            limit=500,
            order_by="child_index",
        )

    def get_thread_structured(
        self, *, thread_ref: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        return self._structured_select_one(
            "email_raw_thread_structured", "thread_ref", thread_ref
        )

    def list_thread_structured(
        self, *, project_key: Optional[str] = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        return self._structured_select_all(
            "email_raw_thread_structured",
            where_col="project_key" if project_key else None,
            where_val=project_key,
            limit=limit,
        )

    def get_event_structured(
        self,
        *,
        event_index_id: Optional[str] = None,
        graph_event_id_hash: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if event_index_id:
            return self._structured_select_one(
                "calendar_raw_event_structured", "event_index_id", event_index_id
            )
        return self._structured_select_one(
            "calendar_raw_event_structured", "graph_event_id_hash", graph_event_id_hash
        )

    def list_event_structured(
        self, *, project_key: Optional[str] = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        return self._structured_select_all(
            "calendar_raw_event_structured",
            where_col="project_key" if project_key else None,
            where_val=project_key,
            limit=limit,
            order_by="start_datetime_utc DESC",
        )

    def list_event_attendees_structured(
        self, *, parent_projection_id: str
    ) -> list[dict[str, Any]]:
        return self._structured_select_all(
            "calendar_raw_event_attendees_structured",
            where_col="parent_projection_id",
            where_val=parent_projection_id,
            limit=500,
            order_by="child_index",
        )

    # -------------------------------------------------------------------------
    # --- Phase 10A Prompt 06 — Raw Model Context Packets (V42 table) ---
    # Builders (local_ai/raw_context) persist model-ready packets containing
    # actual raw email/calendar content (when policy + model_context allow).
    # Bounded per ModelContextConfig; carry source refs + token_estimate.
    # -------------------------------------------------------------------------

    def upsert_raw_content_model_context_packet(
        self,
        *,
        packet_id: str,
        packet_type: str,
        source_family: str,
        source_ref_hash: Optional[str] = None,
        project_key: Optional[str] = None,
        raw_content_included: int = 1,
        packet_json: str,
        token_estimate: Optional[int] = None,
    ) -> None:
        """Idempotent upsert for a raw content model context packet (P06)."""
        if not packet_id:
            raise ValueError("packet_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO raw_content_model_context_packets
                    (packet_id, packet_type, source_family, source_ref_hash,
                     project_key, raw_content_included, packet_json, token_estimate,
                     created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(packet_id) DO UPDATE SET
                    packet_type = excluded.packet_type,
                    source_family = excluded.source_family,
                    source_ref_hash = excluded.source_ref_hash,
                    project_key = excluded.project_key,
                    raw_content_included = excluded.raw_content_included,
                    packet_json = excluded.packet_json,
                    token_estimate = excluded.token_estimate
                """,
                (
                    packet_id,
                    packet_type,
                    source_family,
                    source_ref_hash,
                    project_key,
                    raw_content_included,
                    packet_json,
                    token_estimate,
                    _utc_now(),
                ),
            )

    def list_raw_content_model_context_packets(
        self,
        *,
        project_key: Optional[str] = None,
        packet_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List persisted raw model context packets (for inspection/evidence)."""
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if packet_type is not None:
            clauses.append("packet_type = ?")
            params.append(packet_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT packet_id, packet_type, source_family, source_ref_hash,
                   project_key, raw_content_included, packet_json, token_estimate, created_utc
            FROM raw_content_model_context_packets {where}
            ORDER BY created_utc DESC
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "packet_id",
            "packet_type",
            "source_family",
            "source_ref_hash",
            "project_key",
            "raw_content_included",
            "packet_json",
            "token_estimate",
            "created_utc",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # --- Phase 10 V41 Action Candidates (task, commitment, source refs) from raw content (P07) ---
    # Advisory candidates produced by local models over Phase 10A raw email/calendar content.
    # Persist with evidence_redacted = bounded verbatim raw excerpt from the source raw row
    # (the raw tables themselves are the exempt holders; these carry short excerpts for explainability).
    # Idempotent on candidate_id (PK) / stable_key (UNIQUE for tasks/comms). Source refs link
    # back to raw rows (email_message_raw_content, calendar_event_raw_content, etc.).
    # The 13 _P10_GUARDS are enforced by the table DDL (never set here).
    # -------------------------------------------------------------------------

    def upsert_task_candidate(
        self,
        *,
        candidate_id: str,
        stable_key: str,
        title_redacted: str,
        project_key: Optional[str] = None,
        assignee_class: str = "unknown",
        due_at_utc: Optional[str] = None,
        urgency: str = "normal",
        waiting_state: str = "unknown",
        safety_category: str = "normal",
        confidence: float = 0.0,
        reason_redacted: Optional[str] = None,
        recommended_next_action: str = "review",
        review_status: str = "pending",
        model_profile_id: Optional[str] = None,
        prompt_template_version: Optional[str] = None,
    ) -> None:
        """Upsert a Phase 10 V41 task candidate (advisory, produced from raw content).

        Idempotent by candidate_id (and stable_key UNIQUE). Mirrors the V41 DDL.
        """
        if not candidate_id or not stable_key or not title_redacted:
            raise ValueError("candidate_id, stable_key and title_redacted are required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO task_candidates
                    (candidate_id, stable_key, title_redacted, project_key, assignee_class,
                     due_at_utc, urgency, waiting_state, safety_category, confidence,
                     reason_redacted, recommended_next_action, review_status,
                     model_profile_id, prompt_template_version, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    stable_key = excluded.stable_key,
                    title_redacted = excluded.title_redacted,
                    project_key = excluded.project_key,
                    assignee_class = excluded.assignee_class,
                    due_at_utc = excluded.due_at_utc,
                    urgency = excluded.urgency,
                    waiting_state = excluded.waiting_state,
                    safety_category = excluded.safety_category,
                    confidence = excluded.confidence,
                    reason_redacted = excluded.reason_redacted,
                    recommended_next_action = excluded.recommended_next_action,
                    review_status = excluded.review_status,
                    model_profile_id = excluded.model_profile_id,
                    prompt_template_version = excluded.prompt_template_version,
                    updated_utc = excluded.updated_utc
                """,
                (
                    candidate_id,
                    stable_key,
                    title_redacted,
                    project_key,
                    assignee_class,
                    due_at_utc,
                    urgency,
                    waiting_state,
                    safety_category,
                    confidence,
                    reason_redacted,
                    recommended_next_action,
                    review_status,
                    model_profile_id,
                    prompt_template_version,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def upsert_commitment_candidate(
        self,
        *,
        candidate_id: str,
        stable_key: str,
        title_redacted: str,
        project_key: Optional[str] = None,
        commitment_actor_class: str = "unknown",
        promised_at_utc: Optional[str] = None,
        due_at_utc: Optional[str] = None,
        urgency: str = "normal",
        waiting_state: str = "unknown",
        safety_category: str = "normal",
        confidence: float = 0.0,
        reason_redacted: Optional[str] = None,
        recommended_next_action: str = "review",
        review_status: str = "pending",
        model_profile_id: Optional[str] = None,
        prompt_template_version: Optional[str] = None,
    ) -> None:
        """Upsert a Phase 10 V41 commitment candidate (advisory, produced from raw content).

        Idempotent by candidate_id (and stable_key UNIQUE). Mirrors the V41 DDL.
        """
        if not candidate_id or not stable_key or not title_redacted:
            raise ValueError("candidate_id, stable_key and title_redacted are required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO commitment_candidates
                    (candidate_id, stable_key, title_redacted, project_key, commitment_actor_class,
                     promised_at_utc, due_at_utc, urgency, waiting_state, safety_category,
                     confidence, reason_redacted, recommended_next_action, review_status,
                     model_profile_id, prompt_template_version, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    stable_key = excluded.stable_key,
                    title_redacted = excluded.title_redacted,
                    project_key = excluded.project_key,
                    commitment_actor_class = excluded.commitment_actor_class,
                    promised_at_utc = excluded.promised_at_utc,
                    due_at_utc = excluded.due_at_utc,
                    urgency = excluded.urgency,
                    waiting_state = excluded.waiting_state,
                    safety_category = excluded.safety_category,
                    confidence = excluded.confidence,
                    reason_redacted = excluded.reason_redacted,
                    recommended_next_action = excluded.recommended_next_action,
                    review_status = excluded.review_status,
                    model_profile_id = excluded.model_profile_id,
                    prompt_template_version = excluded.prompt_template_version,
                    updated_utc = excluded.updated_utc
                """,
                (
                    candidate_id,
                    stable_key,
                    title_redacted,
                    project_key,
                    commitment_actor_class,
                    promised_at_utc,
                    due_at_utc,
                    urgency,
                    waiting_state,
                    safety_category,
                    confidence,
                    reason_redacted,
                    recommended_next_action,
                    review_status,
                    model_profile_id,
                    prompt_template_version,
                    _utc_now(),
                    _utc_now(),
                ),
            )

    def upsert_candidate_source_ref(
        self,
        *,
        source_ref_id: str,
        candidate_type: str,
        candidate_id: str,
        source_family: str,
        source_ref_hash: str,
        source_table: Optional[str] = None,
        source_primary_key_hash: Optional[str] = None,
        evidence_redacted: Optional[str] = None,
    ) -> None:
        """Upsert a source reference for a Phase 10 action candidate.

        candidate_type: "task" | "commitment" (or other Phase 10 types).
        When source is raw email/calendar content, pass a short bounded excerpt in
        evidence_redacted (verbatim from the raw row body/subject etc.).
        Idempotent by source_ref_id.
        """
        if not source_ref_id or not candidate_id or not source_family or not source_ref_hash:
            raise ValueError(
                "source_ref_id, candidate_id, source_family and source_ref_hash are required"
            )
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO candidate_source_refs
                    (source_ref_id, candidate_type, candidate_id, source_family,
                     source_ref_hash, source_table, source_primary_key_hash,
                     evidence_redacted, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_ref_id) DO UPDATE SET
                    candidate_type = excluded.candidate_type,
                    candidate_id = excluded.candidate_id,
                    source_family = excluded.source_family,
                    source_ref_hash = excluded.source_ref_hash,
                    source_table = excluded.source_table,
                    source_primary_key_hash = excluded.source_primary_key_hash,
                    evidence_redacted = excluded.evidence_redacted
                """,
                (
                    source_ref_id,
                    candidate_type,
                    candidate_id,
                    source_family,
                    source_ref_hash,
                    source_table,
                    source_primary_key_hash,
                    evidence_redacted,
                    _utc_now(),
                ),
            )

    def insert_local_model_run_receipt(
        self,
        *,
        model_run_receipt_id: str,
        profile_id: str,
        provider: str,
        model_name: str,
        task_type: str,
        status: str,
        input_context_hash: str,
        output_hash: Optional[str] = None,
        schema_name: Optional[str] = None,
        schema_valid: bool = False,
        input_token_count: Optional[int] = None,
        output_token_count: Optional[int] = None,
        latency_ms: Optional[int] = None,
        fallback_used: bool = False,
    ) -> None:
        """Persist a Phase 10 V41 ``local_model_run_receipts`` row (hashing-only).

        This method is the only write path to the receipt table. By contract it accepts
        **hashes and metadata only** — there is no parameter that can carry a raw prompt,
        raw response, body, URL, token, or path. ``input_context_hash`` / ``output_hash``
        are the SHA-256[:12] prefixes from ``procore.normalizers.hashing.hash_summary``.
        The 13 no-raw / no-writeback guard columns are pinned to literal 0 (the schema CHECK
        forbids any other value and the schema-status proof sums them to 0).
        """
        if not model_run_receipt_id or not profile_id or not provider or not model_name:
            raise ValueError(
                "model_run_receipt_id, profile_id, provider and model_name are required"
            )
        if not task_type or not status or not input_context_hash:
            raise ValueError("task_type, status and input_context_hash are required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO local_model_run_receipts
                    (model_run_receipt_id, profile_id, provider, model_name, task_type,
                     status, input_context_hash, output_hash, schema_name, schema_valid,
                     input_token_count, output_token_count, latency_ms, fallback_used,
                     created_utc,
                     raw_email_body_persisted, raw_document_text_persisted,
                     raw_calendar_payload_persisted, raw_procore_payload_persisted,
                     raw_prompt_persisted, raw_response_persisted, signed_url_persisted,
                     download_url_persisted, external_writeback_performed,
                     graph_writeback_performed, procore_writeback_performed,
                     email_send_performed, calendar_mutation_performed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                """,
                (
                    model_run_receipt_id,
                    profile_id,
                    provider,
                    model_name,
                    task_type,
                    status,
                    input_context_hash,
                    output_hash,
                    schema_name,
                    1 if schema_valid else 0,
                    input_token_count,
                    output_token_count,
                    latency_ms,
                    1 if fallback_used else 0,
                    _utc_now(),
                ),
            )

    def list_local_model_run_receipts(
        self,
        *,
        profile_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List run receipts (for tests/evidence). Hash-only fields."""
        conn = get_connection(self._db_path)
        sql = (
            "SELECT model_run_receipt_id, profile_id, provider, model_name, task_type, "
            "status, input_context_hash, output_hash, schema_name, schema_valid, "
            "input_token_count, output_token_count, latency_ms, fallback_used, created_utc "
            "FROM local_model_run_receipts WHERE 1=1"
        )
        params: list[Any] = []
        if profile_id is not None:
            sql += " AND profile_id = ?"
            params.append(profile_id)
        sql += " ORDER BY created_utc DESC LIMIT ?"
        params.append(int(limit))
        keys = (
            "model_run_receipt_id",
            "profile_id",
            "provider",
            "model_name",
            "task_type",
            "status",
            "input_context_hash",
            "output_hash",
            "schema_name",
            "schema_valid",
            "input_token_count",
            "output_token_count",
            "latency_ms",
            "fallback_used",
            "created_utc",
        )
        rows = [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]
        for r in rows:
            r["schema_valid"] = bool(r["schema_valid"])
            r["fallback_used"] = bool(r["fallback_used"])
        return rows

    def ai_job_status_summary(
        self,
        *,
        environment: Optional[str] = None,
    ) -> dict[str, Any]:
        """Read-only Phase 10 AI-job posture: queue counts by status + recent run aggregates.

        Scoped by ``environment`` (dev/production isolation) when provided. Uses the
        ``ix_ai_job_queue_env_status`` index. Metadata/counts only — no payloads, no raw.
        """
        conn = get_connection(self._db_path)

        q_sql = "SELECT status, COUNT(*) FROM ai_job_queue WHERE 1=1"
        q_params: list[Any] = []
        if environment is not None:
            q_sql += " AND environment = ?"
            q_params.append(environment)
        q_sql += " GROUP BY status"
        queue_by_status = {
            str(row[0]): int(row[1]) for row in conn.execute(q_sql, tuple(q_params)).fetchall()
        }
        queue_total = sum(queue_by_status.values())

        r_sql = (
            "SELECT COUNT(*), "
            "COALESCE(SUM(candidate_count),0), "
            "COALESCE(SUM(accepted_count),0), "
            "COALESCE(SUM(rejected_count),0), "
            "COALESCE(SUM(CASE WHEN dry_run = 1 THEN 1 ELSE 0 END),0) "
            "FROM ai_job_runs"
        )
        r_params: list[Any] = []
        if environment is not None:
            r_sql += " WHERE job_id IN (SELECT job_id FROM ai_job_queue WHERE environment = ?)"
            r_params.append(environment)
        rrow = conn.execute(r_sql, tuple(r_params)).fetchone()
        runs = {
            "run_count": int(rrow[0]),
            "candidate_count": int(rrow[1]),
            "accepted_count": int(rrow[2]),
            "rejected_count": int(rrow[3]),
            "dry_run_count": int(rrow[4]),
        }
        return {
            "environment": environment,
            "queue_total": queue_total,
            "queue_by_status": queue_by_status,
            "runs": runs,
        }

    # -- Phase 10 Prompt 05: AI job queue + run lifecycle (advisory, local-only) -------------
    def enqueue_ai_job(
        self,
        *,
        job_id: str,
        environment: str,
        job_type: str,
        idempotency_key: str,
        priority: int = 100,
        source_watermark: Optional[str] = None,
        payload_json: str = "{}",
        max_retries: int = 2,
        status: str = "queued",
    ) -> bool:
        """Idempotent enqueue into V41 ``ai_job_queue`` (metadata only).

        Keyed by ``UNIQUE(environment, job_type, idempotency_key)`` via INSERT OR IGNORE — returns
        True when a new row was created, False when an equivalent job already exists. The 13 no-raw /
        no-writeback guard columns are pinned to literal 0.
        """
        if not job_id or not environment or not job_type or not idempotency_key:
            raise ValueError("job_id, environment, job_type and idempotency_key are required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO ai_job_queue
                    (job_id, environment, job_type, status, priority, idempotency_key,
                     source_watermark, payload_json, queued_utc, retry_count, max_retries,
                     raw_email_body_persisted, raw_document_text_persisted,
                     raw_calendar_payload_persisted, raw_procore_payload_persisted,
                     raw_prompt_persisted, raw_response_persisted, signed_url_persisted,
                     download_url_persisted, external_writeback_performed,
                     graph_writeback_performed, procore_writeback_performed,
                     email_send_performed, calendar_mutation_performed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                """,
                (
                    job_id,
                    environment,
                    job_type,
                    status,
                    int(priority),
                    idempotency_key,
                    source_watermark,
                    payload_json,
                    _utc_now(),
                    int(max_retries),
                ),
            )
            return cur.rowcount > 0

    def claim_eligible_ai_jobs(
        self,
        *,
        environment: str,
        limit: int,
        backoff_seconds: int = 0,
        now: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return queued jobs eligible to run (read-only; the caller transitions them).

        A job is eligible when ``status='queued'``, ``retry_count < max_retries``, and it has no
        prior run *or* its latest ``ai_job_runs.finished_utc`` is older than ``backoff_seconds``.
        Ordered ``priority ASC, queued_utc ASC``. Metadata only.
        """
        conn = get_connection(self._db_path)
        now_s = now or _utc_now()
        rows = conn.execute(
            """
            SELECT q.job_id, q.environment, q.job_type, q.status, q.priority,
                   q.idempotency_key, q.source_watermark, q.payload_json, q.queued_utc,
                   q.retry_count, q.max_retries, q.last_error_redacted,
                   (SELECT MAX(r.finished_utc) FROM ai_job_runs r WHERE r.job_id = q.job_id)
                       AS latest_run_finished_utc
            FROM ai_job_queue q
            WHERE q.environment = ? AND q.status = 'queued' AND q.retry_count < q.max_retries
            ORDER BY q.priority ASC, q.queued_utc ASC
            """,
            (environment,),
        ).fetchall()
        keys = (
            "job_id",
            "environment",
            "job_type",
            "status",
            "priority",
            "idempotency_key",
            "source_watermark",
            "payload_json",
            "queued_utc",
            "retry_count",
            "max_retries",
            "last_error_redacted",
            "latest_run_finished_utc",
        )
        eligible: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(keys, row, strict=True))
            last = rec.get("latest_run_finished_utc")
            if last and backoff_seconds > 0 and not _utc_older_than(last, now_s, backoff_seconds):
                continue  # within backoff window — skip until eligible
            eligible.append(rec)
            if len(eligible) >= int(limit):
                break
        return eligible

    def mark_ai_job_running(self, *, job_id: str, now: Optional[str] = None) -> bool:
        """Transition a queued job to ``running`` and stamp ``started_utc``."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                "UPDATE ai_job_queue SET status = 'running', started_utc = ? WHERE job_id = ?",
                (now or _utc_now(), job_id),
            )
            return cur.rowcount > 0

    def complete_ai_job(
        self,
        *,
        job_id: str,
        status: str,
        error_redacted: Optional[str] = None,
        increment_retry: bool = False,
        now: Optional[str] = None,
    ) -> bool:
        """Finalize a job's queue row: set status (+ optional redacted error), stamp finished_utc.

        When ``increment_retry`` is True, ``retry_count`` is bumped (used when a failed job is
        returned to ``queued`` for a backoff retry). ``error_redacted`` must be a short category
        code — never raw error text.
        """
        conn = get_connection(self._db_path)
        with transaction(conn):
            if increment_retry:
                cur = conn.execute(
                    "UPDATE ai_job_queue SET status = ?, last_error_redacted = ?, "
                    "finished_utc = ?, retry_count = retry_count + 1 WHERE job_id = ?",
                    (status, error_redacted, now or _utc_now(), job_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE ai_job_queue SET status = ?, last_error_redacted = ?, "
                    "finished_utc = ? WHERE job_id = ?",
                    (status, error_redacted, now or _utc_now(), job_id),
                )
            return cur.rowcount > 0

    def insert_ai_job_run(
        self,
        *,
        run_id: str,
        job_id: str,
        run_kind: str,
        status: str,
        dry_run: bool,
        profile_id: Optional[str] = None,
        started_utc: Optional[str] = None,
    ) -> None:
        """Open a V41 ``ai_job_runs`` receipt (metadata only; 13 guards pinned to 0)."""
        if not run_id or not job_id or not run_kind or not status:
            raise ValueError("run_id, job_id, run_kind and status are required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO ai_job_runs
                    (run_id, job_id, run_kind, status, dry_run, profile_id, started_utc,
                     raw_email_body_persisted, raw_document_text_persisted,
                     raw_calendar_payload_persisted, raw_procore_payload_persisted,
                     raw_prompt_persisted, raw_response_persisted, signed_url_persisted,
                     download_url_persisted, external_writeback_performed,
                     graph_writeback_performed, procore_writeback_performed,
                     email_send_performed, calendar_mutation_performed)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                """,
                (
                    run_id,
                    job_id,
                    run_kind,
                    status,
                    1 if dry_run else 0,
                    profile_id,
                    started_utc or _utc_now(),
                ),
            )

    def complete_ai_job_run(
        self,
        *,
        run_id: str,
        status: str,
        candidate_count: int = 0,
        accepted_count: int = 0,
        rejected_count: int = 0,
        warning_count: int = 0,
        blockers_json: str = "[]",
        finished_utc: Optional[str] = None,
    ) -> bool:
        """Finalize an ``ai_job_runs`` receipt with counts + status (no raw)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                UPDATE ai_job_runs SET
                    status = ?, finished_utc = ?, candidate_count = ?, accepted_count = ?,
                    rejected_count = ?, warning_count = ?, blockers_json = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    finished_utc or _utc_now(),
                    int(candidate_count),
                    int(accepted_count),
                    int(rejected_count),
                    int(warning_count),
                    blockers_json,
                    run_id,
                ),
            )
            return cur.rowcount > 0

    def list_ai_jobs(
        self,
        *,
        environment: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List ai_job_queue rows (metadata only; for status --list / tests)."""
        conn = get_connection(self._db_path)
        sql = (
            "SELECT job_id, environment, job_type, status, priority, idempotency_key, "
            "source_watermark, queued_utc, started_utc, finished_utc, retry_count, "
            "max_retries, last_error_redacted FROM ai_job_queue WHERE 1=1"
        )
        params: list[Any] = []
        if environment is not None:
            sql += " AND environment = ?"
            params.append(environment)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY priority ASC, queued_utc ASC LIMIT ?"
        params.append(int(limit))
        keys = (
            "job_id",
            "environment",
            "job_type",
            "status",
            "priority",
            "idempotency_key",
            "source_watermark",
            "queued_utc",
            "started_utc",
            "finished_utc",
            "retry_count",
            "max_retries",
            "last_error_redacted",
        )
        return [
            dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()
        ]

    def latest_ai_job_run(self, job_id: str) -> Optional[dict[str, Any]]:
        """Return the most recent ai_job_runs row for a job (metadata only) or None."""
        conn = get_connection(self._db_path)
        row = conn.execute(
            "SELECT run_id, job_id, run_kind, status, dry_run, profile_id, started_utc, "
            "finished_utc, candidate_count, accepted_count, rejected_count, warning_count "
            "FROM ai_job_runs WHERE job_id = ? ORDER BY started_utc DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        keys = (
            "run_id",
            "job_id",
            "run_kind",
            "status",
            "dry_run",
            "profile_id",
            "started_utc",
            "finished_utc",
            "candidate_count",
            "accepted_count",
            "rejected_count",
            "warning_count",
        )
        rec = dict(zip(keys, row, strict=True))
        rec["dry_run"] = bool(rec["dry_run"])
        return rec

    def list_task_candidates(
        self,
        *,
        project_key: Optional[str] = None,
        review_status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List task candidates (for tests/evidence). Safe fields only."""
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if review_status is not None:
            clauses.append("review_status = ?")
            params.append(review_status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT candidate_id, stable_key, title_redacted, project_key, assignee_class,
                   due_at_utc, urgency, waiting_state, safety_category, confidence,
                   reason_redacted, recommended_next_action, review_status,
                   model_profile_id, prompt_template_version, created_utc, updated_utc,
                   snoozed_until_utc, reviewed_utc, reviewed_by, review_note_redacted
            FROM task_candidates {where}
            ORDER BY created_utc DESC
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "candidate_id",
            "stable_key",
            "title_redacted",
            "project_key",
            "assignee_class",
            "due_at_utc",
            "urgency",
            "waiting_state",
            "safety_category",
            "confidence",
            "reason_redacted",
            "recommended_next_action",
            "review_status",
            "model_profile_id",
            "prompt_template_version",
            "created_utc",
            "updated_utc",
            # V43 candidate-review lifecycle columns (additive).
            "snoozed_until_utc",
            "reviewed_utc",
            "reviewed_by",
            "review_note_redacted",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_commitment_candidates(
        self,
        *,
        project_key: Optional[str] = None,
        review_status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List commitment candidates (for tests/evidence). Safe fields only."""
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if review_status is not None:
            clauses.append("review_status = ?")
            params.append(review_status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT candidate_id, stable_key, title_redacted, project_key, commitment_actor_class,
                   promised_at_utc, due_at_utc, urgency, waiting_state, safety_category, confidence,
                   reason_redacted, recommended_next_action, review_status,
                   model_profile_id, prompt_template_version, created_utc, updated_utc,
                   snoozed_until_utc, reviewed_utc, reviewed_by, review_note_redacted
            FROM commitment_candidates {where}
            ORDER BY created_utc DESC
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "candidate_id",
            "stable_key",
            "title_redacted",
            "project_key",
            "commitment_actor_class",
            "promised_at_utc",
            "due_at_utc",
            "urgency",
            "waiting_state",
            "safety_category",
            "confidence",
            "reason_redacted",
            "recommended_next_action",
            "review_status",
            "model_profile_id",
            "prompt_template_version",
            "created_utc",
            "updated_utc",
            # V43 candidate-review lifecycle columns (additive).
            "snoozed_until_utc",
            "reviewed_utc",
            "reviewed_by",
            "review_note_redacted",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def list_candidate_source_refs(
        self,
        *,
        candidate_id: Optional[str] = None,
        candidate_type: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List source refs for Phase 10 candidates (for tests/evidence). Includes evidence_redacted excerpts."""
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if candidate_id is not None:
            clauses.append("candidate_id = ?")
            params.append(candidate_id)
        if candidate_type is not None:
            clauses.append("candidate_type = ?")
            params.append(candidate_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT source_ref_id, candidate_type, candidate_id, source_family,
                   source_ref_hash, source_table, source_primary_key_hash,
                   evidence_redacted, created_utc
            FROM candidate_source_refs {where}
            ORDER BY created_utc DESC
            LIMIT ?
            """,
            tuple(params),
        )
        keys = (
            "source_ref_id",
            "candidate_type",
            "candidate_id",
            "source_family",
            "source_ref_hash",
            "source_table",
            "source_primary_key_hash",
            "evidence_redacted",
            "created_utc",
        )
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    # --- Phase 10/10A candidate review helpers (additive) ---
    # Support operator review of V41/V43 task/commitment candidates (read + review
    # state transitions + audit). Read methods return only redacted/safe columns
    # (never the guard columns); source refs are accessed via
    # list_candidate_source_refs and are never mutated here.
    # -------------------------------------------------------------------------

    # Safe, review-relevant column projections (mirror the list_* methods, incl. V43).
    _TASK_CANDIDATE_COLUMNS = (
        "candidate_id, stable_key, title_redacted, project_key, assignee_class, "
        "due_at_utc, urgency, waiting_state, safety_category, confidence, "
        "reason_redacted, recommended_next_action, review_status, model_profile_id, "
        "prompt_template_version, created_utc, updated_utc, snoozed_until_utc, "
        "reviewed_utc, reviewed_by, review_note_redacted"
    )
    _COMMITMENT_CANDIDATE_COLUMNS = (
        "candidate_id, stable_key, title_redacted, project_key, commitment_actor_class, "
        "promised_at_utc, due_at_utc, urgency, waiting_state, safety_category, confidence, "
        "reason_redacted, recommended_next_action, review_status, model_profile_id, "
        "prompt_template_version, created_utc, updated_utc, snoozed_until_utc, "
        "reviewed_utc, reviewed_by, review_note_redacted"
    )

    def get_task_candidate(self, candidate_id: str) -> Optional[dict[str, Any]]:
        """Return a single task candidate by id (safe fields only), or None."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {self._TASK_CANDIDATE_COLUMNS} FROM task_candidates "
            "WHERE candidate_id = ? LIMIT 1",
            (candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row, strict=True))

    def get_commitment_candidate(self, candidate_id: str) -> Optional[dict[str, Any]]:
        """Return a single commitment candidate by id (safe fields only), or None."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {self._COMMITMENT_CANDIDATE_COLUMNS} FROM commitment_candidates "
            "WHERE candidate_id = ? LIMIT 1",
            (candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row, strict=True))

    def get_candidate(
        self, candidate_id: str, *, candidate_type: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Return a candidate by id, tagged with candidate_type, or None.

        If candidate_type is given, only that table is checked; otherwise task is
        tried first, then commitment.
        """
        if candidate_type == "task":
            row = self.get_task_candidate(candidate_id)
            return {**row, "candidate_type": "task"} if row else None
        if candidate_type == "commitment":
            row = self.get_commitment_candidate(candidate_id)
            return {**row, "candidate_type": "commitment"} if row else None
        row = self.get_task_candidate(candidate_id)
        if row:
            return {**row, "candidate_type": "task"}
        row = self.get_commitment_candidate(candidate_id)
        if row:
            return {**row, "candidate_type": "commitment"}
        return None

    def list_review_candidates(
        self,
        *,
        status: Optional[str] = None,
        project_key: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Merged task + commitment candidates (each tagged with candidate_type).

        Applies the same project_key/review_status filters as the per-type list
        methods, concatenates, and caps the combined result to ``limit``.
        """
        merged: list[dict[str, Any]] = []
        for ctype, rows in (
            (
                "task",
                self.list_task_candidates(
                    project_key=project_key, review_status=status, limit=limit
                ),
            ),
            (
                "commitment",
                self.list_commitment_candidates(
                    project_key=project_key, review_status=status, limit=limit
                ),
            ),
        ):
            for r in rows:
                r["candidate_type"] = ctype
                merged.append(r)
        return merged[:limit]

    def update_candidate_review_state(
        self,
        *,
        candidate_type: str,
        candidate_id: str,
        review_status: str,
        reviewed_utc: Optional[str] = None,
        reviewed_by: Optional[str] = None,
        review_note_redacted: Optional[str] = None,
        snoozed_until_utc: Optional[str] = None,
    ) -> bool:
        """Set review_status on a task or commitment candidate. Returns True if a row was updated.

        Always sets review_status + updated_utc. The optional V43 review-lifecycle
        columns (reviewed_utc/reviewed_by/review_note_redacted/snoozed_until_utc) are
        written only when explicitly provided, so legacy 3-arg callers are unchanged.
        """
        if candidate_type not in ("task", "commitment"):
            return False
        table = "task_candidates" if candidate_type == "task" else "commitment_candidates"
        sets = ["review_status = ?", "updated_utc = ?"]
        params: list[Any] = [review_status, _utc_now()]
        for column, value in (
            ("reviewed_utc", reviewed_utc),
            ("reviewed_by", reviewed_by),
            ("review_note_redacted", review_note_redacted),
            ("snoozed_until_utc", snoozed_until_utc),
        ):
            if value is not None:
                sets.append(f"{column} = ?")
                params.append(value)
        params.append(candidate_id)
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                f"UPDATE {table} SET {', '.join(sets)} WHERE candidate_id = ?",
                tuple(params),
            )
            return cur.rowcount > 0

    # Columns an operator may edit on a candidate row (never stable_key, source refs,
    # or guard columns). assignee maps to the type-specific actor column.
    _EDITABLE_CANDIDATE_COLUMNS = frozenset(
        {"title_redacted", "assignee_class", "commitment_actor_class", "waiting_state"}
    )

    def update_candidate_fields(
        self,
        *,
        candidate_type: str,
        candidate_id: str,
        fields: dict[str, str],
    ) -> bool:
        """Targeted UPDATE of editable candidate fields. Returns True if a row was updated.

        Only whitelisted columns (_EDITABLE_CANDIDATE_COLUMNS) are written; any other
        key is ignored. Always bumps updated_utc. Never touches stable_key, review
        status, source refs, or guard columns.
        """
        if candidate_type not in ("task", "commitment"):
            return False
        table = "task_candidates" if candidate_type == "task" else "commitment_candidates"
        allowed = {
            col: val for col, val in fields.items() if col in self._EDITABLE_CANDIDATE_COLUMNS
        }
        if not allowed:
            return False
        sets = [f"{col} = ?" for col in allowed]
        params: list[Any] = list(allowed.values())
        sets.append("updated_utc = ?")
        params.append(_utc_now())
        params.append(candidate_id)
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                f"UPDATE {table} SET {', '.join(sets)} WHERE candidate_id = ?",
                tuple(params),
            )
            return cur.rowcount > 0

    def insert_candidate_review_event(
        self,
        *,
        candidate_type: str,
        candidate_id: str,
        decision: str,
        reason_redacted: Optional[str] = None,
        reviewer_ref: str = "operator",
        prior_status: Optional[str] = None,
        new_status: Optional[str] = None,
        changes_json_redacted: Optional[str] = None,
        snoozed_until_utc: Optional[str] = None,
    ) -> str:
        """Insert an audit row for a candidate review decision and return its id.

        Columns match the actual candidate_review_events schema (V41 + V43): the
        ``decision`` param maps to ``action`` and ``reason_redacted`` to
        ``user_note_redacted``. The review event is required evidence, not optional
        telemetry — failures are NOT swallowed; they propagate to the caller.
        """
        review_event_id = str(uuid.uuid4())
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO candidate_review_events
                    (review_event_id, candidate_type, candidate_id, action,
                     prior_status, new_status, user_note_redacted, reviewer_ref,
                     changes_json_redacted, snoozed_until_utc, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_event_id,
                    candidate_type,
                    candidate_id,
                    decision,
                    prior_status,
                    new_status,
                    reason_redacted,
                    reviewer_ref,
                    changes_json_redacted,
                    snoozed_until_utc,
                    _utc_now(),
                ),
            )
        return review_event_id

    # --- Phase 10 acceptance promotion + follow-up watch (additive) ---------
    # Promotion: an explicitly-accepted candidate is copied into accepted_tasks /
    # accepted_commitments (safe fields only; the 13 _P10_GUARDS columns are never
    # written and stay DEFAULT 0 / CHECK(=0)). Idempotent: the accepted row id is
    # derived deterministically from candidate_id, so re-promotion DOES NOTHING.
    # Follow-up watch: deterministic advisory monitor over the accepted items; it
    # only ever writes follow_up_watch_items + follow_up_status_events (guards 0).
    # No raw bodies, no writeback — only redacted titles/excerpts and hashes move.
    # ------------------------------------------------------------------------

    @staticmethod
    def accepted_task_id_for(candidate_id: str) -> str:
        """Deterministic accepted_tasks id for a candidate (idempotent promotion key)."""
        return f"acc-task:{candidate_id}"

    @staticmethod
    def accepted_commitment_id_for(candidate_id: str) -> str:
        """Deterministic accepted_commitments id for a candidate (idempotent promotion key)."""
        return f"acc-commit:{candidate_id}"

    def insert_accepted_task(
        self,
        *,
        candidate_id: str,
        title_redacted: str,
        waiting_state: str,
        safety_category: str,
        project_key: Optional[str] = None,
        status: str = "open",
        due_at_utc: Optional[str] = None,
        accepted_utc: Optional[str] = None,
    ) -> bool:
        """Promote a task candidate into accepted_tasks. Returns True if a row was inserted.

        Idempotent: the row id is derived from candidate_id, so a repeat call is a
        no-op (ON CONFLICT DO NOTHING). Guard columns are omitted → DEFAULT 0.
        """
        if not candidate_id or not title_redacted:
            raise ValueError("candidate_id and title_redacted are required")
        accepted_task_id = self.accepted_task_id_for(candidate_id)
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO accepted_tasks
                    (accepted_task_id, candidate_id, title_redacted, project_key,
                     status, due_at_utc, waiting_state, safety_category, accepted_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(accepted_task_id) DO NOTHING
                """,
                (
                    accepted_task_id,
                    candidate_id,
                    title_redacted,
                    project_key,
                    status,
                    due_at_utc,
                    waiting_state,
                    safety_category,
                    accepted_utc or _utc_now(),
                ),
            )
            return cur.rowcount > 0

    def insert_accepted_commitment(
        self,
        *,
        candidate_id: str,
        title_redacted: str,
        waiting_state: str,
        safety_category: str,
        project_key: Optional[str] = None,
        status: str = "open",
        due_at_utc: Optional[str] = None,
        accepted_utc: Optional[str] = None,
    ) -> bool:
        """Promote a commitment candidate into accepted_commitments. Returns True if inserted.

        Idempotent (deterministic id, ON CONFLICT DO NOTHING). Guards omitted → DEFAULT 0.
        """
        if not candidate_id or not title_redacted:
            raise ValueError("candidate_id and title_redacted are required")
        accepted_commitment_id = self.accepted_commitment_id_for(candidate_id)
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO accepted_commitments
                    (accepted_commitment_id, candidate_id, title_redacted, project_key,
                     status, due_at_utc, waiting_state, safety_category, accepted_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(accepted_commitment_id) DO NOTHING
                """,
                (
                    accepted_commitment_id,
                    candidate_id,
                    title_redacted,
                    project_key,
                    status,
                    due_at_utc,
                    waiting_state,
                    safety_category,
                    accepted_utc or _utc_now(),
                ),
            )
            return cur.rowcount > 0

    def list_accepted_tasks(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """List accepted tasks (safe fields only) — input for the follow-up watch agent."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT accepted_task_id, candidate_id, title_redacted, project_key, status,
                   due_at_utc, waiting_state, safety_category, accepted_utc, completed_utc
            FROM accepted_tasks
            ORDER BY accepted_utc DESC
            LIMIT ?
            """,
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def list_accepted_commitments(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """List accepted commitments (safe fields only) — input for the follow-up watch agent."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT accepted_commitment_id, candidate_id, title_redacted, project_key, status,
                   due_at_utc, waiting_state, safety_category, accepted_utc, completed_utc
            FROM accepted_commitments
            ORDER BY accepted_utc DESC
            LIMIT ?
            """,
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def list_follow_up_watch_items(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """List follow-up watch items (safe fields only)."""
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT watch_item_id, accepted_task_id, accepted_commitment_id, project_key,
                   watch_status, waiting_state, next_check_utc, last_checked_utc,
                   stale_after_utc, reason_redacted, created_utc
            FROM follow_up_watch_items
            ORDER BY created_utc DESC
            LIMIT ?
            """,
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def upsert_follow_up_watch_item(
        self,
        *,
        watch_item_id: str,
        watch_status: str,
        waiting_state: str,
        accepted_task_id: Optional[str] = None,
        accepted_commitment_id: Optional[str] = None,
        project_key: Optional[str] = None,
        next_check_utc: Optional[str] = None,
        last_checked_utc: Optional[str] = None,
        stale_after_utc: Optional[str] = None,
        reason_redacted: Optional[str] = None,
    ) -> None:
        """Upsert a follow-up watch item (advisory). Idempotent by watch_item_id.

        created_utc is preserved on update; guard columns are never written so the
        CHECK(=0) invariants hold.
        """
        if not watch_item_id:
            raise ValueError("watch_item_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO follow_up_watch_items
                    (watch_item_id, accepted_task_id, accepted_commitment_id, project_key,
                     watch_status, waiting_state, next_check_utc, last_checked_utc,
                     stale_after_utc, reason_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(watch_item_id) DO UPDATE SET
                    project_key = excluded.project_key,
                    watch_status = excluded.watch_status,
                    waiting_state = excluded.waiting_state,
                    next_check_utc = excluded.next_check_utc,
                    last_checked_utc = excluded.last_checked_utc,
                    stale_after_utc = excluded.stale_after_utc,
                    reason_redacted = excluded.reason_redacted
                """,
                (
                    watch_item_id,
                    accepted_task_id,
                    accepted_commitment_id,
                    project_key,
                    watch_status,
                    waiting_state,
                    next_check_utc,
                    last_checked_utc,
                    stale_after_utc,
                    reason_redacted,
                ),
            )

    def insert_follow_up_status_event(
        self,
        *,
        watch_item_id: str,
        new_status: str,
        prior_status: Optional[str] = None,
        signal_type: str = "deterministic_scan",
        source_ref_hash: Optional[str] = None,
        evidence_redacted: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> str:
        """Insert a follow-up status event (audit of a watch_status change). Returns its id.

        Carries only a source_ref_hash + already-redacted excerpt — never raw content.
        Guard columns omitted → DEFAULT 0.
        """
        if not watch_item_id or not new_status:
            raise ValueError("watch_item_id and new_status are required")
        status_event_id = str(uuid.uuid4())
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO follow_up_status_events
                    (status_event_id, watch_item_id, prior_status, new_status,
                     signal_type, source_ref_hash, evidence_redacted, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    status_event_id,
                    watch_item_id,
                    prior_status,
                    new_status,
                    signal_type,
                    source_ref_hash,
                    evidence_redacted,
                    confidence,
                ),
            )
        return status_event_id

    # --- Phase 10 email follow-up raw enrichment (V45, additive) ------------
    # Review-safe destination for model-enriched follow-up metadata derived from a bounded,
    # sanitized, NON-persisted local raw email window. Persists ONLY structured/redacted enriched
    # fields + SHA-256[:12] hashes + source refs. No raw body, prompt, response, HTML, URL, token,
    # or secret can flow through these methods. Guard columns omitted → DEFAULT 0 / CHECK(=0).
    # Idempotent by idempotency_key (re-enrichment updates in place; operator review_status is
    # preserved on update). V1-V44 read models untouched.
    # -----------------------------------------------------------------------

    _EMAIL_FOLLOWUP_ENRICHMENT_COLUMNS = (
        "enrichment_id, idempotency_key, source_candidate_id, source_candidate_type, "
        "watch_item_id, email_thread_ref_hash, email_message_ref_hashes_json, raw_excerpt_hash, "
        "enriched_title, waiting_state, assignee_type, assignee_display, suggested_next_action, "
        "due_at_utc, confidence, confidence_band, reason_codes_json, source_refs_json, "
        "review_status, model_task, model_profile_id, prompt_template_version, "
        "input_context_hash, output_hash, created_utc, updated_utc"
    )

    def upsert_email_followup_enrichment(
        self,
        *,
        enrichment_id: str,
        idempotency_key: str,
        source_candidate_id: str,
        source_candidate_type: str,
        raw_excerpt_hash: str,
        enriched_title: str,
        waiting_state: str,
        assignee_type: str,
        confidence: float,
        confidence_band: str,
        input_context_hash: str,
        output_hash: str,
        prompt_template_version: str,
        watch_item_id: Optional[str] = None,
        email_thread_ref_hash: Optional[str] = None,
        email_message_ref_hashes: Optional[list[str]] = None,
        assignee_display: Optional[str] = None,
        suggested_next_action: Optional[str] = None,
        due_at_utc: Optional[str] = None,
        reason_codes: Optional[list[str]] = None,
        source_refs: Optional[list[str]] = None,
        review_status: str = "pending",
        model_task: str = "email_followup_raw_enrichment",
        model_profile_id: Optional[str] = None,
    ) -> str:
        """Upsert a review-safe V45 ``email_followup_enrichments`` row. Returns 'inserted'|'updated'.

        Idempotent by ``idempotency_key``: re-enriching the same (candidate, refs, raw excerpt,
        task, template, schema) updates the existing row's structured fields in place instead of
        creating a duplicate. ``review_status`` is set on insert only and preserved on update so an
        operator decision is never silently reset. Persists ONLY structured/redacted fields, hashes,
        and source refs — guard columns are omitted so the CHECK(=0) invariants hold.
        """
        if not enrichment_id or not idempotency_key or not source_candidate_id:
            raise ValueError("enrichment_id, idempotency_key and source_candidate_id are required")
        if not raw_excerpt_hash or not input_context_hash or not output_hash:
            raise ValueError(
                "raw_excerpt_hash, input_context_hash and output_hash are required"
            )
        msg_hashes_json = json.dumps(list(email_message_ref_hashes or []), sort_keys=True)
        reasons_json = json.dumps(list(reason_codes or []), sort_keys=True)
        refs_json = json.dumps(list(source_refs or []), sort_keys=True)
        now = _utc_now()
        conn = get_connection(self._db_path)
        with transaction(conn):
            existing = conn.execute(
                "SELECT enrichment_id FROM email_followup_enrichments WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                conn.execute(
                    """
                    UPDATE email_followup_enrichments SET
                        source_candidate_id = ?, source_candidate_type = ?, watch_item_id = ?,
                        email_thread_ref_hash = ?, email_message_ref_hashes_json = ?,
                        raw_excerpt_hash = ?, enriched_title = ?, waiting_state = ?,
                        assignee_type = ?, assignee_display = ?, suggested_next_action = ?,
                        due_at_utc = ?, confidence = ?, confidence_band = ?, reason_codes_json = ?,
                        source_refs_json = ?, model_task = ?, model_profile_id = ?,
                        prompt_template_version = ?, input_context_hash = ?, output_hash = ?,
                        updated_utc = ?
                    WHERE idempotency_key = ?
                    """,
                    (
                        source_candidate_id,
                        source_candidate_type,
                        watch_item_id,
                        email_thread_ref_hash,
                        msg_hashes_json,
                        raw_excerpt_hash,
                        enriched_title,
                        waiting_state,
                        assignee_type,
                        assignee_display,
                        suggested_next_action,
                        due_at_utc,
                        confidence,
                        confidence_band,
                        reasons_json,
                        refs_json,
                        model_task,
                        model_profile_id,
                        prompt_template_version,
                        input_context_hash,
                        output_hash,
                        now,
                        idempotency_key,
                    ),
                )
                return "updated"
            conn.execute(
                """
                INSERT INTO email_followup_enrichments
                    (enrichment_id, idempotency_key, source_candidate_id, source_candidate_type,
                     watch_item_id, email_thread_ref_hash, email_message_ref_hashes_json,
                     raw_excerpt_hash, enriched_title, waiting_state, assignee_type,
                     assignee_display, suggested_next_action, due_at_utc, confidence,
                     confidence_band, reason_codes_json, source_refs_json, review_status,
                     model_task, model_profile_id, prompt_template_version, input_context_hash,
                     output_hash, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?)
                """,
                (
                    enrichment_id,
                    idempotency_key,
                    source_candidate_id,
                    source_candidate_type,
                    watch_item_id,
                    email_thread_ref_hash,
                    msg_hashes_json,
                    raw_excerpt_hash,
                    enriched_title,
                    waiting_state,
                    assignee_type,
                    assignee_display,
                    suggested_next_action,
                    due_at_utc,
                    confidence,
                    confidence_band,
                    reasons_json,
                    refs_json,
                    review_status,
                    model_task,
                    model_profile_id,
                    prompt_template_version,
                    input_context_hash,
                    output_hash,
                    now,
                    now,
                ),
            )
        return "inserted"

    def list_email_followup_enrichments(
        self,
        *,
        review_status: Optional[str] = None,
        source_candidate_id: Optional[str] = None,
        watch_item_id: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List review-safe V45 enrichment rows (safe columns only; JSON parsed to lists).

        Never returns the guard columns. Used by the daily brief (``review_status='pending'``) and
        by tests/evidence. Returns structured/redacted fields + hashes + source refs only.
        """
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if review_status is not None:
            clauses.append("review_status = ?")
            params.append(review_status)
        if source_candidate_id is not None:
            clauses.append("source_candidate_id = ?")
            params.append(source_candidate_id)
        if watch_item_id is not None:
            clauses.append("watch_item_id = ?")
            params.append(watch_item_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"SELECT {self._EMAIL_FOLLOWUP_ENRICHMENT_COLUMNS} FROM email_followup_enrichments "
            f"{where} ORDER BY created_utc DESC LIMIT ?",
            tuple(params),
        )
        cols = [d[0] for d in cur.description]
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row, strict=True))
            for jk in (
                "email_message_ref_hashes_json",
                "reason_codes_json",
                "source_refs_json",
            ):
                try:
                    rec[jk.replace("_json", "")] = self._load_json(rec[jk]) or []
                except Exception:
                    rec[jk.replace("_json", "")] = []
            results.append(rec)
        return results

    def count_email_followup_enrichments(self, *, review_status: Optional[str] = None) -> int:
        """Count V45 enrichment rows (optionally by review_status)."""
        conn = get_connection(self._db_path)
        if review_status is None:
            cur = conn.execute("SELECT COUNT(*) FROM email_followup_enrichments")
        else:
            cur = conn.execute(
                "SELECT COUNT(*) FROM email_followup_enrichments WHERE review_status = ?",
                (review_status,),
            )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    # --- Phase 10 daily-brief action candidates (additive) -----------------
    # Destination for advisory digest/synthesis candidates (e.g. the Procore
    # action-signal digest and the daily-brief synthesis layer). Rollup rows only:
    # redacted titles + reason codes + safe enums — never raw bodies. Guard columns
    # omitted → DEFAULT 0 / CHECK(=0). Idempotent on a deterministic id.
    # -----------------------------------------------------------------------

    @staticmethod
    def daily_brief_action_candidate_id_for(brief_date: str, section: str, group_key: str) -> str:
        """Deterministic id for a daily-brief action candidate (idempotent upsert key)."""
        digest = hashlib.sha256(f"{brief_date}|{section}|{group_key}".encode()).hexdigest()[:32]
        return f"dbac-{digest}"

    def insert_daily_brief_action_candidate(
        self,
        *,
        brief_date: str,
        section: str,
        title_redacted: str,
        confidence: float,
        project_key: Optional[str] = None,
        priority: int = 100,
        status: str = "candidate",
        reason_redacted: Optional[str] = None,
        recommended_next_action: Optional[str] = None,
        daily_brief_action_candidate_id: Optional[str] = None,
        group_key: Optional[str] = None,
    ) -> bool:
        """Insert a daily-brief action candidate. Returns True if a row was inserted.

        Idempotent: the id is derived from (brief_date, section, group_key) unless one is
        supplied, so a repeat call is a no-op (ON CONFLICT DO NOTHING). Guard columns are
        omitted → DEFAULT 0 / CHECK(=0).
        """
        if not brief_date or not section or not title_redacted:
            raise ValueError("brief_date, section and title_redacted are required")
        row_id = daily_brief_action_candidate_id or self.daily_brief_action_candidate_id_for(
            brief_date, section, group_key or title_redacted
        )
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO daily_brief_action_candidates
                    (daily_brief_action_candidate_id, brief_date, section, title_redacted,
                     project_key, priority, status, confidence, reason_redacted,
                     recommended_next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(daily_brief_action_candidate_id) DO NOTHING
                """,
                (
                    row_id,
                    brief_date,
                    section,
                    title_redacted,
                    project_key,
                    priority,
                    status,
                    confidence,
                    reason_redacted,
                    recommended_next_action,
                ),
            )
            return cur.rowcount > 0

    def list_daily_brief_action_candidates(
        self,
        *,
        brief_date: Optional[str] = None,
        section: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List daily-brief action candidates (safe fields only)."""
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if brief_date is not None:
            clauses.append("brief_date = ?")
            params.append(brief_date)
        if section is not None:
            clauses.append("section = ?")
            params.append(section)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT daily_brief_action_candidate_id, brief_date, section, title_redacted,
                   project_key, priority, status, confidence, reason_redacted,
                   recommended_next_action, created_utc
            FROM daily_brief_action_candidates {where}
            ORDER BY priority ASC, created_utc DESC
            LIMIT ?
            """,
            tuple(params),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    # V41 Phase 10 — relationship candidates (deterministic, source-linked, redacted)
    # Persists only hashed source refs + safe reason codes. Guard columns are omitted on
    # INSERT → DEFAULT 0 / CHECK(=0). No raw subjects, bodies, addresses, URLs, or payloads.
    # -------------------------------------------------------------------------

    def insert_phase10_relationship_candidate(
        self,
        *,
        relationship_candidate_id: str,
        from_source_family: str,
        from_source_ref_hash: str,
        to_source_family: str,
        to_source_ref_hash: str,
        relationship_type: str,
        confidence: float,
        confidence_class: str,
        project_key: Optional[str] = None,
        deterministic: bool = True,
        model_proposed: bool = False,
        review_status: str = "pending",
        reason_redacted: Optional[str] = None,
    ) -> bool:
        """Insert a relationship candidate. Returns True if a row was inserted.

        Idempotent: ``relationship_candidate_id`` is the PK, so a repeat call is a no-op
        (ON CONFLICT DO NOTHING). Guard columns are omitted → DEFAULT 0 / CHECK(=0).
        """
        if not relationship_candidate_id:
            raise ValueError("relationship_candidate_id is required")
        if not from_source_family or not to_source_family or not relationship_type:
            raise ValueError("source families and relationship_type are required")
        if not from_source_ref_hash or not to_source_ref_hash:
            raise ValueError("source ref hashes are required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO phase10_relationship_candidates
                    (relationship_candidate_id, from_source_family, from_source_ref_hash,
                     to_source_family, to_source_ref_hash, relationship_type, project_key,
                     confidence, confidence_class, deterministic, model_proposed,
                     review_status, reason_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relationship_candidate_id) DO NOTHING
                """,
                (
                    relationship_candidate_id,
                    from_source_family,
                    from_source_ref_hash,
                    to_source_family,
                    to_source_ref_hash,
                    relationship_type,
                    project_key,
                    float(confidence),
                    confidence_class,
                    1 if deterministic else 0,
                    1 if model_proposed else 0,
                    review_status,
                    reason_redacted,
                ),
            )
            return cur.rowcount > 0

    def list_phase10_relationship_candidate_ids(self) -> set[str]:
        """Return the set of existing relationship_candidate_id values (idempotency check)."""
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT relationship_candidate_id FROM phase10_relationship_candidates")
        return {str(row[0]) for row in cur.fetchall()}

    def list_phase10_relationship_candidates(
        self,
        *,
        project_key: Optional[str] = None,
        relationship_type: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """List relationship candidates (safe fields only) in deterministic order.

        Order: confidence DESC, then relationship_candidate_id ASC (stable tie-break).
        """
        conn = get_connection(self._db_path)
        clauses: list[str] = []
        params: list[Any] = []
        if project_key is not None:
            clauses.append("project_key = ?")
            params.append(project_key)
        if relationship_type is not None:
            clauses.append("relationship_type = ?")
            params.append(relationship_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = conn.execute(
            f"""
            SELECT relationship_candidate_id, from_source_family, from_source_ref_hash,
                   to_source_family, to_source_ref_hash, relationship_type, project_key,
                   confidence, confidence_class, deterministic, model_proposed,
                   review_status, reason_redacted, created_utc
            FROM phase10_relationship_candidates {where}
            ORDER BY confidence DESC, relationship_candidate_id ASC
            LIMIT ?
            """,
            tuple(params),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def count_phase10_relationship_candidates(self) -> int:
        """Return the total relationship-candidate row count."""
        conn = get_connection(self._db_path)
        cur = conn.execute("SELECT COUNT(*) FROM phase10_relationship_candidates")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    # V20 Phase 07A Prompt 01 — Data Quality + Canonical Source-Record Map
    # All adapters enforce the guardrail flags=False at the Python layer (defense
    # in depth with the schema CHECKs). No raw bodies, full text, or writeback.
    # -------------------------------------------------------------------------

    def insert_data_quality_run(
        self,
        *,
        run_id: str,
        phase: str,
        started_utc: str,
        status: str,
        repo_sha: Optional[str] = None,
        schema_version: Optional[int] = None,
        summary_json: Optional[str] = None,
    ) -> None:
        """Record a data-quality evaluation run (idempotent on run_id)."""
        if not run_id:
            raise ValueError("run_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT OR REPLACE INTO construction_data_quality_runs
                (run_id, phase, started_utc, completed_utc, status, repo_sha, schema_version, summary_json,
                 raw_body_persisted, external_writeback_performed)
                VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 0, 0)
                """,
                (run_id, phase, started_utc, status, repo_sha, schema_version, summary_json),
            )

    def upsert_table_lifecycle_registry(self, row: dict[str, Any]) -> None:
        """Upsert a table lifecycle classification row (PK = table_name)."""
        table_name = row.get("table_name")
        if not table_name:
            raise ValueError("table_name is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT OR REPLACE INTO construction_table_lifecycle_registry
                (table_name, table_family, lifecycle_status, expected_population_status,
                 phase_owner, blocking_for_phase, notes_redacted, last_audited_run_id, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    table_name,
                    row.get("table_family"),
                    row.get("lifecycle_status"),
                    row.get("expected_population_status"),
                    row.get("phase_owner"),
                    row.get("blocking_for_phase"),
                    row.get("notes_redacted"),
                    row.get("last_audited_run_id"),
                    _utc_now(),
                ),
            )

    def upsert_source_system_record(self, rec: dict[str, Any]) -> str:
        """Upsert a canonical source-system record. Returns canonical_record_id.
        Adapter-enforced: raw_body_persisted=0, full_text_persisted=0, external_writeback=0.
        """
        for flag in ("raw_body_persisted", "full_text_persisted", "external_writeback_performed"):
            if rec.get(flag) not in (None, False, 0):
                raise ValueError(
                    f"{flag} must be False — Phase 07A source_system_record_map never persists raw content or performs writeback"
                )
        canonical_id = rec.get("canonical_record_id")
        if not canonical_id:
            raise ValueError("canonical_record_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO source_system_record_map
                (canonical_record_id, project_key, project_number, source_system, source_table,
                 source_primary_key, record_type, record_status, title_redacted, source_url_redacted,
                 first_seen_utc, last_seen_utc, source_updated_utc, confidence_class, review_required,
                 mapping_signals_json, raw_body_persisted, full_text_persisted, external_writeback_performed,
                 created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
                ON CONFLICT(source_system, source_table, source_primary_key) DO UPDATE SET
                    project_key=excluded.project_key,
                    project_number=excluded.project_number,
                    record_type=excluded.record_type,
                    record_status=excluded.record_status,
                    title_redacted=excluded.title_redacted,
                    source_url_redacted=excluded.source_url_redacted,
                    last_seen_utc=excluded.last_seen_utc,
                    source_updated_utc=excluded.source_updated_utc,
                    confidence_class=excluded.confidence_class,
                    review_required=excluded.review_required,
                    mapping_signals_json=excluded.mapping_signals_json,
                    updated_utc=excluded.updated_utc
                """,
                (
                    canonical_id,
                    rec.get("project_key"),
                    rec.get("project_number"),
                    rec.get("source_system"),
                    rec.get("source_table"),
                    rec.get("source_primary_key"),
                    rec.get("record_type"),
                    rec.get("record_status"),
                    rec.get("title_redacted"),
                    rec.get("source_url_redacted"),
                    rec.get("first_seen_utc"),
                    rec.get("last_seen_utc"),
                    rec.get("source_updated_utc"),
                    rec.get("confidence_class"),
                    1 if rec.get("review_required") else 0,
                    rec.get("mapping_signals_json"),
                    _utc_now(),
                    _utc_now(),
                ),
            )
        return canonical_id

    def insert_relationship_resolution_candidate(self, rel: dict[str, Any]) -> str:
        """Insert (or upsert) a relationship candidate/queue row. Returns relationship_id.
        Enforces guardrail flags at adapter layer.
        """
        for flag in ("raw_body_persisted", "full_text_persisted"):
            if rel.get(flag) not in (None, False, 0):
                raise ValueError(
                    f"{flag} must be False — Phase 07A relationship_resolution_queue never persists raw content"
                )
        relationship_id = rel.get("relationship_id")
        if not relationship_id:
            raise ValueError("relationship_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT OR REPLACE INTO relationship_resolution_queue
                (relationship_id, from_canonical_record_id, to_canonical_record_id,
                 from_source_system, to_source_system, relationship_type, relationship_status,
                 confidence_class, confidence, evidence_redacted, review_required,
                 promotion_status, rejection_reason, raw_body_persisted, full_text_persisted,
                 created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                """,
                (
                    relationship_id,
                    rel.get("from_canonical_record_id"),
                    rel.get("to_canonical_record_id"),
                    rel.get("from_source_system"),
                    rel.get("to_source_system"),
                    rel.get("relationship_type"),
                    rel.get("relationship_status"),
                    rel.get("confidence_class"),
                    rel.get("confidence"),
                    rel.get("evidence_redacted"),
                    1 if rel.get("review_required") else 0,
                    rel.get("promotion_status") or "not_promoted",
                    rel.get("rejection_reason"),
                    _utc_now(),
                    _utc_now(),
                ),
            )
        return relationship_id

    def upsert_project_source_coverage(self, cov: dict[str, Any]) -> None:
        """Upsert a project source coverage mart row (PK coverage_id)."""
        coverage_id = cov.get("coverage_id")
        if not coverage_id:
            raise ValueError("coverage_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT OR REPLACE INTO project_source_coverage_mart
                (coverage_id, run_id, project_key, project_number, source_domain,
                 record_count, mapped_count, unmapped_count, relationship_count, orphan_count,
                 quality_status, blocking_reasons_json, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coverage_id,
                    cov.get("run_id"),
                    cov.get("project_key"),
                    cov.get("project_number"),
                    cov.get("source_domain"),
                    cov.get("record_count", 0),
                    cov.get("mapped_count", 0),
                    cov.get("unmapped_count", 0),
                    cov.get("relationship_count", 0),
                    cov.get("orphan_count", 0),
                    cov.get("quality_status"),
                    cov.get("blocking_reasons_json"),
                    _utc_now(),
                ),
            )

    # --- Prompt 05 agent-ready query marts (additive, follow coverage pattern) ---

    def upsert_source_record_summary(self, row: dict[str, Any]) -> None:
        """Upsert a source-record summary mart row."""
        sid = row.get("summary_id")
        if not sid:
            raise ValueError("summary_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            # Defensive IF NOT EXISTS so the CLI works even before explicit V21 migration on this DB
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_record_summary_mart (
                  summary_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  project_key TEXT NOT NULL,
                  source_system TEXT NOT NULL,
                  source_table TEXT NOT NULL,
                  record_count INTEGER NOT NULL DEFAULT 0,
                  mapped_count INTEGER NOT NULL DEFAULT 0,
                  unmapped_count INTEGER NOT NULL DEFAULT 0,
                  review_required_count INTEGER NOT NULL DEFAULT 0,
                  stale_count INTEGER NOT NULL DEFAULT 0,
                  quality_status TEXT NOT NULL,
                  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                """
                INSERT OR REPLACE INTO source_record_summary_mart
                (summary_id, run_id, project_key, source_system, source_table,
                 record_count, mapped_count, unmapped_count, review_required_count,
                 stale_count, quality_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    row.get("run_id"),
                    row.get("project_key"),
                    row.get("source_system"),
                    row.get("source_table"),
                    row.get("record_count", 0),
                    row.get("mapped_count", 0),
                    row.get("unmapped_count", 0),
                    row.get("review_required_count", 0),
                    row.get("stale_count", 0),
                    row.get("quality_status"),
                    _utc_now(),
                ),
            )

    def upsert_relationship_quality(self, row: dict[str, Any]) -> None:
        """Upsert a relationship quality mart row."""
        qid = row.get("quality_id")
        if not qid:
            raise ValueError("quality_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationship_quality_mart (
                  quality_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  project_key TEXT,
                  relationship_type TEXT NOT NULL,
                  confidence_class TEXT NOT NULL,
                  relationship_status TEXT NOT NULL,
                  total_count INTEGER NOT NULL DEFAULT 0,
                  review_required_count INTEGER NOT NULL DEFAULT 0,
                  orphan_count INTEGER NOT NULL DEFAULT 0,
                  quality_status TEXT NOT NULL,
                  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                """
                INSERT OR REPLACE INTO relationship_quality_mart
                (quality_id, run_id, project_key, relationship_type, confidence_class,
                 relationship_status, total_count, review_required_count, orphan_count,
                 quality_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    qid,
                    row.get("run_id"),
                    row.get("project_key"),
                    row.get("relationship_type"),
                    row.get("confidence_class"),
                    row.get("relationship_status"),
                    row.get("total_count", 0),
                    row.get("review_required_count", 0),
                    row.get("orphan_count", 0),
                    row.get("quality_status"),
                    _utc_now(),
                ),
            )

    def upsert_cross_domain_readiness(self, row: dict[str, Any]) -> None:
        """Upsert a cross-domain context readiness mart row."""
        rid = row.get("readiness_id")
        if not rid:
            raise ValueError("readiness_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cross_domain_context_readiness_mart (
                  readiness_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  project_key TEXT NOT NULL,
                  meeting_prep_ready INTEGER NOT NULL DEFAULT 0,
                  risk_digest_ready INTEGER NOT NULL DEFAULT 0,
                  financial_review_ready INTEGER NOT NULL DEFAULT 0,
                  blocking_reasons_json TEXT,
                  overall_status TEXT NOT NULL,
                  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                """
                INSERT OR REPLACE INTO cross_domain_context_readiness_mart
                (readiness_id, run_id, project_key, meeting_prep_ready, risk_digest_ready,
                 financial_review_ready, blocking_reasons_json, overall_status, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    row.get("run_id"),
                    row.get("project_key"),
                    1 if row.get("meeting_prep_ready") else 0,
                    1 if row.get("risk_digest_ready") else 0,
                    1 if row.get("financial_review_ready") else 0,
                    row.get("blocking_reasons_json"),
                    row.get("overall_status"),
                    _utc_now(),
                ),
            )

    def insert_data_quality_gate_result(self, gate: dict[str, Any]) -> None:
        """Insert a gate result row (idempotent on gate_result_id)."""
        gate_result_id = gate.get("gate_result_id")
        if not gate_result_id:
            raise ValueError("gate_result_id is required")
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT OR REPLACE INTO data_quality_gate_results
                (gate_result_id, run_id, gate_name, gate_status, threshold_json, observed_json,
                 blocking, created_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate_result_id,
                    gate.get("run_id"),
                    gate.get("gate_name"),
                    gate.get("gate_status"),
                    gate.get("threshold_json"),
                    gate.get("observed_json"),
                    1 if gate.get("blocking") else 0,
                    _utc_now(),
                ),
            )

    # --- Phase 07A Prompt 03 reusable helper (high-volume procore live table) ---
    # Added as the single minimal read-only extension for Prompt 03.
    # All other source adapters in source_record_map.py continue to use direct
    # bounded get_connection() queries + existing public list_* methods.
    # This helper reduces duplication for the dominant pilot data volume and
    # is intended for reuse in later prompts (diagnostics, marts, gates).
    # Read-only, no side effects, supports optional project filter + limit.

    def list_procore_live_records(
        self, *, project_key: Optional[str] = None, limit: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """Bounded read of procore_live_records (V6+). Returns dict rows.

        Used by Prompt 03 SourceRecordMapBuilder for deterministic mapping of
        the high-volume pilot live records. Can be reused by diagnostics/marts
        without duplicating SQL.
        """
        conn = get_connection(self._db_path)
        sql = (
            "SELECT project_key, procore_project_id, endpoint_id, parent_procore_id, "
            "procore_record_id, procore_record_number, title_redacted, status, "
            "updated_at_utc, source_url_redacted, first_seen_at_utc, last_seen_at_utc, "
            "last_sync_run_id, review_required, sensitive_reason "
            "FROM procore_live_records WHERE 1=1"
        )
        params: list[Any] = []
        if project_key is not None:
            sql += " AND project_key = ?"
            params.append(project_key)
        sql += " ORDER BY last_seen_at_utc DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        cur = conn.execute(sql, tuple(params))
        keys = (
            "project_key",
            "procore_project_id",
            "endpoint_id",
            "parent_procore_id",
            "procore_record_id",
            "procore_record_number",
            "title_redacted",
            "status",
            "updated_at_utc",
            "source_url_redacted",
            "first_seen_at_utc",
            "last_seen_at_utc",
            "last_sync_run_id",
            "review_required",
            "sensitive_reason",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]
        for r in rows:
            r["review_required"] = bool(r.get("review_required", 0))
        return rows
