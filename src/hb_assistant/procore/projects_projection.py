"""One-row-per-project_key semantics for ``procore_ep_projects`` projection."""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

PROJECTS_ENDPOINT_ID = "projects"
PROJECTS_PRIMARY_TABLE = "procore_ep_projects"


def projects_record_key_for_project_key(project_key: str) -> str:
    """Stable primary ``record_key`` for a HB ``project_key``."""
    digest = hashlib.sha256(project_key.encode("utf-8")).hexdigest()[:32]
    return f"psk-{digest}"


def primary_upsert_conflict_key(primary_table: str) -> str:
    if primary_table == PROJECTS_PRIMARY_TABLE:
        return "project_key"
    return "record_key"


def payload_matches_projects_context(
    *,
    endpoint_id: str,
    procore_project_id: str | None,
    record_id: str,
    payload: dict[str, Any],
) -> bool:
    """Company-level ``projects`` list items must match the sync-context Procore id."""
    if endpoint_id != PROJECTS_ENDPOINT_ID:
        return True
    ctx_id = str(procore_project_id or "").strip()
    if not ctx_id:
        return True
    payload_id = str(payload.get("id") or record_id).strip()
    return payload_id == ctx_id


def projects_child_tables() -> list[str]:
    from .projection_registry import plan_for

    plan = plan_for(PROJECTS_ENDPOINT_ID)
    if plan is None:
        return []
    return [child.table for child in plan.child_tables]


def dedupe_procore_ep_projects(conn: sqlite3.Connection) -> dict[str, int]:
    """Retain one primary row per ``project_key``; delete extras and orphan children."""
    conn.row_factory = sqlite3.Row
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (PROJECTS_PRIMARY_TABLE,),
    ).fetchone():
        return {"keepers": 0, "deleted_primaries": 0, "deleted_children": 0}

    rows = list(
        conn.execute(
            f"""
            SELECT record_key, project_key, record_id, project_id, updated_utc
            FROM {PROJECTS_PRIMARY_TABLE}
            WHERE project_key IS NOT NULL AND TRIM(project_key) <> ''
            ORDER BY project_key, updated_utc DESC, record_key
            """
        )
    )
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        key = str(row["project_key"])
        grouped.setdefault(key, []).append(row)

    child_tables = projects_child_tables()
    deleted_children = 0
    deleted_primaries = 0
    keepers = 0

    for project_key, group in grouped.items():
        matched = [
            row
            for row in group
            if str(row["record_id"] or "").strip() == str(row["project_id"] or "").strip()
            and str(row["record_id"] or "").strip()
        ]
        keeper = matched[0] if matched else group[0]
        keepers += 1
        keeper_old_key = str(keeper["record_key"])
        stable_key = projects_record_key_for_project_key(project_key)
        if keeper_old_key != stable_key:
            for child_table in child_tables:
                if not conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (child_table,),
                ).fetchone():
                    continue
                cur = conn.execute(
                    f"DELETE FROM {child_table} WHERE primary_record_key = ?",
                    (keeper_old_key,),
                )
                deleted_children += cur.rowcount
            conn.execute(
                f"UPDATE {PROJECTS_PRIMARY_TABLE} SET record_key = ? WHERE record_key = ?",
                (stable_key, keeper_old_key),
            )
        for row in group:
            row_key = str(row["record_key"])
            if row_key in (keeper_old_key, stable_key):
                continue
            for child_table in child_tables:
                if not conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (child_table,),
                ).fetchone():
                    continue
                cur = conn.execute(
                    f"DELETE FROM {child_table} WHERE primary_record_key = ?",
                    (row["record_key"],),
                )
                deleted_children += cur.rowcount
            conn.execute(
                f"DELETE FROM {PROJECTS_PRIMARY_TABLE} WHERE record_key = ?",
                (row["record_key"],),
            )
            deleted_primaries += 1

    return {
        "keepers": keepers,
        "deleted_primaries": deleted_primaries,
        "deleted_children": deleted_children,
    }