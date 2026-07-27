"""Independent expected-inventory oracle for Phase C source-index migration fixtures (PCR-002).

This module is the *independent* authority for "what a source-index database looks like at legacy
origin version N". It is hand-authored from a reading of the migration source
(``src/hb_assistant/store/migrator.py`` V119-V129 blocks and the ``*_tables.py`` DDL modules) and
frozen here as data. It shares **no code path** with the fixture builder
(``source_index_migration_fixture.py``): the builder mutates a database with SQL to *produce* an
origin; this oracle introspects a database read-only to *judge* whether it matches the expected
origin. A fixture is valid only when it passes this oracle before it is used for any migration proof.

The oracle checks the *discriminating* source-index objects (the V122-V129 deltas) plus a base-object
presence sanity set. V123 IS a real object discriminator: a faithful pre-V123 fixture carries the
historical narrow unique index ``idx_si_sources_relpath (source_kind, rel_path)`` (which a real
deployed pre-V123 database had, and which is why it blocked cross-root duplicate paths), and V123
drops it. The oracle therefore asserts the narrow index is present **iff origin < 123**, and asserts
the **exact** canonical SQL of both the narrow and the root-scoped (V93) indexes.

Read-only guarantee: every function here issues only ``SELECT`` / ``PRAGMA table_info`` statements.
It never writes, and it never imports the builder.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

# --- Supported origins -------------------------------------------------------------------------

SUPPORTED_ORIGINS: tuple[int, ...] = (121, 124, 125, 126, 127, 128, 129)
HEAD_VERSION: int = 129

# --- Delta objects, keyed by the migration version that introduces them ------------------------
# Derived from migrator.py:9148-9297 and the *_tables.py DDL. An object introduced at version V is
# expected PRESENT when origin >= V and ABSENT when origin < V.

DELTA_TABLES: dict[int, tuple[str, ...]] = {
    122: ("source_index_scan_generations",),
    125: ("source_index_scan_quarantine",),
    128: ("source_index_entities", "source_index_locators", "source_index_move_signals"),
}

DELTA_INDEXES: dict[int, tuple[str, ...]] = {
    122: (
        "idx_source_index_scan_generations_active",
        "idx_source_index_scan_generations_root",
        "idx_source_index_scan_generations_status",
    ),
    124: ("idx_si_metadata_fts_rowid",),
    125: (
        "idx_source_index_scan_quarantine_active",
        "idx_source_index_scan_quarantine_root_state",
    ),
    126: ("idx_si_sources_renamed_from",),
    128: (
        "idx_locators_current_per_entity",
        "idx_locators_active_path",
        "idx_locators_source_id",
        "idx_si_scan_quarantine_entity",
        "idx_si_events_entity",
    ),
    129: ("idx_locators_reconcile",),
}

# (table, column) added at each version.
DELTA_COLUMNS: dict[int, tuple[tuple[str, str], ...]] = {
    122: (
        ("source_intelligence_sources", "last_seen_generation"),
        ("source_intelligence_sources", "last_seen_at"),
        ("source_intelligence_sources", "last_indexed_fingerprint"),
        ("source_intelligence_metadata", "extraction_disposition"),
        ("source_intelligence_metadata", "content_indexed_at"),
        ("source_index_bootstrap_runs", "generation_id"),
    ),
    126: (("source_intelligence_sources", "renamed_from_source_id"),),
    127: (
        ("source_intelligence_events", "dest_rel_path"),
        ("source_intelligence_events", "next_attempt_at"),
    ),
    128: (
        ("source_index_entities", "source_entity_id"),
        ("source_index_locators", "source_entity_id"),
        ("source_index_locators", "source_id"),
        ("source_intelligence_sources", "source_entity_id"),
        ("source_intelligence_metadata", "source_entity_id"),
        ("source_intelligence_text", "source_entity_id"),
        ("source_intelligence_chunks", "source_entity_id"),
        ("source_intelligence_generated_notes", "source_entity_id"),
        ("source_intelligence_summaries", "source_entity_id"),
        ("source_intelligence_relationships", "src_source_entity_id"),
        ("source_intelligence_events", "source_entity_id"),
        ("source_index_scan_quarantine", "source_entity_id"),
    ),
    129: (
        ("source_index_locators", "last_seen_generation"),
        ("source_index_locators", "last_seen_at"),
        ("source_index_locators", "last_indexed_fingerprint"),
        ("source_index_locators", "policy_validation_state"),
        ("source_index_move_signals", "disposition"),
        ("source_index_move_signals", "disposition_at"),
        ("source_index_move_signals", "disposition_reason"),
        ("source_index_move_signals", "resulting_entity_id"),
        ("source_index_move_signals", "resulting_locator_id"),
    ),
}

# The V127 events rebuild widens the event_type CHECK to accept 'moved'. Observable read-only by
# inspecting the events table's CREATE sql in sqlite_master.
MOVED_ACCEPTED_AT: int = 127

# Relpath uniqueness indexes (S1-AUD-006). Two distinct objects:
#  * idx_si_sources_root_relpath — root-scoped, introduced by the **V93** base DDL, present at ALL
#    supported origins (NOT introduced by V123, contrary to a common misreading of the version map).
#  * idx_si_sources_relpath — the historical NARROW unique index (source_kind, rel_path) that OMITS
#    source_root_key. The current migrator never creates it (grep: only DROP statements at V99/V123),
#    but a real pre-V123 deployed database carried it (the base DDL created it before the fix), which
#    is exactly why it blocked multi-root duplicate rel_paths. A credible pre-V123 fixture therefore
#    carries the narrow index; V123 drops it. Expected PRESENT iff origin < NARROW_INDEX_DROPPED_AT.
NARROW_INDEX_DROPPED_AT: int = 123
# Exact canonical (whitespace-normalized) index SQL, asserted so a name match cannot hide a wrong
# definition (the auditor's required remediation for S1-AUD-006).
EXPECTED_ROOT_RELPATH_SQL: str = (
    "CREATE UNIQUE INDEX idx_si_sources_root_relpath "
    "ON source_intelligence_sources(source_kind, source_root_key, rel_path) WHERE rel_path IS NOT NULL"
)
EXPECTED_NARROW_RELPATH_SQL: str = (
    "CREATE UNIQUE INDEX idx_si_sources_relpath "
    "ON source_intelligence_sources(source_kind, rel_path) WHERE rel_path IS NOT NULL"
)

# Base source-index objects expected PRESENT at every supported origin (>= V121). A presence sanity
# set, not exhaustive — enough to assert the fixture is a real source-index DB, not an empty shell.
BASE_TABLES: tuple[str, ...] = (
    "schema_migrations",
    "source_intelligence_sources",
    "source_intelligence_metadata",
    "source_intelligence_text",
    "source_intelligence_chunks",
    "source_intelligence_relationships",
    "source_intelligence_generated_notes",
    "source_intelligence_events",
    "source_intelligence_state",
    "source_intelligence_summaries",
    "source_structure_roots",
    "source_structure_folders",
    "source_structure_overrides",
    "source_index_bootstrap_state",
    "source_index_reconciliation_runs",
    "source_index_bootstrap_runs",
)

# Present at every origin regardless of version.
BASE_INDEXES: tuple[str, ...] = (
    "idx_si_sources_domain",
    "idx_si_events_status",
    "idx_si_events_source",
)

# FTS5 virtual tables (present only when the runtime SQLite has FTS5, which it does here).
FTS_TABLES: tuple[str, ...] = ("source_intelligence_fts", "obsidian_note_fts")


# --- Read-only introspection helpers -----------------------------------------------------------


def _object_exists(conn: sqlite3.Connection, obj_type: str, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?", (obj_type, name)
    ).fetchone()
    return row is not None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    # FTS5 registers as type 'table'; virtual tables included.
    return _object_exists(conn, "table", name)


def _index_exists(conn: sqlite3.Connection, name: str) -> bool:
    return _object_exists(conn, "index", name)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def _ledger_max_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _events_create_sql(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'source_intelligence_events'"
    ).fetchone()
    return (row[0] or "") if row else ""


def _normalize_sql(sql: str | None) -> str:
    return " ".join((sql or "").split())


def _index_sql(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)
    ).fetchone()
    return _normalize_sql(row[0] if row else None)


# --- Validation --------------------------------------------------------------------------------


@dataclass
class InventoryVerdict:
    origin: int
    ok: bool
    violations: list[str] = field(default_factory=list)


def validate_origin(conn: sqlite3.Connection, origin: int) -> InventoryVerdict:
    """Judge, read-only, whether ``conn`` matches the expected inventory for the given origin.

    Returns a verdict with a list of human-readable violations (empty ⇒ ok).
    """
    if origin not in SUPPORTED_ORIGINS:
        return InventoryVerdict(origin, False, [f"unsupported origin {origin}"])

    violations: list[str] = []

    # 1. Ledger head.
    max_ver = _ledger_max_version(conn)
    if max_ver != origin:
        violations.append(f"schema_migrations MAX(version)={max_ver}, expected {origin}")

    # 2. Base objects present.
    for tbl in BASE_TABLES:
        if not _table_exists(conn, tbl):
            violations.append(f"base table missing: {tbl}")
    for idx in BASE_INDEXES:
        if not _index_exists(conn, idx):
            violations.append(f"base index missing: {idx}")
    for fts in FTS_TABLES:
        if not _table_exists(conn, fts):
            violations.append(f"FTS table missing: {fts}")

    # 3. Delta tables: present iff origin >= intro version.
    for intro, tables in DELTA_TABLES.items():
        for tbl in tables:
            present = _table_exists(conn, tbl)
            expected = origin >= intro
            if present != expected:
                violations.append(
                    f"table {tbl}: present={present}, expected_present={expected} (intro V{intro})"
                )

    # 4. Delta indexes.
    for intro, indexes in DELTA_INDEXES.items():
        for idx in indexes:
            present = _index_exists(conn, idx)
            expected = origin >= intro
            if present != expected:
                violations.append(
                    f"index {idx}: present={present}, expected_present={expected} (intro V{intro})"
                )

    # 5. Delta columns. V128 re-keys the seven-table source graph, so the legacy V122 observation
    # columns on ``source_intelligence_sources`` exist only through V127; V129 re-homes them to the
    # current locator.
    for intro, columns in DELTA_COLUMNS.items():
        for table, column in columns:
            present = _column_exists(conn, table, column)
            expected = origin >= intro
            if intro == 122 and table == "source_intelligence_sources":
                expected = 122 <= origin < 128
            if present != expected:
                violations.append(
                    f"column {table}.{column}: present={present}, "
                    f"expected_present={expected} (intro V{intro})"
                )

    legacy_source_id_columns = (
        ("source_intelligence_sources", "source_id"),
        ("source_intelligence_metadata", "source_id"),
        ("source_intelligence_text", "source_id"),
        ("source_intelligence_chunks", "source_id"),
        ("source_intelligence_generated_notes", "source_id"),
        ("source_intelligence_summaries", "source_id"),
        ("source_intelligence_relationships", "src_source_id"),
    )
    for table, column in legacy_source_id_columns:
        present = _column_exists(conn, table, column)
        expected = origin < 128
        if present != expected:
            violations.append(
                f"legacy key {table}.{column}: present={present}, expected_present={expected}"
            )

    last_seen_index_present = _index_exists(conn, "idx_si_sources_last_seen_gen")
    expected_last_seen_index = 122 <= origin < 128
    if last_seen_index_present != expected_last_seen_index:
        violations.append(
            "idx_si_sources_last_seen_gen: "
            f"present={last_seen_index_present}, expected_present={expected_last_seen_index}"
        )

    # 6. events CHECK accepts 'moved' iff origin >= 127 (read-only sqlite_master inspection).
    events_sql = _events_create_sql(conn)
    moved_accepted = "'moved'" in events_sql
    expected_moved = origin >= MOVED_ACCEPTED_AT
    if moved_accepted != expected_moved:
        violations.append(
            f"events CHECK moved-accepted={moved_accepted}, expected={expected_moved} "
            f"(intro V{MOVED_ACCEPTED_AT})"
        )

    # 7. Root-scoped relpath index: present through V127 with the exact V93 definition. V128 moves
    # path uniqueness to ``idx_locators_active_path`` and deliberately removes this parent index.
    root_sql = _index_sql(conn, "idx_si_sources_root_relpath")
    expected_root_sql = (
        _normalize_sql(EXPECTED_ROOT_RELPATH_SQL) if origin < 128 else ""
    )
    if root_sql != expected_root_sql:
        violations.append(
            f"idx_si_sources_root_relpath SQL mismatch:\n    got:      {root_sql or '<absent>'}\n"
            f"    expected: {expected_root_sql or '<absent>'}"
        )

    # 8. Narrow relpath index: present iff origin < 123 (pre-V123 deployed shape), with EXACT SQL.
    narrow_present = _index_exists(conn, "idx_si_sources_relpath")
    expected_narrow = origin < NARROW_INDEX_DROPPED_AT
    if narrow_present != expected_narrow:
        violations.append(
            f"narrow idx_si_sources_relpath present={narrow_present}, "
            f"expected_present={expected_narrow} (dropped by V{NARROW_INDEX_DROPPED_AT})"
        )
    elif narrow_present:
        narrow_sql = _index_sql(conn, "idx_si_sources_relpath")
        if narrow_sql != _normalize_sql(EXPECTED_NARROW_RELPATH_SQL):
            violations.append(
                f"narrow idx_si_sources_relpath SQL mismatch:\n    got:      {narrow_sql}\n"
                f"    expected: {_normalize_sql(EXPECTED_NARROW_RELPATH_SQL)}"
            )

    return InventoryVerdict(origin, not violations, violations)


def assert_origin(conn: sqlite3.Connection, origin: int) -> None:
    """Raise ``AssertionError`` with all violations if ``conn`` does not match the expected origin."""
    verdict = validate_origin(conn, origin)
    if not verdict.ok:
        detail = "\n  - ".join(verdict.violations)
        raise AssertionError(
            f"fixture does not match expected inventory for origin V{origin}:\n  - {detail}"
        )
