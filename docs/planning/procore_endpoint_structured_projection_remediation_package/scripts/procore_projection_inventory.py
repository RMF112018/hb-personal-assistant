#!/usr/bin/env python3
"""Safe Procore payload field inventory helper.

This helper intentionally emits JSON paths, types and counts only. It does not emit
payload values. It is suitable for /tmp DB-copy validation evidence.

Usage:
    python scripts/procore_projection_inventory.py --db /tmp/copy.sqlite --out /tmp/inventory.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

Scalar = str | int | float | bool | None


def walk(value: Any, prefix: str = "$"):
    if isinstance(value, dict):
        yield prefix, "object"
        for key, child in value.items():
            safe_key = str(key).replace(".", "\\.")
            yield from walk(child, f"{prefix}.{safe_key}")
    elif isinstance(value, list):
        yield prefix, "array"
        for child in value:
            yield from walk(child, f"{prefix}[]")
    else:
        yield prefix, type(value).__name__


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

    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    non_null: dict[tuple[str, str, str], int] = defaultdict(int)

    sql = """
        SELECT endpoint_key, payload_json
        FROM procore_endpoint_raw_payloads
        WHERE raw_procore_payload_persisted = 1
        ORDER BY endpoint_key, payload_seen_last_utc DESC
    """
    if args.limit and args.limit > 0:
        sql += f" LIMIT {int(args.limit)}"

    with sqlite3.connect(db) as conn:
        for endpoint_key, payload_json in conn.execute(sql):
            try:
                payload = json.loads(payload_json)
            except Exception:
                counts[(endpoint_key, "$", "invalid_json")] += 1
                continue
            for path, typ in walk(payload):
                key = (endpoint_key, path, typ)
                counts[key] += 1
                # We do not emit values. This only distinguishes observed non-empty shape.
                if typ not in {"NoneType"}:
                    non_null[key] += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["endpoint_key", "json_path", "observed_type", "occurrence_count", "non_null_shape_count"])
        for (endpoint_key, path, typ), count in sorted(counts.items()):
            writer.writerow([endpoint_key, path, typ, count, non_null.get((endpoint_key, path, typ), 0)])

    print(f"wrote={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
