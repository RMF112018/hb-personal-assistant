"""DB copy rehearsal against disposable copies only."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RehearsalResult:
    source_db_path: str
    copy_db_path: str
    copy_ok: bool
    schema_version_before: int
    schema_version_after: int
    foreign_key_check_rows: int
    integrity_check: str
    wrote_production: bool = False


def rehearse_copy_and_migrate(
    source: Path,
    copy: Path,
    *,
    migrate_fn,
) -> RehearsalResult:
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, copy)
    conn = sqlite3.connect(str(copy))
    try:
        before = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        # prefer schema_migrations max if present
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            if row and row[0] is not None:
                before = int(row[0])
        except sqlite3.Error:
            pass
        after = int(migrate_fn(copy))
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return RehearsalResult(
            source_db_path=str(source),
            copy_db_path=str(copy),
            copy_ok=True,
            schema_version_before=before,
            schema_version_after=after,
            foreign_key_check_rows=len(fk),
            integrity_check=str(integrity),
            wrote_production=False,
        )
    finally:
        conn.close()
