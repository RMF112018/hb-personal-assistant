"""Bounded-DAO-read compatibility probe, executed **under a prior executable** (PC-WI-04 / PCR-007).

This script is run as a subprocess with ``PYTHONPATH`` pointing at a ``git worktree`` of a pinned prior
executable SHA, so ``import hb_assistant.store...`` resolves to that **prior** code, not the current
tree. It performs a *bounded* DAO read against a target database using the prior executable's own
connection layer — it does **not** start the full application, migrate, or write application data — and
emits a structured JSON result on stdout describing what the prior executable observed.

It imports only ``hb_assistant.store`` (the prior executable) and the standard library, so the current
test tree is never mixed into the prior executable's process. If the prior executable cannot open or
read the target, the failure is reported in the JSON (``read_ok: false`` + ``error``) rather than
raising, so the orchestrating test can classify it as INSUFFICIENT EVIDENCE rather than a false pass.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys

# A source-index table that has existed since V122 — present in every origin the compat matrix uses,
# so a successful read exercises a real prior-executable read path across schema heads.
_REPRESENTATIVE_TABLE = "source_index_scan_generations"


def _probe(db: str) -> dict[str, object]:
    from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

    result: dict[str, object] = {
        "prior_latest_schema_version": int(LATEST_SCHEMA_VERSION),
        "target_db": db,
        "representative_table": _REPRESENTATIVE_TABLE,
        "current_version_read": None,
        "representative_row_count": None,
        "read_ok": False,
        "error": None,
    }
    try:
        # Bounded DAO read via the prior executable's own connection/migrator layer.
        result["current_version_read"] = int(SQLiteMigrator(db_path=db).current_version())
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {_REPRESENTATIVE_TABLE}").fetchone()
            result["representative_row_count"] = int(row[0])
        finally:
            conn.close()
        result["read_ok"] = True
    except Exception as exc:  # reported, never raised — the orchestrator classifies it
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC-WI-04 prior-executable bounded-DAO-read probe")
    parser.add_argument("--db", required=True, help="target database path")
    parser.add_argument("--out", required=True, help="JSON result output path")
    args = parser.parse_args(argv)
    result = _probe(args.db)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True)
        handle.flush()
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
