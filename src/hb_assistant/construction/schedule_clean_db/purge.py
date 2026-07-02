"""Tropical schedule purge planner/executor for copied clean databases."""

from __future__ import annotations

import sqlite3
from typing import Any

from hb_assistant.construction.schedule_clean_db.purge_dependency_map import (
    PURGE_TABLE_STRATEGIES,
    topological_delete_order,
)
from hb_assistant.construction.schedule_clean_db.schema_audit import (
    CATALOG_PRESERVE_TABLES,
    build_schema_audit_report,
    is_schedule_domain_table,
)


def _project_import_ids(conn: sqlite3.Connection, project_key: str) -> list[str]:
    try:
        return [
            str(row[0])
            for row in conn.execute(
                "SELECT import_id FROM schedule_file_imports WHERE project_key=?",
                (project_key,),
            ).fetchall()
        ]
    except sqlite3.Error:
        return []


def _project_version_keys(conn: sqlite3.Connection, project_key: str) -> list[str]:
    try:
        return [
            str(row[0])
            for row in conn.execute(
                "SELECT schedule_version_key FROM schedule_file_imports WHERE project_key=?",
                (project_key,),
            ).fetchall()
        ]
    except sqlite3.Error:
        return []


def _project_baseline_project_keys(conn: sqlite3.Connection, project_key: str) -> list[str]:
    try:
        return [
            str(row[0])
            for row in conn.execute(
                """
                SELECT baseline_project_key FROM schedule_baseline_projects
                WHERE import_id IN (
                  SELECT import_id FROM schedule_file_imports WHERE project_key=?
                )
                """,
                (project_key,),
            ).fetchall()
            if row[0]
        ]
    except sqlite3.Error:
        return []


def _delete_for_project(
    conn: sqlite3.Connection,
    table: str,
    project_key: str,
    strategy: str,
) -> int:
    if table in CATALOG_PRESERVE_TABLES:
        return 0
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if "project_key" in columns:
        cur = conn.execute(f"DELETE FROM {table} WHERE project_key=?", (project_key,))
        return int(cur.rowcount)
    if "baseline_project_key" in columns:
        keys = _project_baseline_project_keys(conn, project_key)
        if not keys:
            return 0
        placeholders = ", ".join("?" for _ in keys)
        cur = conn.execute(
            f"DELETE FROM {table} WHERE baseline_project_key IN ({placeholders})",
            keys,
        )
        return int(cur.rowcount)
    if "schedule_version_key" in columns:
        keys = _project_version_keys(conn, project_key)
        if not keys:
            return 0
        placeholders = ", ".join("?" for _ in keys)
        cur = conn.execute(
            f"DELETE FROM {table} WHERE schedule_version_key IN ({placeholders})",
            keys,
        )
        return int(cur.rowcount)
    if "current_schedule_version_key" in columns:
        keys = _project_version_keys(conn, project_key)
        if not keys:
            return 0
        placeholders = ", ".join("?" for _ in keys)
        cur = conn.execute(
            f"DELETE FROM {table} WHERE current_schedule_version_key IN ({placeholders})",
            keys,
        )
        return int(cur.rowcount)
    if "import_id" in columns:
        import_ids = _project_import_ids(conn, project_key)
        if not import_ids:
            return 0
        placeholders = ", ".join("?" for _ in import_ids)
        cur = conn.execute(
            f"DELETE FROM {table} WHERE import_id IN ({placeholders})",
            import_ids,
        )
        return int(cur.rowcount)
    if "cpm_run_id" in columns and "schedule_cpm_runs" in {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        keys = _project_version_keys(conn, project_key)
        if not keys:
            return 0
        placeholders = ", ".join("?" for _ in keys)
        run_ids = [
            str(row[0])
            for row in conn.execute(
                f"SELECT cpm_run_id FROM schedule_cpm_runs WHERE schedule_version_key IN ({placeholders})",
                keys,
            ).fetchall()
        ]
        if not run_ids:
            return 0
        ph2 = ", ".join("?" for _ in run_ids)
        cur = conn.execute(f"DELETE FROM {table} WHERE cpm_run_id IN ({ph2})", run_ids)
        return int(cur.rowcount)
    if "review_item_id" in columns and "project_schedule_review_items" in {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        review_ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT review_item_id FROM project_schedule_review_items WHERE project_key=?",
                (project_key,),
            ).fetchall()
        ]
        if not review_ids:
            return 0
        placeholders = ", ".join("?" for _ in review_ids)
        cur = conn.execute(
            f"DELETE FROM {table} WHERE review_item_id IN ({placeholders})",
            review_ids,
        )
        return int(cur.rowcount)
    if "named_baseline_review_item_id" in columns and "project_schedule_named_baseline_review_items" in {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        item_ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT named_baseline_review_item_id FROM project_schedule_named_baseline_review_items WHERE project_key=?",
                (project_key,),
            ).fetchall()
        ]
        if not item_ids:
            return 0
        placeholders = ", ".join("?" for _ in item_ids)
        cur = conn.execute(
            f"DELETE FROM {table} WHERE named_baseline_review_item_id IN ({placeholders})",
            item_ids,
        )
        return int(cur.rowcount)
    return 0


def _collect_purge_tables(audit: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    purge_tables: set[str] = set()
    manual_review: list[dict[str, Any]] = []
    for row in audit.get("discovered_by_heuristic", []):
        table = row["table"]
        if not is_schedule_domain_table(table):
            continue
        if row.get("preserve_catalog"):
            continue
        if row.get("purgeable_for_project") or row.get("count_strategy") != "preserve_catalog":
            if row.get("count_strategy") == "global_or_skip" and table not in PURGE_TABLE_STRATEGIES:
                if row.get("row_count_for_project"):
                    manual_review.append({"table": table, "reason": "unknown_count_strategy"})
                continue
            purge_tables.add(table)
        elif row.get("row_count_for_project"):
            manual_review.append({"table": table, "reason": "schedule_like_unclassified"})
    return purge_tables, manual_review


def _fk_edges(conn: sqlite3.Connection, tables: set[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for table in tables:
        for row in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            parent = str(row[2])
            if parent in tables:
                edges.append((table, parent))
    return edges


def _remaining_schedule_count(audit: dict[str, Any]) -> int:
    total = 0
    for row in audit.get("discovered_by_heuristic", []):
        if row.get("preserve_catalog"):
            continue
        if not is_schedule_domain_table(str(row["table"])):
            continue
        val = row.get("row_count_for_project")
        if isinstance(val, int) and val > 0:
            total += val
    return total


def _schedule_row_counts(
    audit: dict[str, Any],
    project_key: str,
    *,
    include_tables: set[str] | None = None,
    only_positive: bool = False,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    if include_tables is not None:
        for table in sorted(include_tables):
            counts[table] = 0
        for row in audit.get("discovered_by_heuristic", []):
            table = row["table"]
            if table not in include_tables:
                continue
            val = row.get("row_count_for_project")
            if isinstance(val, int):
                counts[table] = val
        return counts

    for row in audit.get("discovered_by_heuristic", []):
        if row.get("preserve_catalog"):
            continue
        val = row.get("row_count_for_project")
        if isinstance(val, int):
            if only_positive and val <= 0:
                continue
            counts[row["table"]] = val
    return counts


def run_tropical_purge(
    db_path: str,
    *,
    project_key: str = "tropical",
    dry_run: bool = True,
    apply: bool = False,
) -> dict[str, Any]:
    audit_before = build_schema_audit_report(db_path, project_key=project_key)
    purge_tables, manual_review = _collect_purge_tables(audit_before)
    before_counts = _schedule_row_counts(audit_before, project_key, only_positive=True)

    conn = sqlite3.connect(db_path)
    deleted_counts: dict[str, int] = {}
    try:
        fk_edges = _fk_edges(conn, purge_tables)
        delete_order = topological_delete_order(purge_tables, fk_edges)
        planned = [{"table": t, "strategy": PURGE_TABLE_STRATEGIES.get(t, "derived")} for t in delete_order]
        if apply and not dry_run:
            conn.execute("PRAGMA foreign_keys=ON")
            for table in delete_order:
                strategy = PURGE_TABLE_STRATEGIES.get(table, "derived")
                deleted_counts[table] = _delete_for_project(conn, table, project_key, strategy)
            # Final sweep for project_key schedule tables missed by ordering.
            for table in sorted(purge_tables):
                if table in deleted_counts and deleted_counts[table]:
                    continue
                deleted_counts[table] = _delete_for_project(conn, table, project_key, "derived")
            conn.commit()
    finally:
        conn.close()

    audit_after = build_schema_audit_report(db_path, project_key=project_key)
    after_counts = _schedule_row_counts(
        audit_after,
        project_key,
        include_tables=set(before_counts),
    )
    remaining = _remaining_schedule_count(audit_after)

    catalog_preserved = True
    try:
        with sqlite3.connect(db_path) as c2:
            catalog_preserved = (
                int(
                    c2.execute(
                        "SELECT COUNT(*) FROM procore_ep_projects WHERE project_key=?",
                        (project_key,),
                    ).fetchone()[0]
                )
                >= 1
            )
    except sqlite3.Error:
        catalog_preserved = False

    return {
        "mode": "schedule_clean_db_purge",
        "db_path": db_path,
        "project_key": project_key,
        "dry_run": dry_run,
        "apply": apply,
        "before_counts": before_counts,
        "planned_delete_order": planned,
        "deleted_counts": deleted_counts if apply and not dry_run else {},
        "after_counts": after_counts,
        "remaining_tropical_schedule_records": remaining,
        "project_catalog_preserved": catalog_preserved,
        "live_db_protection": True,
        "manual_review_required": manual_review,
        "warnings": [],
    }
