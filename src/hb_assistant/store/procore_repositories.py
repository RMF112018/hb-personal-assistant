"""SQLite repository functions for the Phase 04A procore live sync tables.

Owns insert/upsert of ``procore_live_sync_runs``, ``procore_live_records``,
and ``procore_live_sync_watermarks``. Callers (the live sync orchestrator)
supply already-normalized, redacted field dicts; this module never accepts
raw Procore response bodies and never writes secrets.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .connection import get_connection, transaction


def _open(db_path: Optional[Path]) -> sqlite3.Connection:
    return get_connection(db_path)


def record_sync_run_start(
    *,
    sync_run_id: str,
    endpoint_id: str,
    command_endpoint: str,
    legacy_endpoint_alias: Optional[str],
    project_key: str,
    procore_project_id: str,
    company_id: str,
    mode: str,
    started_at_utc: str,
    db_path: Optional[Path] = None,
) -> None:
    """Insert a pending sync-run row. Counts and state are updated at completion."""
    conn = _open(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_live_sync_runs (
              sync_run_id, endpoint_id, command_endpoint, legacy_endpoint_alias,
              project_key, procore_project_id, company_id, mode,
              started_at_utc, status, state, redaction_applied, raw_body_persisted,
              no_live_call_performed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', 'in_progress', 1, 0, 0)
            """,
            (
                sync_run_id,
                endpoint_id,
                command_endpoint,
                legacy_endpoint_alias,
                project_key,
                procore_project_id,
                company_id,
                mode,
                started_at_utc,
            ),
        )


def record_sync_run_complete(
    *,
    sync_run_id: str,
    status: str,
    state: str,
    reason_codes: Optional[list[str]],
    request_count: int,
    retrieved_count: int,
    normalized_count: int,
    sqlite_upserted_count: int,
    evidence_path: Optional[str],
    completed_at_utc: str,
    no_live_call_performed: bool,
    db_path: Optional[Path] = None,
) -> None:
    """Update the sync-run row with final counts, state, and reason codes."""
    conn = _open(db_path)
    with transaction(conn):
        conn.execute(
            """
            UPDATE procore_live_sync_runs
               SET completed_at_utc = ?,
                   status = ?,
                   state = ?,
                   reason_codes_json = ?,
                   request_count = ?,
                   retrieved_count = ?,
                   normalized_count = ?,
                   sqlite_upserted_count = ?,
                   evidence_path = ?,
                   no_live_call_performed = ?
             WHERE sync_run_id = ?
            """,
            (
                completed_at_utc,
                status,
                state,
                json.dumps(reason_codes or []),
                request_count,
                retrieved_count,
                normalized_count,
                sqlite_upserted_count,
                evidence_path,
                1 if no_live_call_performed else 0,
                sync_run_id,
            ),
        )


def upsert_procore_live_record(
    *,
    project_key: str,
    procore_project_id: str,
    endpoint_id: str,
    procore_record_id: str,
    parent_procore_id: Optional[str],
    normalized_fields: Mapping[str, Any],
    review_required: bool,
    sensitive_reason: Optional[str],
    source_url_redacted: Optional[str],
    last_sync_run_id: str,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> str:
    """Upsert a single live record. Returns ``"inserted"`` or ``"updated"``.

    ``normalized_fields`` is the canonical-field dict (already redacted) and
    is persisted as a single JSON column to avoid per-endpoint schema sprawl.
    """

    record_number = normalized_fields.get("number") if isinstance(normalized_fields, dict) else None
    title = normalized_fields.get("title") or normalized_fields.get("subject") if isinstance(normalized_fields, dict) else None
    status = normalized_fields.get("status") if isinstance(normalized_fields, dict) else None
    updated_at = normalized_fields.get("updated_at") if isinstance(normalized_fields, dict) else None
    canonical_json = json.dumps(dict(normalized_fields), default=str, sort_keys=True)
    parent_id_str = parent_procore_id or ""

    conn = _open(db_path)
    with transaction(conn):
        existing = conn.execute(
            """
            SELECT 1 FROM procore_live_records
             WHERE project_key = ?
               AND endpoint_id = ?
               AND parent_procore_id = ?
               AND procore_record_id = ?
            """,
            (project_key, endpoint_id, parent_id_str, str(procore_record_id)),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO procore_live_records (
                  project_key, procore_project_id, endpoint_id, parent_procore_id,
                  procore_record_id, procore_record_number, title_redacted, status,
                  updated_at_utc, source_url_redacted, canonical_json_redacted,
                  review_required, sensitive_reason, first_seen_at_utc,
                  last_seen_at_utc, last_sync_run_id, raw_body_persisted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    project_key,
                    procore_project_id,
                    endpoint_id,
                    parent_id_str,
                    str(procore_record_id),
                    str(record_number) if record_number is not None else None,
                    str(title) if title is not None else None,
                    str(status) if status is not None else None,
                    str(updated_at) if updated_at is not None else None,
                    source_url_redacted,
                    canonical_json,
                    1 if review_required else 0,
                    sensitive_reason,
                    now_utc,
                    now_utc,
                    last_sync_run_id,
                ),
            )
            return "inserted"

        conn.execute(
            """
            UPDATE procore_live_records
               SET procore_project_id = ?,
                   procore_record_number = ?,
                   title_redacted = ?,
                   status = ?,
                   updated_at_utc = ?,
                   source_url_redacted = ?,
                   canonical_json_redacted = ?,
                   review_required = ?,
                   sensitive_reason = ?,
                   last_seen_at_utc = ?,
                   last_sync_run_id = ?
             WHERE project_key = ?
               AND endpoint_id = ?
               AND parent_procore_id = ?
               AND procore_record_id = ?
            """,
            (
                procore_project_id,
                str(record_number) if record_number is not None else None,
                str(title) if title is not None else None,
                str(status) if status is not None else None,
                str(updated_at) if updated_at is not None else None,
                source_url_redacted,
                canonical_json,
                1 if review_required else 0,
                sensitive_reason,
                now_utc,
                last_sync_run_id,
                project_key,
                endpoint_id,
                parent_id_str,
                str(procore_record_id),
            ),
        )
        return "updated"


def update_watermark(
    *,
    company_id: str,
    project_key: str,
    procore_project_id: str,
    endpoint_id: str,
    cursor_redacted: Optional[str],
    receipt_id: str,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> None:
    """Insert-or-update the per-endpoint watermark row."""
    conn = _open(db_path)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO procore_live_sync_watermarks (
              company_id, project_key, procore_project_id, endpoint_id,
              last_success_at_utc, last_receipt_id, cursor_redacted
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, project_key, procore_project_id, endpoint_id)
            DO UPDATE SET
              last_success_at_utc = excluded.last_success_at_utc,
              last_receipt_id = excluded.last_receipt_id,
              cursor_redacted = excluded.cursor_redacted
            """,
            (
                company_id,
                project_key,
                procore_project_id,
                endpoint_id,
                now_utc,
                receipt_id,
                cursor_redacted,
            ),
        )


def count_procore_live_records(
    *,
    project_key: str,
    endpoint_id: str,
    db_path: Optional[Path] = None,
) -> int:
    """Return the number of canonical live-records rows for the given scope."""
    conn = _open(db_path)
    cur = conn.execute(
        """
        SELECT COUNT(1) FROM procore_live_records
         WHERE project_key = ? AND endpoint_id = ?
        """,
        (project_key, endpoint_id),
    )
    row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def get_first_procore_record_id(
    *,
    project_key: str,
    endpoint_id: str,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Return earliest-seen procore_record_id for (project, endpoint), else None."""
    conn = _open(db_path)
    cur = conn.execute(
        """
        SELECT procore_record_id
          FROM procore_live_records
         WHERE project_key = ? AND endpoint_id = ?
         ORDER BY first_seen_at_utc ASC, procore_record_id ASC
         LIMIT 1
        """,
        (project_key, endpoint_id),
    )
    row = cur.fetchone()
    if not row or row[0] in (None, ""):
        return None
    return str(row[0])


def get_sync_run(
    *, sync_run_id: str, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Return the sync-run row as a dict (for tests/CLI introspection)."""
    conn = _open(db_path)
    cur = conn.execute(
        "SELECT * FROM procore_live_sync_runs WHERE sync_run_id = ?",
        (sync_run_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def delete_procore_live_records_by_sync_run(
    *,
    sync_run_id: str,
    db_path: Optional[Path] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Rollback path: drop every ``procore_live_records`` row attributed to a sync run.

    The matching ``procore_live_sync_runs`` row is intentionally preserved so
    operators retain an audit trail of "this run was rolled back" — the
    receipt still exists; only the persisted records it produced are removed.

    Defaults to ``dry_run=True``: returns ``{sync_run_id, would_delete, dry_run}``
    with no mutation. Pass ``dry_run=False`` to actually delete; the return
    payload then carries ``deleted`` instead of ``would_delete``.
    """
    conn = _open(db_path)
    cur = conn.execute(
        """
        SELECT COUNT(1) FROM procore_live_records
         WHERE last_sync_run_id = ?
        """,
        (sync_run_id,),
    )
    row = cur.fetchone()
    matched = int(row[0]) if row and row[0] is not None else 0

    if dry_run:
        return {
            "sync_run_id": sync_run_id,
            "would_delete": matched,
            "dry_run": True,
        }

    with transaction(conn):
        conn.execute(
            """
            DELETE FROM procore_live_records
             WHERE last_sync_run_id = ?
            """,
            (sync_run_id,),
        )
    return {
        "sync_run_id": sync_run_id,
        "deleted": matched,
        "dry_run": False,
    }


__all__ = [
    "count_procore_live_records",
    "delete_procore_live_records_by_sync_run",
    "get_first_procore_record_id",
    "get_sync_run",
    "record_sync_run_complete",
    "record_sync_run_start",
    "update_watermark",
    "upsert_procore_live_record",
]
