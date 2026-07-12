"""V125 — durable poison-file quarantine for NAS source-index scans.

One row per (root, path) that repeatedly failed per-file observation/upsert during a metadata walk. The
quarantine is a **root-level** blocker: it keeps a root unsafe and its generation non-authoritative until an
operator resolves it, and it must survive generation pruning (``generation_id`` is nullable; the originating
generation id is retained as sanitized audit in ``origin_generation_id``; there is NO cascading delete of an
unresolved record).

Additive, version-guarded, parity-guarded: ``CREATE TABLE IF NOT EXISTS`` + a partial UNIQUE index that
enforces at most one ACTIVE UNRESOLVED record per ``(source_root_key, rel_path)`` while allowing resolved
history to accumulate. No absolute host paths and no raw exception text are stored — ``rel_path`` is
root-relative and ``error_code`` is a structured classification.
"""

from __future__ import annotations

import sqlite3

# Structured failure classifications (never raw exception strings / host paths).
QUARANTINE_ERROR_CODES: frozenset[str] = frozenset(
    {"stat_failed", "metadata_upsert_failed", "path_unreadable", "path_changed_during_observation"}
)

# resolution_state values.
RESOLUTION_UNRESOLVED = "unresolved"
RESOLUTION_RESOLVED = "resolved"
RESOLUTION_CONFIRMED_ABSENT = "confirmed_absent"

# status values (lifecycle of the record itself).
STATUS_QUARANTINED = "quarantined"
STATUS_RESOLVED = "resolved"

# The no-forward-progress error code a generation carries when it ends holding unresolved quarantine.
QUARANTINE_UNRESOLVED_ERROR_CODE = "quarantine_unresolved"


# Ordered, additive, parity-guarded DDL executed by the V125 migration block (mirrors the
# ``V122_SOURCE_INDEX_SCAN_GENERATIONS_STATEMENTS`` pattern). Every statement is ``IF NOT EXISTS`` so an
# unconditional re-run on an already-migrated DB is a no-op.
V125_SOURCE_INDEX_SCAN_QUARANTINE_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS source_index_scan_quarantine (
        quarantine_id                  TEXT PRIMARY KEY,
        source_root_key                TEXT NOT NULL,
        generation_id                  TEXT,
        origin_generation_id           TEXT,
        source_id                      TEXT,
        rel_path                       TEXT NOT NULL,
        failure_stage                  TEXT NOT NULL,
        error_code                     TEXT NOT NULL,
        attempt_count                  INTEGER NOT NULL DEFAULT 0,
        first_seen_at                  TEXT NOT NULL,
        last_seen_at                   TEXT NOT NULL,
        last_attempt_at                TEXT,
        status                         TEXT NOT NULL DEFAULT 'quarantined',
        resolution_state               TEXT NOT NULL DEFAULT 'unresolved',
        resolved_at                    TEXT,
        last_successful_observation_at TEXT
    )
    """,
    # At most one ACTIVE UNRESOLVED quarantine per (root, path); resolved rows are exempt so history can
    # accumulate. Partial unique index → deterministic upsert target for the active record.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_source_index_scan_quarantine_active
    ON source_index_scan_quarantine (source_root_key, rel_path)
    WHERE resolution_state = 'unresolved'
    """,
    # Root-level lookups (trust / status counts) hit (root, resolution_state).
    """
    CREATE INDEX IF NOT EXISTS idx_source_index_scan_quarantine_root_state
    ON source_index_scan_quarantine (source_root_key, resolution_state)
    """,
]


def create_source_index_scan_quarantine_tables(conn: sqlite3.Connection) -> None:
    """Idempotent DDL for the quarantine table + its indexes (convenience wrapper over the statement list).

    Safe on a fresh DB and on an upgrade; re-running is a no-op (parity-guarded via ``IF NOT EXISTS``)."""
    for stmt in V125_SOURCE_INDEX_SCAN_QUARANTINE_STATEMENTS:
        conn.execute(stmt)
