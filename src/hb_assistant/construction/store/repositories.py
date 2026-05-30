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
