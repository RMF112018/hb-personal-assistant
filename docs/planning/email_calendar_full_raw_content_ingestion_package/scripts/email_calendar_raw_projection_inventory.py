#!/usr/bin/env python3
"""Safe email/calendar raw field inventory helper.

This helper emits column names, JSON paths, observed types and counts only. It does
not emit raw email/calendar values. It is suitable for /tmp DB-copy validation
evidence.

Usage:
    python scripts/email_calendar_raw_projection_inventory.py --db /tmp/copy.sqlite --out /tmp/inventory.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

RAW_TABLES = {
    "email": {
        "email_message_raw_content": [
            "to_recipients_json",
            "cc_recipients_json",
            "bcc_recipients_json",
            "attachment_metadata_json",
        ],
        "email_thread_raw_context": ["messages_json", "source_refs_json"],
    },
    "calendar": {
        "calendar_event_raw_content": ["attendees_json", "recurrence_json"],
    },
}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


def walk_json(value: Any, prefix: str = "$"):
    if isinstance(value, dict):
        yield prefix, "object"
        for key, child in value.items():
            safe_key = str(key).replace(".", "\\.")
            yield from walk_json(child, f"{prefix}.{safe_key}")
    elif isinstance(value, list):
        yield prefix, "array"
        for child in value:
            yield from walk_json(child, f"{prefix}[]")
    else:
        yield prefix, type(value).__name__


def value_type(value: Any) -> str:
    if value is None:
        return "NoneType"
    if isinstance(value, str):
        return "str"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return type(value).__name__


def is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    db = Path(args.db)
    out = Path(args.out)
    if not db.exists():
        raise SystemExit(f"DB not found: {db}")

    counts: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    non_null: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    empty: dict[tuple[str, str, str, str, str], int] = defaultdict(int)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        for source_family, tables in RAW_TABLES.items():
            for table, json_cols in tables.items():
                if not table_exists(conn, table):
                    continue
                cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
                sql = f"SELECT * FROM {table}"
                if args.limit and args.limit > 0:
                    sql += f" LIMIT {int(args.limit)}"
                for row in conn.execute(sql):
                    d = dict(row)
                    for col in cols:
                        val = d.get(col)
                        key = (source_family, table, col, "column", value_type(val))
                        counts[key] += 1
                        if is_non_empty(val):
                            non_null[key] += 1
                        else:
                            empty[key] += 1

                    for col in json_cols:
                        raw = d.get(col)
                        if raw is None or str(raw).strip() == "":
                            continue
                        try:
                            parsed = json.loads(raw)
                        except Exception:
                            key = (source_family, table, f"{col}:$", "json_path", "invalid_json")
                            counts[key] += 1
                            empty[key] += 1
                            continue
                        for path, typ in walk_json(parsed):
                            key = (source_family, table, f"{col}:{path}", "json_path", typ)
                            counts[key] += 1
                            if typ != "NoneType":
                                non_null[key] += 1
                            else:
                                empty[key] += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "source_family",
                "source_table",
                "raw_column_or_json_path",
                "path_kind",
                "observed_type",
                "occurrence_count",
                "non_null_count",
                "empty_count",
            ]
        )
        for key, count in sorted(counts.items()):
            writer.writerow([*key, count, non_null.get(key, 0), empty.get(key, 0)])

    print(f"wrote={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
