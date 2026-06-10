#!/usr/bin/env python3
"""Read-only probe for email/calendar raw content coverage.

This script resolves Bobby's production DB path through PathPolicy unless --db-path is
provided, copies the DB to /tmp, then runs count/null-rate/source-quality checks on the
copy. It never prints raw body values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RAW_TABLES = [
    "raw_content_policy_state",
    "email_message_raw_content",
    "email_thread_raw_context",
    "calendar_event_raw_content",
    "raw_content_model_context_packets",
    "raw_content_access_events",
]

LEGACY_TABLES = [
    "emails",
    "email_messages",
    "calendar_events",
    "calendar_event_index",
]

BODY_SENTINEL_COLUMNS = {
    "email_message_raw_content": ["body_preview", "body_text", "body_html"],
    "email_thread_raw_context": ["messages_json"],
    "calendar_event_raw_content": ["body_preview", "body_text", "body_html", "attendees_json", "join_url"],
}

SECRET_PATTERNS = [
    "Authorization: Bearer",
    "refresh_token",
    "access_token",
    "client_secret",
    "@microsoft.graph.downloadUrl",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_db_path(repo: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    sys.path.insert(0, str(repo / "src"))
    from hb_assistant.config.path_policy import PathPolicy  # type: ignore

    return PathPolicy().get_db_path().expanduser().resolve()


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if not table_exists(conn, table):
        return []
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def scalar(conn: sqlite3.Connection, sql: str) -> Any:
    try:
        row = conn.execute(sql).fetchone()
        return row[0] if row else None
    except sqlite3.Error as exc:
        return {"error": type(exc).__name__, "message": str(exc)}


def table_count(conn: sqlite3.Connection, table: str) -> int | None:
    if not table_exists(conn, table):
        return None
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def non_null_count(conn: sqlite3.Connection, table: str, column: str) -> int | None:
    cols = columns(conn, table)
    if column not in cols:
        return None
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {column} IS NOT NULL AND length(CAST({column} AS TEXT)) > 0"
    ).fetchone()
    return int(row[0])


def source_quality_distribution(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if "source_quality" not in columns(conn, table):
        return []
    rows = conn.execute(
        f"SELECT source_quality, COUNT(*) AS rows FROM {table} GROUP BY source_quality ORDER BY rows DESC, source_quality"
    ).fetchall()
    return [dict(r) for r in rows]


def coverage_table(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "table": table,
        "exists": table_exists(conn, table),
        "rows": table_count(conn, table),
        "columns": columns(conn, table),
        "source_quality_distribution": source_quality_distribution(conn, table),
    }
    for col in ["body_preview", "body_text", "body_html", "messages_json", "attendees_json", "join_url"]:
        n = non_null_count(conn, table, col)
        if n is not None:
            result[f"{col}_non_null"] = n
    return result


def secret_scan_counts(conn: sqlite3.Connection) -> dict[str, Any]:
    """Count potential secret pattern occurrences inside raw body-capable columns.

    This returns counts only and never returns matching values.
    """
    findings: dict[str, Any] = {}
    for table, cols in BODY_SENTINEL_COLUMNS.items():
        if not table_exists(conn, table):
            continue
        existing_cols = set(columns(conn, table))
        table_findings = {}
        for col in cols:
            if col not in existing_cols:
                continue
            col_findings = {}
            for pattern in SECRET_PATTERNS:
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE ?",
                    (f"%{pattern}%",),
                ).fetchone()
                col_findings[pattern] = int(row[0])
            table_findings[col] = col_findings
        findings[table] = table_findings
    return findings


def consumer_matrix(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    def has_rows(table: str) -> bool:
        count = table_count(conn, table)
        return bool(count and count > 0)

    email_raw = has_rows("email_message_raw_content") or has_rows("email_thread_raw_context")
    cal_raw = has_rows("calendar_event_raw_content")
    packets = has_rows("raw_content_model_context_packets")
    access = has_rows("raw_content_access_events")

    return [
        {
            "consumer": "daily brief email follow-ups",
            "before_source": "email_followup_enrichments / metadata summaries",
            "after_source_available": email_raw,
            "verdict": "raw_available" if email_raw else "blocked_or_not_yet_populated",
        },
        {
            "consumer": "daily brief meeting prep",
            "before_source": "calendar_event_index / meeting_prep_brief_sections",
            "after_source_available": cal_raw,
            "verdict": "raw_available" if cal_raw else "blocked_or_not_yet_populated",
        },
        {
            "consumer": "model context packets",
            "before_source": "bounded/redacted packet receipts",
            "after_source_available": packets,
            "verdict": "packet_rows_present" if packets else "no_packet_rows_observed",
        },
        {
            "consumer": "raw access audit",
            "before_source": "n/a",
            "after_source_available": access,
            "verdict": "access_events_present" if access else "no_access_events_observed",
        },
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/Users/bobbyfetting/hb-personal-assistant")
    ap.add_argument("--db-path", default=None)
    ap.add_argument("--output", default=None)
    ap.add_argument("--keep-copy", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    db_path = resolve_db_path(repo, args.db_path)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    before_hash = sha256_file(db_path)
    before_stat = db_path.stat()

    tmp_dir = Path(tempfile.mkdtemp(prefix="email-calendar-raw-probe-"))
    copy_path = tmp_dir / db_path.name
    shutil.copy2(db_path, copy_path)

    conn = connect_readonly(copy_path)
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "production_db_path_hash": hashlib.sha256(str(db_path).encode()).hexdigest()[:16],
        "production_db_sha256_before": before_hash,
        "production_db_mtime_before": before_stat.st_mtime,
        "tmp_copy": str(copy_path),
        "schema_head": scalar(conn, "SELECT MAX(version) FROM schema_migrations"),
        "tables": {},
        "consumer_matrix": [],
        "secret_pattern_counts": {},
        "production_db_unchanged_after_probe": None,
    }

    for table in RAW_TABLES + LEGACY_TABLES:
        report["tables"][table] = coverage_table(conn, table)

    report["consumer_matrix"] = consumer_matrix(conn)
    report["secret_pattern_counts"] = secret_scan_counts(conn)
    conn.close()

    after_hash = sha256_file(db_path)
    after_stat = db_path.stat()
    report["production_db_sha256_after"] = after_hash
    report["production_db_mtime_after"] = after_stat.st_mtime
    report["production_db_unchanged_after_probe"] = (
        before_hash == after_hash and before_stat.st_mtime == after_stat.st_mtime
    )

    if not args.keep_copy:
        try:
            copy_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
            report["tmp_copy_removed"] = True
        except OSError:
            report["tmp_copy_removed"] = False
    else:
        report["tmp_copy_removed"] = False

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(json.dumps({
            "status": "ok",
            "output": args.output,
            "schema_head": report["schema_head"],
            "production_db_unchanged_after_probe": report["production_db_unchanged_after_probe"],
        }, indent=2))
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
