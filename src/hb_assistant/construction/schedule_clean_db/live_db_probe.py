"""Live DB unchanged probe for schedule validation safety."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.db_path_guard import is_live_db_path
from hb_assistant.construction.schedule_clean_db.schema_audit import build_schema_audit_report
from hb_assistant.store.migrator import SQLiteMigrator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_meta(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = None
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
    except OSError:
        pass
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
        "sha256": digest,
    }


def snapshot_live_db(
    live_db_path: str | Path,
    *,
    project_key: str,
    read_only_live: bool = False,
) -> dict[str, Any]:
    path = Path(live_db_path).expanduser().resolve()
    if is_live_db_path(path) and not read_only_live:
        raise ValueError("live database snapshot requires --read-only-live")
    audit = build_schema_audit_report(path, project_key=project_key, read_only_live=True)
    schedule_counts = {
        row["table"]: row.get("row_count_for_project", 0)
        for row in audit.get("discovered_by_heuristic", [])
        if not row.get("preserve_catalog")
    }
    schema_version = 0
    try:
        schema_version = int(SQLiteMigrator(db_path=str(path)).current_version())
    except Exception:
        pass
    return {
        "mode": "schedule_live_db_snapshot",
        "timestamp": _now(),
        "live_db_path": str(path),
        "project_key": project_key,
        "read_only_live": read_only_live or is_live_db_path(path),
        "file_metadata": _file_meta(path),
        "schema_version": schema_version,
        "schedule_table_counts": schedule_counts,
    }


def compare_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    before_counts = before.get("schedule_table_counts", {})
    after_counts = after.get("schedule_table_counts", {})
    changed: dict[str, dict[str, int]] = {}
    for table, bcount in before_counts.items():
        acount = after_counts.get(table, 0)
        if bcount != acount:
            changed[table] = {"before": int(bcount or 0), "after": int(acount or 0)}
    hash_warning = None
    bhash = (before.get("file_metadata") or {}).get("sha256")
    ahash = (after.get("file_metadata") or {}).get("sha256")
    if bhash and ahash and bhash != ahash and not changed:
        hash_warning = "file_hash_changed_but_schedule_counts_unchanged"
    passed = len(changed) == 0
    return {
        "mode": "schedule_live_db_compare",
        "timestamp": _now(),
        "project_key": before.get("project_key"),
        "passed": passed,
        "schedule_count_changes": changed,
        "file_hash_warning": hash_warning,
        "before_timestamp": before.get("timestamp"),
        "after_timestamp": after.get("timestamp"),
    }


def load_snapshot(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_snapshot(snapshot: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
