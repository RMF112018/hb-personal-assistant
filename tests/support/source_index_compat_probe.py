"""Compatibility probe executed **under a prior executable** (PC-WI-04 / PCR-007).

This script is run as a subprocess with ``PYTHONPATH`` pointing at a ``git worktree`` of a pinned prior
executable SHA, so ``import hb_assistant...`` resolves to that **prior** code, not the current tree. It
performs bounded reads against a target database using the prior executable's own layers and reports
what the prior executable observed — it does **not** start the full application, migrate, or write
application data. Two kinds of read are distinguished honestly in the JSON:

- ``repo_generated_note_counts`` — a genuine **repository DAO** operation
  (``SourceIndexRepository.generated_note_counts()``), the read-only generation-table path;
- ``current_version_read`` — the prior migrator's ``current_version()`` over its own connection layer.

It also reports the prior executable's **known** ``source_intelligence_events`` event types and the
event types actually present in the target database, so the orchestrator can detect a newer database
carrying an event type (e.g. the V127 ``moved`` semantic) that the prior executable has no knowledge
of. Read failures are reported (``read_ok: false`` + ``error``) rather than raised, so the orchestrator
can classify them instead of mistaking a crash for a pass.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys


def _probe(db: str) -> dict[str, object]:
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
    from hb_assistant.store.source_intelligence_tables import EVENT_TYPE_VALUES

    known_event_types = sorted(EVENT_TYPE_VALUES)
    result: dict[str, object] = {
        "prior_latest_schema_version": int(LATEST_SCHEMA_VERSION),
        "target_db": db,
        "current_version_read": None,
        "repo_generated_note_counts": None,  # genuine repository DAO read
        "known_event_types": known_event_types,  # what the PRIOR executable understands
        "present_event_types": None,  # what the target DB actually contains
        "unknown_event_types": None,  # present in the DB but unknown to the prior executable
        "read_ok": False,
        "error": None,
    }
    try:
        # (1) prior migrator connection-layer read
        result["current_version_read"] = int(SQLiteMigrator(db_path=db).current_version())
        # (2) genuine prior repository DAO read (read-only generation-table path)
        result["repo_generated_note_counts"] = dict(SourceIndexRepository(db).generated_note_counts())
        # (3) event-type knowledge gap: what the prior executable can/cannot interpret
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            present = sorted(
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT event_type FROM source_intelligence_events"
                ).fetchall()
            )
        finally:
            conn.close()
        result["present_event_types"] = present
        result["unknown_event_types"] = sorted(set(present) - set(known_event_types))
        result["read_ok"] = True
    except Exception as exc:  # reported, never raised — the orchestrator classifies it
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC-WI-04 prior-executable compatibility probe")
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
