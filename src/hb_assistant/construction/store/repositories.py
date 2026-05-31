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

import json
from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Column order for construction_drive_items reads (V5 base + V15 rich metadata).
_DRIVE_ITEM_KEYS: tuple[str, ...] = (
    "source_id", "drive_id", "drive_item_id", "parent_drive_item_id",
    "site_id", "list_id", "list_item_id", "name", "path", "web_url",
    "is_folder", "is_file", "file_extension", "mime_type", "size_bytes",
    "last_modified_datetime", "deleted", "quick_xor_hash",
    "project_number_detected", "document_type_detected",
    "indexing_policy", "classification_status",
    "created_utc", "updated_utc",
    "is_package", "e_tag", "c_tag", "created_datetime",
    "parent_reference_path", "folder_child_count",
    "sharepoint_web_id", "sharepoint_list_item_id",
    "file_hashes_json", "package_json_redacted",
    "remote_item_json_redacted", "first_seen_utc", "last_seen_utc",
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
            "source_key", "drive_id", "item_id", "name", "web_url", "parent_path",
            "size_bytes", "is_folder", "last_modified", "etag", "status",
            "first_seen_at", "last_seen_at",
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
        self, source_key: str, *, include_deleted: bool = False, limit: int = 5000,
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
        keys = ("source_key", "drive_id", "item_id", "name", "web_url", "parent_path",
                "size_bytes", "is_folder", "last_modified", "etag", "status",
                "first_seen_at", "last_seen_at")
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
                    match.source_key, match.project_key, match.item_id,
                    match.name, match.parent_path, match.rule_id,
                    match.classification_label, match.sensitivity, match.reason,
                    match.suggested_action, match.confidence, _utc_now(),
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
        keys = ("id", "source_key", "project_key", "item_id", "name", "parent_path",
                "rule_id", "classification_label", "sensitivity", "reason",
                "suggested_action", "confidence", "status", "routed_at", "resolved_at")
        return [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]

    def count_review_queue(
        self, *, source_key: str | None = None, status: str | None = "open",
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
                    decision.source_key, decision.item_id, decision.project_key,
                    decision.model_name, decision.model_task,
                    decision.proposed_label, decision.confidence,
                    decision.rationale_truncated, decision.raw_output_truncated,
                    decision.status, decision.routing_reason, decision.routed_at,
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
        keys = ("id", "source_key", "item_id", "project_key", "model_name", "model_task",
                "proposed_label", "confidence", "rationale_truncated",
                "raw_output_truncated", "status", "routing_reason", "routed_at")
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
        keys = ("id", "run_id", "mode", "started_at", "finished_at", "pages_seen",
                "items_seen", "items_new", "items_updated", "items_deleted",
                "delta_link_recorded", "status", "error_redacted")
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
                    source_id, source_system, source_scope, source_name,
                    project_key, project_number, project_name, tenant_id,
                    site_url, site_id, drive_id, folder_item_id, folder_path,
                    folder_web_url, library_name, list_id, local_sync_path,
                    sync_mode, sync_frequency_minutes, 1 if enabled else 0,
                    self._dump_json(baseline_policy),
                    self._dump_json(folder_policies),
                    _utc_now(), _utc_now(),
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
                    source_id, mailbox_owner_hash, mailbox_owner_domain, calendar_id_hash,
                    calendar_role, calendar_display_name_hash, 1 if enabled else 0,
                    lookback_days, lookahead_days, max_items_per_run, policy_id,
                    _utc_now(), _utc_now(),
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
                    source_id, last_successful_sync_utc, last_attempted_sync_utc,
                    window_start_utc, window_end_utc, last_event_count, sync_status,
                    error_redacted,
                ),
            )

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
                    run_id, source_id, mode, started_at_utc or _utc_now(),
                    window_start_utc, window_end_utc, status,
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
                    status, completed_at_utc or _utc_now(), events_seen,
                    events_indexed, events_private, events_cancelled,
                    events_review_required, error_redacted, run_id,
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
                    event_index_id, source_id, graph_event_id_hash, ical_uid_hash,
                    series_master_id_hash, web_link_hash, subject_hash, subject_redacted,
                    subject_token_hashes_json, organizer_hash, organizer_domain,
                    location_hash, location_redacted, start_datetime_utc, end_datetime_utc,
                    timezone, 1 if is_cancelled else 0, 1 if is_private else 0,
                    1 if is_online_meeting else 0, online_meeting_provider,
                    1 if has_attachments else 0, project_key, project_match_method,
                    project_match_confidence, 1 if review_required else 0,
                    review_reasons_json, _utc_now(), _utc_now(),
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
                    event_index_id, attendee_hash, attendee_domain, attendee_role,
                    response_status, 1 if review_required else 0,
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
            "event_index_id", "source_id", "subject_token_hashes_json", "organizer_domain",
            "is_private", "is_cancelled", "project_key", "project_match_method",
            "project_match_confidence", "review_required", "review_reasons_json",
        )
        rows: list[dict[str, Any]] = []
        for row in conn.execute(sql, params):
            rec = dict(zip(keys, row, strict=True))
            rec["subject_token_hashes"] = self._load_json(rec.pop("subject_token_hashes_json")) or []
            rec["review_reasons"] = self._load_json(rec.pop("review_reasons_json")) or []
            rec["is_private"] = bool(rec["is_private"])
            rec["is_cancelled"] = bool(rec["is_cancelled"])
            rec["review_required"] = bool(rec["review_required"])
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
                    candidate_id, event_index_id, project_key, candidate_type,
                    signals_json, confidence, confidence_class, 1 if deterministic else 0,
                    1 if model_proposed else 0, 1 if review_required else 0,
                    promotion_status, _utc_now(),
                ),
            )

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
            "source_id", "source_system", "source_scope", "source_name",
            "project_key", "project_number", "project_name", "tenant_id",
            "site_url", "site_id", "drive_id", "folder_item_id", "folder_path",
            "folder_web_url", "library_name", "list_id", "local_sync_path",
            "sync_mode", "sync_frequency_minutes", "enabled", "read_only",
            "baseline_policy_json", "folder_policies_json",
            "created_utc", "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        record["baseline_policy"] = self._load_json(record.pop("baseline_policy_json"))
        record["folder_policies"] = self._load_json(record.pop("folder_policies_json"))
        record["enabled"] = bool(record["enabled"])
        record["read_only"] = bool(record["read_only"])
        return record

    def list_source_locations(
        self, *, project_key: Optional[str] = None, limit: int = 1000,
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
                    source_id, drive_id, folder_item_id, delta_link,
                    delta_link_fingerprint, last_successful_sync_utc,
                    last_attempted_sync_utc, last_baseline_item_count,
                    last_change_count, sync_status, error_message_redacted,
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
            "source_id", "drive_id", "folder_item_id", "delta_link",
            "delta_link_fingerprint", "last_successful_sync_utc",
            "last_attempted_sync_utc", "last_baseline_item_count",
            "last_change_count", "sync_status", "error_message_redacted",
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
                    run_id, source_id, source_scope, mode, started_at,
                    completed_at, pages_seen, items_seen, items_in_scope,
                    items_out_of_scope_filtered, 1 if delta_link_recorded else 0,
                    status, error_redacted,
                ),
            )

    def list_source_crawl_runs(
        self, *, source_id: Optional[str] = None, limit: int = 100,
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
            "run_id", "source_id", "source_scope", "mode", "started_at",
            "completed_at", "pages_seen", "items_seen", "items_in_scope",
            "items_out_of_scope_filtered", "delta_link_recorded", "status",
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
                     remote_item_json_redacted, first_seen_utc, last_seen_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    last_seen_utc = excluded.last_seen_utc
                """,
                (
                    source_id, drive_id, drive_item_id, parent_drive_item_id,
                    site_id, list_id, list_item_id, name, path, web_url,
                    1 if is_folder else 0, 1 if is_file else 0,
                    file_extension, mime_type, size_bytes,
                    last_modified_datetime, 1 if deleted else 0, quick_xor_hash,
                    project_number_detected, document_type_detected,
                    indexing_policy, classification_status,
                    now, now,
                    1 if is_package else 0, e_tag, c_tag, created_datetime,
                    parent_reference_path, folder_child_count,
                    sharepoint_web_id, sharepoint_list_item_id,
                    file_hashes_json, package_json_redacted,
                    remote_item_json_redacted, now, now,
                ),
            )

    def get_drive_item(
        self, *, source_id: str, drive_item_id: str,
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
                   remote_item_json_redacted, first_seen_utc, last_seen_utc
            FROM construction_drive_items
            WHERE source_id = ? AND drive_item_id = ?
            """,
            (source_id, drive_item_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        record = dict(zip(_DRIVE_ITEM_KEYS, row, strict=True))
        for bool_field in ("is_folder", "is_file", "deleted", "is_package"):
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
            "remote_item_json_redacted, first_seen_utc, last_seen_utc "
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
            for bool_field in ("is_folder", "is_file", "deleted", "is_package"):
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
                    project_key, project_number_detected, match_confidence,
                    match_status, 1 if review_required else 0, review_reason,
                    match_signals_json, _utc_now(), source_id, drive_item_id,
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
            "source_id", "drive_item_id", "name", "path", "project_key",
            "project_number_detected", "match_confidence", "match_status",
            "review_required", "review_reason", "match_signals_json",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()]
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
                    decision_id, source_id, drive_id, drive_item_id, project_key,
                    project_number_detected, document_type_detected,
                    ingestion_disposition, 1 if review_required else 0, review_reason,
                    1 if extraction_allowed else 0, 1 if download_allowed else 0,
                    reason_codes_json, _utc_now(),
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
            "decision_id", "source_id", "drive_id", "drive_item_id", "project_key",
            "project_number_detected", "document_type_detected", "ingestion_disposition",
            "review_required", "review_reason", "extraction_allowed", "download_allowed",
            "reason_codes_json", "decided_utc",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()]
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
                    receipt_id, source_id, drive_id, drive_item_id, project_key, mode,
                    1 if download_attempted else 0, 1 if download_completed else 0,
                    bytes_written, sha256, cache_path_redacted,
                    1 if cache_deleted_after_parse else 0, status, error_redacted,
                    _utc_now(),
                ),
            )

    def list_download_receipts(
        self, *, source_id: Optional[str] = None, limit: int = 1000,
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
            "receipt_id", "source_id", "drive_id", "drive_item_id", "project_key", "mode",
            "download_attempted", "download_completed", "bytes_written", "sha256",
            "cache_path_redacted", "cache_deleted_after_parse", "status", "error_redacted",
            "created_utc", "raw_download_url_persisted", "source_file_copied_to_vault",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            for b in ("download_attempted", "download_completed", "cache_deleted_after_parse",
                      "raw_download_url_persisted", "source_file_copied_to_vault"):
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
                    extraction_id, source_id, drive_id, drive_item_id, project_key,
                    parser_name, parser_version, content_hash, extraction_status,
                    text_excerpt_redacted, char_count, 1 if review_required else 0,
                    error_redacted, _utc_now(),
                ),
            )

    def list_file_extraction_runs(
        self, *, source_id: Optional[str] = None, limit: int = 1000,
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
            "extraction_id", "source_id", "drive_id", "drive_item_id", "project_key",
            "parser_name", "parser_version", "content_hash", "extraction_status",
            "text_excerpt_redacted", "char_count", "full_text_persisted", "review_required",
            "error_redacted", "created_utc",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()]
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
                    project_key, hb_project_number, project_name_raw,
                    project_name_normalized, 1 if is_active else 0,
                    procore_project_id, project_stage, last_seen_utc,
                    last_validated_utc, match_status, match_confidence,
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
            "project_key", "hb_project_number", "project_name_raw",
            "project_name_normalized", "is_active", "procore_project_id",
            "project_stage", "last_seen_utc", "last_validated_utc",
            "match_status", "match_confidence",
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
                    project_key, source_id, match_method, match_confidence,
                    1 if review_required else 0, _utc_now(),
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
            "id", "project_key", "source_id", "match_method", "match_confidence",
            "review_required", "created_utc",
        )
        rows = [dict(zip(keys, row, strict=True)) for row in cur.fetchall()]
        for r in rows:
            r["review_required"] = bool(r["review_required"])
        return rows

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
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO construction_document_cards
                    (card_id, source_id, drive_item_id, project_key,
                     document_type, status, confidence, needs_review, card_path,
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    source_id = excluded.source_id,
                    drive_item_id = excluded.drive_item_id,
                    project_key = excluded.project_key,
                    document_type = excluded.document_type,
                    status = excluded.status,
                    confidence = excluded.confidence,
                    needs_review = excluded.needs_review,
                    card_path = excluded.card_path,
                    updated_utc = excluded.updated_utc
                """,
                (
                    card_id, source_id, drive_item_id, project_key,
                    document_type, status, confidence,
                    1 if needs_review else 0, card_path,
                    _utc_now(), _utc_now(),
                ),
            )

    def get_document_card(self, card_id: str) -> Optional[dict[str, Any]]:
        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT card_id, source_id, drive_item_id, project_key,
                   document_type, status, confidence, needs_review, card_path,
                   created_utc, updated_utc
            FROM construction_document_cards
            WHERE card_id = ?
            """,
            (card_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "card_id", "source_id", "drive_item_id", "project_key",
            "document_type", "status", "confidence", "needs_review", "card_path",
            "created_utc", "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        record["needs_review"] = bool(record["needs_review"])
        return record

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
                    receipt_id, source_id, operation, status,
                    self._dump_json(detail), _utc_now(),
                ),
            )

    def list_processing_receipts(
        self, *, source_id: Optional[str] = None, limit: int = 100,
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
        keys = ("receipt_id", "source_id", "operation", "status", "generated_at",
                "detail_json")
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
                    resolution_id, source_id, redacted_url, hostname,
                    normalized_path, url_fingerprint, share_token_fingerprint,
                    resolution_method, status, site_id, drive_id, drive_item_id,
                    folder_item_id, parent_drive_id, parent_drive_item_id,
                    list_id, list_item_id, web_url, name, item_kind,
                    error_redacted, _utc_now(),
                ),
            )

    def list_link_resolutions(
        self, *, source_id: Optional[str] = None, limit: int = 100,
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
            "resolution_id", "source_id", "redacted_url", "hostname",
            "normalized_path", "url_fingerprint", "share_token_fingerprint",
            "resolution_method", "status", "site_id", "drive_id", "drive_item_id",
            "folder_item_id", "parent_drive_id", "parent_drive_item_id",
            "list_id", "list_item_id", "web_url", "name", "item_kind",
            "error_redacted", "raw_tokenized_url_persisted", "created_utc",
        )
        return [dict(zip(keys, row, strict=True)) for row in conn.execute(sql, tuple(params)).fetchall()]

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
        keys = ("id", "source_id", "operation", "error_class", "error_redacted",
                "occurred_utc", "resolved_utc")
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
                "persist_full_body must be False — Phase 02 never persists full "
                "mailbox bodies"
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
        keys = ("id", "mail_read_all_granted", "mail_readwrite_all_granted",
                "mailbox_writeback_allowed", "persist_full_body", "updated_utc")
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
            raise ValueError(
                "mailbox_mode must be 'read_only' — Phase 06 mailbox stays read-only"
            )
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
            "id", "policy_phase", "mailbox_mode", "writeback_allowed",
            "mailbox_mutation_allowed", "full_archive_crawl", "source_copy_to_vault",
            "full_email_body_in_obsidian", "attachment_content_download_by_default",
            "metadata_only_by_default", "review_required_for_sensitive",
            "initial_backfill_mode", "ollama_invalid_json_routes_to_review",
            "default_lookback_days", "ollama_enabled_for_email_intelligence",
            "low_confidence_threshold", "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        for bool_field in (
            "writeback_allowed", "mailbox_mutation_allowed", "full_archive_crawl",
            "source_copy_to_vault", "full_email_body_in_obsidian",
            "attachment_content_download_by_default", "metadata_only_by_default",
            "review_required_for_sensitive", "ollama_invalid_json_routes_to_review",
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
            raise ValueError(
                "email_source_locations.read_only must be True (no mailbox writeback)"
            )
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
            "source_id", "source_system", "mailbox_owner_hash",
            "mailbox_display_name_redacted", "mailbox_user_principal_name_hash",
            "folder_id", "folder_display_name", "folder_role", "include_in_sync",
            "sync_mode", "default_lookback_days", "read_only",
            "mailbox_mutation_allowed", "full_archive_crawl_allowed",
            "source_copy_to_vault_allowed", "full_email_body_in_obsidian_allowed",
            "created_utc", "updated_utc",
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
            "include_in_sync", "read_only", "mailbox_mutation_allowed",
            "full_archive_crawl_allowed", "source_copy_to_vault_allowed",
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
                "include_in_sync", "read_only", "mailbox_mutation_allowed",
                "full_archive_crawl_allowed", "source_copy_to_vault_allowed",
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

    def get_email_sync_state(
        self, *, source_id: str, folder_id: str
    ) -> Optional[dict[str, Any]]:
        keys = (
            "source_id", "folder_id", "sync_mode", "lookback_days",
            "last_successful_sync_utc", "last_attempted_sync_utc",
            "latest_received_datetime", "latest_sent_datetime",
            "delta_token_fingerprint", "delta_token_supported", "sync_status",
            "error_redacted",
        )
        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT {', '.join(keys)} FROM email_sync_state "
            "WHERE source_id = ? AND folder_id = ?",
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

    @staticmethod
    def _email_message_keys() -> tuple[str, ...]:
        return (
            "message_id", "internet_message_id", "conversation_id", "thread_key",
            "source_id", "folder_id", "folder_display_name", "subject_redacted",
            "subject_hash", "sender_name_redacted", "sender_address_hash",
            "sender_domain", "to_recipient_count", "cc_recipient_count",
            "bcc_recipient_count", "received_datetime", "sent_datetime",
            "last_modified_datetime", "has_attachments", "importance",
            "categories_metadata_json", "sensitivity_metadata", "web_link",
            "body_preview_hash", "body_preview_excerpt_redacted", "body_checked",
            "body_mention_detected", "project_number_detected",
            "project_match_confidence", "sensitivity_classification",
            "extraction_policy", "review_required", "full_body_persisted",
            "mailbox_mutation_allowed", "indexed_utc", "updated_utc",
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
            raise ValueError(
                "email_messages.extraction_policy must be 'metadata_only' in Phase 06"
            )
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
    def _email_message_row_to_record(
        keys: tuple[str, ...], row: Any
    ) -> dict[str, Any]:
        record = dict(zip(keys, row, strict=True))
        record["categories_metadata"] = ConstructionStore._load_json(
            record.pop("categories_metadata_json")
        )
        for bool_field in (
            "has_attachments", "body_checked", "body_mention_detected",
            "review_required", "full_body_persisted", "mailbox_mutation_allowed",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

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

    def list_email_message_recipients(
        self, message_id: str
    ) -> list[dict[str, Any]]:
        keys = (
            "id", "message_id", "recipient_role", "display_name_redacted",
            "address_hash", "domain", "is_bobby", "known_project_participant",
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
            record["known_project_participant"] = bool(
                record["known_project_participant"]
            )
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
            raise ValueError(
                "email_message_attachments.metadata_only must be True in Phase 06"
            )
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
            "match_id", "message_id", "project_key", "project_number",
            "project_name_normalized", "match_signal", "match_value_hash",
            "confidence", "review_required", "evidence_redacted", "created_utc",
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
            "candidate_id", "message_id", "project_key", "candidate_type",
            "target_source_system", "target_table", "target_key", "match_signal",
            "confidence", "evidence_redacted", "review_required", "created_utc",
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
            "review_id", "message_id", "project_key", "category", "sensitivity",
            "reason", "suggested_action", "confidence", "status", "routed_utc",
            "resolved_utc", "body_capture_eligible", "encrypted_body_capture_allowed",
            "review_required_before_body_use", "body_capture_decision_json",
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
        cur = conn.execute(
            f"SELECT COUNT(*) FROM email_review_queue {where}", tuple(params)
        )
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
            "receipt_id", "run_id", "message_id", "project_key", "operation",
            "status", "detail_json", "mailbox_mutation_attempted",
            "full_body_persisted", "attachment_content_downloaded", "generated_utc",
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
                "mailbox_mutation_attempted", "full_body_persisted",
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
            "message_id", "internet_message_id", "conversation_id", "body_content_type",
            "body_hash", "body_length", "encrypted_full_body_ref", "encrypted_at_utc",
            "encryption_method", "plaintext_persisted", "obsidian_body_persisted",
            "evidence_body_persisted", "log_body_persisted", "extraction_policy",
            "review_required", "sensitivity_classification", "created_utc", "updated_utc",
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
            "plaintext_persisted", "obsidian_body_persisted", "evidence_body_persisted",
            "log_body_persisted", "review_required",
        ):
            record[bool_field] = bool(record[bool_field])
        return record

    # -------------------------------------------------------------------------
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
                raise ValueError(f"{flag} must be False — Phase 07A source_system_record_map never persists raw content or performs writeback")
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
                raise ValueError(f"{flag} must be False — Phase 07A relationship_resolution_queue never persists raw content")
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
