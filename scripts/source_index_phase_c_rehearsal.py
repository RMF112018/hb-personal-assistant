#!/usr/bin/env python3
"""PC-WI-06 — authorized production-shaped source-index rehearsal (PCR-006 / PC-AC-048).

Generates a **synthetic** source-index fixture under a temporary rehearsal root using the Stage-1
configurable generator (``tests.support.source_index_migration_fixture.build_fixture``), then runs the
full pipeline — migrate (origin → head) → validate → backup → independent restore → restored validation
→ bounded compatibility read — emitting timing / size / WAL / migration / backup / restore / compat raw
evidence as JSON.

Synthetic only: no production or NAS database is touched (PCR-001/008 rehearsal-root isolation). At
``--rows 400000`` the two seeded roots produce ~800k ``source_intelligence_sources`` rows (≥ the
PC-AC-048 800k+ requirement).

Usage:
    PYTHONPATH=src:subrepos/construction-financial-review/src \\
      python scripts/source_index_phase_c_rehearsal.py --rows 400000 --origin 124 --out evidence.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

MINIMUM_SOURCE_ROWS = 800_000


def _size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _now() -> float:
    return time.monotonic()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC-WI-06 production-shaped source-index rehearsal")
    parser.add_argument("--rows", type=int, default=400000, help="row_count per root (2 roots ~= 2x source rows)")
    parser.add_argument("--origin", type=int, default=124, help="fixture origin version")
    parser.add_argument("--root", default=None, help="rehearsal root (default: a fresh temp dir)")
    parser.add_argument("--out", required=True, help="evidence JSON output path")
    args = parser.parse_args(argv)

    # Make the harness runnable standalone: ensure the repo root (for tests.support), src, and the
    # financial-review subrepo are importable regardless of the caller's PYTHONPATH.
    repo_root = Path(__file__).resolve().parents[1]
    for entry in (str(repo_root), str(repo_root / "src"), str(repo_root / "subrepos/construction-financial-review/src")):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.source_index_migration_assurance import collect_inventory
    from hb_assistant.store.sqlite_backup import (
        backup_database,
        restore_backup,
        validate_restored,
        verify_backup,
    )
    from tests.support.source_index_migration_fixture import HEAD_VERSION, build_fixture

    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="pc-wi-06-rehearsal-"))
    root.mkdir(parents=True, exist_ok=True)
    ev: dict[str, object] = {
        "work_item": "PC-WI-06",
        "acceptance_criterion": "PC-AC-048",
        "rows_per_root": args.rows,
        "origin": args.origin,
        "head": HEAD_VERSION,
        # Evidence is safe to commit: never emit the host-specific absolute rehearsal path.
        "rehearsal_root": "<redacted-disposable-root>",
        "synthetic": True,
        "production_or_nas_touched": False,
        "minimum_source_rows": MINIMUM_SOURCE_ROWS,
        "python_version": sys.version.split()[0],
        "sqlite_version": sqlite3.sqlite_version,
    }

    # 1) generate the synthetic fixture (Stage-1 generator), timed
    t0 = _now()
    fx = build_fixture(root, args.origin, row_count=args.rows, filename="rehearsal.sqlite")
    ev["generate_seconds"] = round(_now() - t0, 3)
    db = fx.db_path

    conn = sqlite3.connect(str(db))
    try:
        counts: dict[str, int | None] = {}
        for table in (
            "source_intelligence_sources",
            "source_intelligence_metadata",
            "source_intelligence_fts",
            "source_intelligence_text",
            "source_intelligence_events",
            "schema_migrations",
        ):
            try:
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                counts[table] = None
        origin_version = int(conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
    finally:
        conn.close()
    ev["origin_row_counts"] = counts
    ev["source_rows"] = counts.get("source_intelligence_sources")
    ev["scale_requirement_met"] = bool(
        isinstance(ev["source_rows"], int) and ev["source_rows"] >= MINIMUM_SOURCE_ROWS
    )
    ev["total_source_index_rows"] = sum(v for v in counts.values() if isinstance(v, int))
    ev["origin_version"] = origin_version
    ev["origin_db_size_bytes"] = _size(db)

    # 2) migrate origin -> head, timed; measure the WAL before checkpointing
    conn = sqlite3.connect(str(db))
    try:
        t0 = _now()
        migrated = int(SQLiteMigrator(db_path=str(db)).apply(conn=conn))
        ev["migrate_seconds"] = round(_now() - t0, 3)
    finally:
        conn.close()
    ev["migrated_version"] = migrated
    ev["wal_size_bytes_after_migrate"] = _size(db.with_name(db.name + "-wal"))
    # settle the WAL so the read-only inventory engine can inspect the migrated DB
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    ev["migrated_db_size_bytes"] = _size(db)

    inv = collect_inventory(db)
    ev["integrity"] = {
        "quick_check": inv.integrity.quick_check,
        "integrity_check": inv.integrity.integrity_check,
        "foreign_key_violations": inv.integrity.foreign_key_violations,
    }
    conn = sqlite3.connect(str(db))
    try:
        ledger = [int(r[0]) for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        conn.close()
    ev["ledger_complete_1_to_head"] = ledger == list(range(1, HEAD_VERSION + 1))

    # 3) backup, timed + sized
    dest = root / "backups"
    dest.mkdir(exist_ok=True)
    t0 = _now()
    result = backup_database(db, dest, rehearsal_root=root)
    ev["backup_seconds"] = round(_now() - t0, 3)
    ev["backup_size_bytes"] = _size(result.backup_path)
    ev["backup_status"] = result.receipt.status
    ev["backup_sha256"] = result.receipt.backup_sha256
    ev["backup_logical_hash"] = result.receipt.backup_logical_hash
    ev["source_logical_hash"] = result.receipt.source_logical_hash
    ev["backup_schema_version"] = result.receipt.schema_version
    backup_ok, backup_reason = verify_backup(result.backup_path, result.receipt)
    ev["backup_verify"] = {"ok": backup_ok, "reason": backup_reason}

    # 4) independent restore, timed + validated
    restore_dir = root / "restored"
    restore_dir.mkdir(exist_ok=True)
    t0 = _now()
    restored = restore_backup(result.backup_path, restore_dir / "restored.sqlite", rehearsal_root=root)
    ev["restore_seconds"] = round(_now() - t0, 3)
    restore_ok, restore_reason = validate_restored(restored, result.receipt.source_logical_hash)
    ev["restore_validation"] = {"ok": restore_ok, "reason": restore_reason}
    ev["restored_db_size_bytes"] = _size(restored)

    # 5) bounded compatibility read (current executable repository DAO against the migrated head), timed
    t0 = _now()
    note_counts = dict(SourceIndexRepository(db).generated_note_counts())
    ev["compat_seconds"] = round(_now() - t0, 3)
    ev["compat_generated_note_counts"] = note_counts

    ev["rehearsal_ok"] = bool(
        migrated == HEAD_VERSION
        and ev["scale_requirement_met"]
        and ev["ledger_complete_1_to_head"]
        and inv.integrity.integrity_check == "ok"
        and inv.integrity.quick_check == "ok"
        and backup_ok
        and restore_ok
    )

    Path(args.out).write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        k: ev[k]
        for k in (
            "source_rows",
            "scale_requirement_met",
            "total_source_index_rows",
            "generate_seconds",
            "migrate_seconds",
            "backup_seconds",
            "restore_seconds",
            "migrated_db_size_bytes",
            "wal_size_bytes_after_migrate",
            "rehearsal_ok",
        )
    }
    json.dump(summary, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if ev["rehearsal_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
