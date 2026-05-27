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
    ) -> None:
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
                     created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    updated_utc = excluded.updated_utc
                """,
                (
                    source_id, drive_id, drive_item_id, parent_drive_item_id,
                    site_id, list_id, list_item_id, name, path, web_url,
                    1 if is_folder else 0, 1 if is_file else 0,
                    file_extension, mime_type, size_bytes,
                    last_modified_datetime, 1 if deleted else 0, quick_xor_hash,
                    project_number_detected, document_type_detected,
                    indexing_policy, classification_status,
                    _utc_now(), _utc_now(),
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
                   created_utc, updated_utc
            FROM construction_drive_items
            WHERE source_id = ? AND drive_item_id = ?
            """,
            (source_id, drive_item_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = (
            "source_id", "drive_id", "drive_item_id", "parent_drive_item_id",
            "site_id", "list_id", "list_item_id", "name", "path", "web_url",
            "is_folder", "is_file", "file_extension", "mime_type", "size_bytes",
            "last_modified_datetime", "deleted", "quick_xor_hash",
            "project_number_detected", "document_type_detected",
            "indexing_policy", "classification_status",
            "created_utc", "updated_utc",
        )
        record = dict(zip(keys, row, strict=True))
        for bool_field in ("is_folder", "is_file", "deleted"):
            record[bool_field] = bool(record[bool_field])
        return record

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
