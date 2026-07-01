#!/usr/bin/env python3
"""Phase 13A read-only Tropical schedule DB inventory."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path.home() / "Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
EVIDENCE = Path(__file__).resolve().parent


def _query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        schema = _query(
            conn,
            "SELECT MAX(version) AS version, MAX(applied_at) AS applied_at FROM schema_migrations",
        )
        tables = {
            row["name"]
            for row in _query(
                conn,
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            )
        }
        versions = _query(
            conn,
            """
            SELECT import_id, schedule_version_key, source_filename_redacted, created_at, activity_count
            FROM schedule_file_imports
            WHERE project_key='tropical' AND import_status='committed'
            ORDER BY created_at DESC
            """,
        )
        named_slots = []
        if "project_schedule_named_baseline_slots" in tables:
            named_slots = _query(
                conn,
                """
                SELECT slot_key, schedule_version_key, display_name, selected_at, selected_by, is_active
                FROM project_schedule_named_baseline_slots
                WHERE project_key='tropical' AND is_active=1
                ORDER BY slot_key
                """,
            )
        named_dispositions = 0
        if "project_schedule_named_baseline_review_items" in tables:
            named_dispositions = conn.execute(
                """
                SELECT COUNT(*) FROM project_schedule_named_baseline_review_items
                WHERE project_key='tropical'
                """,
            ).fetchone()[0]
        legacy_baseline = _query(
            conn,
            """
            SELECT current_schedule_version_key, selected_baseline_schedule_version_key, updated_at
            FROM project_schedule_baseline_selections
            WHERE project_key='tropical'
            ORDER BY updated_at DESC LIMIT 5
            """,
        )

    payload = {
        "stamp": stamp,
        "db_path": str(DB),
        "mode": "read_only",
        "project_key": "tropical",
        "schema": schema[0] if schema else {},
        "named_baseline_slots": named_slots,
        "named_disposition_row_count": named_dispositions,
        "legacy_baseline_selections": legacy_baseline,
        "committed_import_count": len(versions),
        "committed_versions": versions,
        "tables_present": {
            "project_schedule_named_baseline_slots": "project_schedule_named_baseline_slots" in tables,
            "project_schedule_named_baseline_review_items": "project_schedule_named_baseline_review_items"
            in tables,
            "project_schedule_named_baseline_review_item_events": "project_schedule_named_baseline_review_item_events"
            in tables,
        },
    }
    (EVIDENCE / "tropical-readonly-db-inventory.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Tropical Read-Only DB Inventory (Phase 13A)",
        "",
        f"**Stamp:** {stamp}",
        f"**DB:** `{DB}` (opened `mode=ro`)",
        "",
        "## Schema",
        "",
        f"- Latest migration: **{payload['schema'].get('version')}** ({payload['schema'].get('applied_at')})",
        "",
        "## Named baseline slots (tropical)",
        "",
    ]
    if named_slots:
        lines.append("| slot_key | schedule_version_key | status |")
        lines.append("|----------|---------------------|--------|")
        for row in named_slots:
            lines.append(
                f"| {row['slot_key']} | `{row['schedule_version_key']}` | active={row['is_active']} |"
            )
    else:
        lines.append("_No named baseline rows (table missing or empty)._")
    lines.extend(
        [
            "",
            f"## Named disposition rows: **{named_dispositions}**",
            "",
            f"## Committed imports: **{len(versions)}**",
            "",
        ]
    )
    for row in versions[:12]:
        lines.append(f"- `{row['schedule_version_key']}` — {row.get('source_filename_redacted')}")
    (EVIDENCE / "tropical-readonly-db-inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"committed_imports": len(versions), "named_slots": len(named_slots)}, indent=2))


if __name__ == "__main__":
    main()
