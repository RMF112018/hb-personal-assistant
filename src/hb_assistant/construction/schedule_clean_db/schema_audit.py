"""Schema-driven schedule table inventory for clean-DB validation."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.db_path_guard import is_live_db_path
from hb_assistant.construction.data_quality.table_inventory import _live_user_tables
from hb_assistant.store.migrator import SQLiteMigrator

NAME_TERMS = ("schedule", "baseline", "review", "cpm", "quality", "portfolio")
COLUMN_TERMS = (
    "project_key",
    "schedule_version_key",
    "current_schedule_version_key",
    "baseline_schedule_version_key",
    "import_id",
    "package_id",
    "review_item_id",
)

CATALOG_PRESERVE_TABLES = frozenset(
    {
        "procore_ep_projects",
        "schema_migrations",
        "sqlite_sequence",
    }
)

REQUIRED_EXPECTED_TABLES: dict[str, dict[str, str]] = {
    "schedule_file_imports": {"domain": "imports", "optional": "false"},
    "schedule_import_packages": {"domain": "packages", "optional": "false"},
    "schedule_import_package_files": {"domain": "packages", "optional": "false"},
    "schedule_package_equivalence_facts": {"domain": "packages", "optional": "true"},
    "schedule_package_field_lineage": {"domain": "lineage", "optional": "true"},
    "schedule_source_capabilities": {"domain": "capabilities", "optional": "true"},
    "schedule_baseline_projects": {"domain": "baseline", "optional": "true"},
    "schedule_baseline_health_facts": {"domain": "baseline", "optional": "true"},
    "schedule_baseline_activity_crosswalk": {"domain": "baseline", "optional": "true"},
    "schedule_cpm_import_observability": {"domain": "cpm_observability", "optional": "true"},
    "schedule_cpm_runs": {"domain": "cpm", "optional": "true"},
    "schedule_cpm_activity_results": {"domain": "cpm", "optional": "true"},
    "schedule_cpm_relationship_results": {"domain": "cpm", "optional": "true"},
    "schedule_cpm_paths": {"domain": "cpm", "optional": "true"},
    "schedule_cpm_path_activities": {"domain": "cpm", "optional": "true"},
    "schedule_cpm_diagnostics": {"domain": "cpm", "optional": "true"},
    "schedule_quality_evaluation_runs": {"domain": "quality", "optional": "true"},
    "schedule_quality_metric_results": {"domain": "quality", "optional": "true"},
    "schedule_quality_scorecards": {"domain": "quality", "optional": "true"},
    "project_schedule_series_membership": {"domain": "membership", "optional": "true"},
    "project_schedule_baseline_selections": {"domain": "baseline_selection", "optional": "true"},
    "project_schedule_review_items": {"domain": "review", "optional": "true"},
    "project_schedule_review_events": {"domain": "review", "optional": "true"},
    "project_schedule_named_baseline_slots": {"domain": "named_baseline", "optional": "true"},
    "project_schedule_named_baseline_review_items": {"domain": "named_baseline_review", "optional": "true"},
    "project_schedule_named_baseline_review_events": {"domain": "named_baseline_review", "optional": "true"},
    "procore_ep_schedule_activities": {"domain": "graph", "optional": "false"},
    "procore_ep_schedule_relationships": {"domain": "graph", "optional": "false"},
    "procore_ep_schedule_wbs_nodes": {"domain": "graph", "optional": "true"},
    "procore_ep_schedule_calendars": {"domain": "graph", "optional": "true"},
    "procore_ep_schedule_activity_code_assignments": {"domain": "graph", "optional": "true"},
    "procore_ep_schedule_udf_values": {"domain": "graph", "optional": "true"},
    "schedule_version_diffs": {"domain": "diffs", "optional": "true"},
    "schedule_version_diff_detail_facts": {"domain": "diffs", "optional": "true"},
    "schedule_version_diff_impact_rollups": {"domain": "diffs", "optional": "true"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_ro(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).expanduser().resolve()
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
    except sqlite3.Error:
        return []


def _foreign_keys(conn: sqlite3.Connection, table: str) -> list[dict[str, str]]:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    except sqlite3.Error:
        return []
    return [
        {
            "from_column": str(row[3]),
            "to_table": str(row[2]),
            "to_column": str(row[4]),
        }
        for row in rows
    ]


def _primary_key_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall() if row[5]]
    except sqlite3.Error:
        return []


def _matches_heuristic(table: str, columns: list[str]) -> bool:
    lower = table.lower()
    if any(term in lower for term in NAME_TERMS):
        return True
    return any(col in columns for col in COLUMN_TERMS)


def _count_strategy(table: str, columns: list[str]) -> str:
    if table in CATALOG_PRESERVE_TABLES:
        return "preserve_catalog"
    if "project_key" in columns:
        return "by_project_key"
    if "schedule_version_key" in columns:
        return "by_schedule_version_key_via_imports"
    if "import_id" in columns:
        return "by_import_id_via_imports"
    if "package_id" in columns:
        return "by_package_id_via_packages"
    if "review_item_id" in columns:
        return "by_review_item_via_project"
    return "global_or_skip"


def _count_for_project(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    project_key: str,
    strategy: str,
) -> int | None:
    try:
        if strategy == "preserve_catalog":
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        if strategy == "by_project_key":
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE project_key=?",
                    (project_key,),
                ).fetchone()[0]
            )
        if strategy == "by_schedule_version_key_via_imports":
            return int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) FROM {table} t
                    WHERE EXISTS (
                      SELECT 1 FROM schedule_file_imports i
                      WHERE i.project_key=? AND i.schedule_version_key=t.schedule_version_key
                    )
                    """,
                    (project_key,),
                ).fetchone()[0]
            )
        if strategy == "by_import_id_via_imports":
            return int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) FROM {table} t
                    WHERE EXISTS (
                      SELECT 1 FROM schedule_file_imports i
                      WHERE i.project_key=? AND i.import_id=t.import_id
                    )
                    """,
                    (project_key,),
                ).fetchone()[0]
            )
        if strategy == "by_package_id_via_packages":
            if "schedule_import_packages" not in _live_user_tables(conn):
                return None
            return int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) FROM {table} t
                    WHERE EXISTS (
                      SELECT 1 FROM schedule_import_packages p
                      WHERE p.project_key=? AND p.package_id=t.package_id
                    )
                    """,
                    (project_key,),
                ).fetchone()[0]
            )
        if strategy == "by_review_item_via_project":
            if "project_schedule_review_items" not in _live_user_tables(conn):
                return None
            return int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) FROM {table} t
                    WHERE EXISTS (
                      SELECT 1 FROM project_schedule_review_items r
                      WHERE r.project_key=? AND r.review_item_id=t.review_item_id
                    )
                    """,
                    (project_key,),
                ).fetchone()[0]
            )
        if strategy == "global_or_skip":
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return None
    return None


def _classify_table(table: str, columns: list[str]) -> dict[str, Any]:
    strategy = _count_strategy(table, columns)
    preserve = table in CATALOG_PRESERVE_TABLES
    purgeable = not preserve and strategy != "preserve_catalog" and _matches_heuristic(table, columns)
    return {
        "purgeable_for_project": purgeable,
        "preserve_catalog": preserve,
        "count_strategy": strategy,
    }


def build_schema_audit_report(
    db_path: str | Path,
    *,
    project_key: str,
    read_only_live: bool = False,
) -> dict[str, Any]:
    if is_live_db_path(db_path) and not read_only_live:
        raise ValueError("live database path rejected; pass read_only_live=True for read-only access")

    conn = _open_ro(db_path)
    try:
        tables = sorted(_live_user_tables(conn))
        discovered: list[dict[str, Any]] = []
        classified_names: set[str] = set()

        for table in tables:
            columns = _table_columns(conn, table)
            if not _matches_heuristic(table, columns) and table not in REQUIRED_EXPECTED_TABLES:
                continue
            classification = _classify_table(table, columns)
            row_count = _count_for_project(
                conn, table, columns, project_key, classification["count_strategy"]
            )
            entry = {
                "table": table,
                "primary_key_columns": _primary_key_columns(conn, table),
                "foreign_keys": _foreign_keys(conn, table),
                "relevant_columns": [c for c in columns if c in COLUMN_TERMS],
                **classification,
                "row_count_for_project": row_count,
            }
            discovered.append(entry)
            classified_names.add(table)

        missing_or_unclassified: list[dict[str, Any]] = []
        for table, meta in REQUIRED_EXPECTED_TABLES.items():
            if table not in tables:
                missing_or_unclassified.append(
                    {
                        "table": table,
                        "status": "missing_optional" if meta.get("optional") == "true" else "missing_required",
                        "domain": meta["domain"],
                    }
                )
            elif table not in classified_names:
                missing_or_unclassified.append(
                    {
                        "table": table,
                        "status": "present_but_unclassified",
                        "domain": meta["domain"],
                    }
                )

        schema_version = 0
        try:
            schema_version = int(SQLiteMigrator(db_path=str(db_path)).current_version())
        except Exception:
            pass

        return {
            "mode": "schedule_clean_db_schema_audit",
            "generated_at": _now(),
            "db_path": str(Path(db_path).expanduser().resolve()),
            "project_key": project_key,
            "schema_version": schema_version,
            "discovered_by_heuristic": discovered,
            "required_expected_tables_missing_or_unclassified": missing_or_unclassified,
        }
    finally:
        conn.close()


def render_schema_audit_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Schedule schema audit",
        "",
        f"- project_key: `{report.get('project_key')}`",
        f"- schema_version: `{report.get('schema_version')}`",
        f"- discovered tables: `{len(report.get('discovered_by_heuristic', []))}`",
        f"- gaps: `{len(report.get('required_expected_tables_missing_or_unclassified', []))}`",
        "",
        "## Discovered by heuristic",
        "",
    ]
    for row in report.get("discovered_by_heuristic", []):
        lines.append(
            f"- `{row['table']}` — count={row.get('row_count_for_project')} "
            f"strategy={row.get('count_strategy')} purgeable={row.get('purgeable_for_project')}"
        )
    lines.extend(["", "## Required expected gaps", ""])
    for row in report.get("required_expected_tables_missing_or_unclassified", []):
        lines.append(f"- `{row['table']}` — {row.get('status')} ({row.get('domain')})")
    lines.append("")
    return "\n".join(lines)


def write_schema_audit_outputs(
    report: dict[str, Any],
    *,
    json_out: str | Path | None = None,
    md_out: str | Path | None = None,
) -> None:
    if json_out:
        Path(json_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if md_out:
        Path(md_out).write_text(render_schema_audit_markdown(report), encoding="utf-8")
