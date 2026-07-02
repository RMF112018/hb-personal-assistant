#!/usr/bin/env python3
"""Probe whether schedule import preview mutates schedule table rows."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.import_preview_probe import (
    run_import_preview_mutation_probe,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _seed_project(db: Path, *, project_key: str) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO procore_ep_projects (
              record_key, endpoint_key, project_key, project_id, display_name, project_number,
              record_id, source_quality, is_current, created_utc, updated_utc,
              external_writeback_performed, raw_payload_emitted_to_read_model,
              raw_payload_emitted_to_evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"rk-{project_key}",
                "projects",
                project_key,
                "9001",
                "Tropical Wind",
                None,
                "9001",
                "ok",
                1,
                "2026-06-22T00:00:00Z",
                "2026-06-22T00:00:00Z",
                0,
                0,
                0,
            ),
        )
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--project-key", default="tropical")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)

    db = Path(args.db_path)
    if not db.exists():
        _seed_project(db, project_key=args.project_key)

    result = run_import_preview_mutation_probe(
        db,
        project_key=args.project_key,
        fixture_path=args.fixture,
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
