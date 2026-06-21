#!/usr/bin/env python3
"""Safe budget dynamic column audit (read-only SQLite). No raw cell values exported."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from hb_assistant.forecasting.budget_column_roles import load_budget_column_roles, procore_label_to_role_key
from hb_assistant.forecasting.field_classifiers import classify_amount_field


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    ).fetchone()
    return row is not None


def _classify_column(
    *,
    column_key: str,
    name: str,
    label: str,
    data_type: str,
    role_key: str | None,
    roles_catalog: dict,
) -> str:
    if role_key and role_key in roles_catalog:
        role_meta = roles_catalog[role_key]
        source_type = str(role_meta.get("source_type") or "")
        if source_type == "calculated":
            return "known_calculated_rollup"
        return "standard_known_column"
    lowered = (column_key or name or label or "").lower()
    if data_type in ("standard",) and lowered in ("budget code", "description", "detail type", "item", "vendor"):
        return "custom_status_or_dimension"
    if data_type in ("standard",) and "note" in lowered:
        return "custom_text_or_note"
    amount_kind = classify_amount_field(
        table="procore_ep_budget_detail_row_cells",
        column=name or column_key,
        declared_type="TEXT",
    )
    kind = str(amount_kind.get("kind") or "")
    if kind == "true_monetary_amount":
        return "custom_numeric_candidate"
    if kind in ("enum_status_dimension", "text_description", "identifier_key"):
        return "custom_status_or_dimension" if "status" in lowered else "custom_text_or_note"
    if data_type in ("source", "budget_forecast"):
        return "review_required"
    return "review_required"


def audit_budget_dynamic_columns(db_path: Path) -> dict:
    catalog = load_budget_column_roles()
    roles = catalog.get("budget_column_roles", {})
    if not isinstance(roles, dict):
        roles = {}

    result: dict = {
        "db_path": str(db_path),
        "budget_views": [],
        "column_profiles": [],
        "classification_counts": {},
        "unmapped_numeric_candidates": [],
    }

    with _connect_ro(db_path) as conn:
        if not _table_exists(conn, "procore_ep_budget_detail_columns"):
            result["error"] = "procore_ep_budget_detail_columns missing"
            return result

        views = conn.execute(
            """
            SELECT budget_view_id, COUNT(*) AS column_defs, COUNT(DISTINCT column_key) AS distinct_keys
            FROM procore_ep_budget_detail_columns
            WHERE is_current = 1
            GROUP BY budget_view_id
            """
        ).fetchall()
        result["budget_views"] = [dict(v) for v in views]

        columns = conn.execute(
            """
            SELECT budget_view_id, column_id, column_key, name, label, data_type, field_path,
                   COUNT(*) AS definition_rows
            FROM procore_ep_budget_detail_columns
            WHERE is_current = 1
            GROUP BY budget_view_id, column_id, column_key, name, label, data_type, field_path
            """
        ).fetchall()

        cell_stats: dict[tuple[str, str], dict] = {}
        if _table_exists(conn, "procore_ep_budget_detail_row_cells"):
            cell_rows = conn.execute(
                """
                SELECT column_key, column_name,
                       SUM(CASE WHEN value_decimal_text IS NOT NULL AND TRIM(value_decimal_text) <> '' THEN 1 ELSE 0 END) AS numeric_cells,
                       SUM(CASE WHEN value_text IS NOT NULL AND TRIM(value_text) <> '' THEN 1 ELSE 0 END) AS text_cells,
                       COUNT(*) AS total_cells
                FROM procore_ep_budget_detail_row_cells
                WHERE is_current = 1
                GROUP BY column_key, column_name
                """
            ).fetchall()
            for row in cell_rows:
                key = (str(row["column_key"] or ""), str(row["column_name"] or ""))
                cell_stats[key] = {
                    "numeric_cells": int(row["numeric_cells"] or 0),
                    "text_cells": int(row["text_cells"] or 0),
                    "total_cells": int(row["total_cells"] or 0),
                }

        classifications: Counter[str] = Counter()
        for col in columns:
            column_key = str(col["column_key"] or "")
            name = str(col["name"] or "")
            label = str(col["label"] or "")
            data_type = str(col["data_type"] or "")
            role_key = procore_label_to_role_key(column_key or name or label)
            classification = _classify_column(
                column_key=column_key,
                name=name,
                label=label,
                data_type=data_type,
                role_key=role_key,
                roles_catalog=roles,
            )
            classifications[classification] += 1
            stats = cell_stats.get((column_key, name), {})
            profile = {
                "budget_view_id": col["budget_view_id"],
                "column_id": col["column_id"],
                "column_key": column_key,
                "name": name,
                "label": label,
                "data_type": data_type,
                "field_path": col["field_path"],
                "mapped_role_key": role_key,
                "classification": classification,
                "definition_rows": int(col["definition_rows"] or 0),
                **stats,
            }
            result["column_profiles"].append(profile)
            if classification in ("custom_numeric_candidate", "review_required") and stats.get("numeric_cells", 0) > 0:
                result["unmapped_numeric_candidates"].append(
                    {
                        "column_key": column_key,
                        "name": name,
                        "classification": classification,
                        "numeric_cells": stats.get("numeric_cells", 0),
                    }
                )

        result["classification_counts"] = dict(classifications)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit budget dynamic columns (read-only)")
    parser.add_argument("--db-path", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = audit_budget_dynamic_columns(args.db_path)
    payload = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())