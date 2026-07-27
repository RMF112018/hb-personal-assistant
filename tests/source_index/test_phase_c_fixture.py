"""Phase C Stage 1 (C2) — fixture framework + independent-oracle tests.

Covers: determinism, per-origin oracle match (PC-AC-002..011, PC-AC-051), the pre-V123 narrow-index
model + exact-SQL assertions and corruption negatives (S1-AUD-006), the fresh fixture (S1-AUD-010),
the configured-application-DB refusal (S1-AUD-011, PCR-001/PCR-008), reconcile_pending generation
coverage (S1-AUD-012), WAL mode (PC-AC-012), synthetic-only data (PC-AC-045), and rehearsal-root path
safety (PCR-001/PCR-008, PC-AC-054).
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.store.source_index_migration_assurance import collect_inventory
from tests.support.source_index_expected_inventory import (
    EXPECTED_NARROW_RELPATH_SQL,
    EXPECTED_ROOT_RELPATH_SQL,
    HEAD_VERSION,
    SUPPORTED_ORIGINS,
    assert_origin,
    validate_origin,
)
from tests.support.source_index_migration_fixture import FRESH, build_fixture


def _ro(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _norm(sql: str) -> str:
    return " ".join(sql.split())


@pytest.mark.parametrize("origin", SUPPORTED_ORIGINS)
def test_fixture_matches_independent_oracle(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    assert res.origin == origin
    conn = _ro(res.db_path)
    try:
        assert_origin(conn, origin)  # raises with all violations if mismatched
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == origin
    finally:
        conn.close()


@pytest.mark.parametrize("origin", SUPPORTED_ORIGINS)
def test_fixture_is_deterministic(tmp_path, origin):
    a = build_fixture(tmp_path, origin, row_count=6, filename=f"a_v{origin}.sqlite")
    b = build_fixture(tmp_path, origin, row_count=6, filename=f"b_v{origin}.sqlite")
    assert a.logical_inventory_hash == b.logical_inventory_hash


# --- Narrow / root-scoped relpath index (S1-AUD-006) ------------------------------------------


def test_v121_carries_pre_v123_narrow_index_with_exact_sql(tmp_path):
    res = build_fixture(tmp_path, 121, row_count=6)
    conn = _ro(res.db_path)
    try:
        narrow = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_si_sources_relpath'"
        ).fetchone()
        root = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_si_sources_root_relpath'"
        ).fetchone()
    finally:
        conn.close()
    assert narrow is not None, "pre-V123 fixture must carry the historical narrow index"
    assert _norm(narrow[0]) == _norm(EXPECTED_NARROW_RELPATH_SQL)
    assert root is not None and _norm(root[0]) == _norm(EXPECTED_ROOT_RELPATH_SQL)


@pytest.mark.parametrize("origin", [124, 125, 126, 127])
def test_post_v123_origins_have_no_narrow_index(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    conn = _ro(res.db_path)
    try:
        narrow = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_si_sources_relpath'"
        ).fetchone()
        root = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_si_sources_root_relpath'"
        ).fetchone()
    finally:
        conn.close()
    assert narrow is None, "V123 drops the narrow index; it must be absent at V124+"
    assert root is not None and _norm(root[0]) == _norm(EXPECTED_ROOT_RELPATH_SQL)


def test_oracle_rejects_narrow_index_injected_into_post_v123_fixture(tmp_path):
    res = build_fixture(tmp_path, 124, row_count=4)
    conn = sqlite3.connect(str(res.db_path))
    try:
        # A duplicate-free is not guaranteed at V124 (cross-root dupes exist), so build the narrow
        # index only over rows that are unique — but the point is schema presence, so drop the
        # duplicate first is unnecessary: create a NON-unique stand-in is not the historical shape.
        # Instead assert the oracle rejects the *presence* of the narrow index name at V124.
        conn.execute(
            "CREATE INDEX idx_si_sources_relpath "
            "ON source_intelligence_sources(source_kind, rel_path)"
        )
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(str(res.db_path))
    try:
        verdict = validate_origin(conn, 124)
        assert not verdict.ok
        assert any("idx_si_sources_relpath" in v for v in verdict.violations)
    finally:
        conn.close()


def test_oracle_rejects_v121_with_narrow_index_removed(tmp_path):
    res = build_fixture(tmp_path, 121, row_count=4)
    conn = sqlite3.connect(str(res.db_path))
    try:
        conn.execute("DROP INDEX idx_si_sources_relpath")
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(str(res.db_path))
    try:
        verdict = validate_origin(conn, 121)
        assert not verdict.ok
        assert any("idx_si_sources_relpath" in v for v in verdict.violations)
    finally:
        conn.close()


# --- Invariant coverage -----------------------------------------------------------------------


def test_head_fixture_carries_all_invariants(tmp_path):
    res = build_fixture(tmp_path, HEAD_VERSION, row_count=6)
    inv = collect_inventory(res.db_path)
    assert inv.duplicate_relpath_across_roots > 0  # multi-root duplicate paths (PC-AC-005)
    assert inv.fts_present_count > 0 and inv.fts_missing_count > 0  # FTS present + missing (PC-AC-007)
    assert set(inv.generation_counts_by_status) == {
        "running",
        "partial",
        "reconcile_pending",
        "failed",
        "abandoned",
        "completed",
    }  # ALL six generation states incl reconcile_pending (PC-AC-006 / S1-AUD-012)
    assert inv.quarantine_unresolved_count == 1  # quarantine (PC-AC-009)
    assert inv.lineage_count == 1  # rename lineage (PC-AC-010)
    assert inv.events_moved_supported and inv.events_by_type.get("moved", 0) == 1  # V127 (PC-AC-011)
    assert inv.row_counts["source_intelligence_generated_notes"] > 0  # cards (PC-AC-008)
    assert inv.row_counts["source_index_bootstrap_runs"] == 2  # pass links (PC-AC-008)
    assert inv.row_counts["source_index_entities"] == inv.row_counts["source_intelligence_sources"]
    assert inv.row_counts["source_index_locators"] == inv.row_counts["source_intelligence_sources"]
    assert inv.row_counts["source_index_move_signals"] == 1
    assert inv.fts_parity.matched > 0 and inv.fts_parity.dangling == 0 and inv.fts_parity.orphan == 0


def test_v121_has_no_cross_root_duplicates(tmp_path):
    """Pre-V123 the narrow unique index forbids cross-root duplicate rel_paths — faithful modeling."""
    res = build_fixture(tmp_path, 121, row_count=6)
    inv = collect_inventory(res.db_path)
    assert inv.duplicate_relpath_across_roots == 0
    assert inv.root_count == 2


@pytest.mark.parametrize("origin", SUPPORTED_ORIGINS)
def test_fixture_runs_in_wal_mode(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=4)
    conn = _ro(res.db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


# --- Fresh fixture (S1-AUD-010) ---------------------------------------------------------------


def test_fresh_fixture_is_empty_head_schema(tmp_path):
    res = build_fixture(tmp_path, FRESH)
    assert res.origin == FRESH
    inv = collect_inventory(res.db_path)
    assert inv.schema_head == HEAD_VERSION
    assert inv.events_moved_supported  # head schema
    assert inv.row_counts.get("source_intelligence_sources", 0) == 0  # genuinely empty
    conn = _ro(res.db_path)
    try:
        # No narrow index at head; schema matches the execution-time oracle.
        assert (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_si_sources_relpath'"
            ).fetchone()
            is None
        )
        assert validate_origin(conn, HEAD_VERSION).ok
    finally:
        conn.close()


# --- Synthetic-only data (PC-AC-045) ----------------------------------------------------------


def test_no_absolute_host_paths_in_data(tmp_path):
    res = build_fixture(tmp_path, HEAD_VERSION, row_count=6)
    conn = _ro(res.db_path)
    try:
        rel_paths = [
            r[0]
            for r in conn.execute(
                "SELECT rel_path FROM source_intelligence_sources WHERE rel_path IS NOT NULL"
            ).fetchall()
        ]
        roots = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT source_root_key FROM source_intelligence_sources"
            ).fetchall()
        ]
    finally:
        conn.close()
    assert rel_paths and all(not p.startswith("/") for p in rel_paths)
    assert all(not (r or "").startswith("/") for r in roots)
    assert all("/Users/" not in p for p in rel_paths)


# --- Path safety (PCR-001 / PCR-008) ----------------------------------------------------------


def test_rejects_destination_outside_rehearsal_root(tmp_path):
    with pytest.raises(ValueError, match="bare name"):
        build_fixture(tmp_path, 127, filename="../escape.sqlite")


def test_rejects_symlinked_rehearsal_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        build_fixture(link, 127)


def test_rejects_missing_rehearsal_root(tmp_path):
    with pytest.raises(ValueError, match="existing directory"):
        build_fixture(tmp_path / "does-not-exist", 127)


def test_refuses_to_overwrite_unmarked_database(tmp_path):
    victim = tmp_path / "source_index_v127.sqlite"
    victim.write_bytes(b"not a fixture")
    with pytest.raises(ValueError, match="non-fixture database"):
        build_fixture(tmp_path, 127)


def test_refuses_configured_application_database(tmp_path, monkeypatch):
    """The builder must refuse to write over the resolved application DB path (S1-AUD-011)."""
    target = (tmp_path / "source_index_v127.sqlite").resolve()
    monkeypatch.setattr(
        "hb_assistant.config.path_policy.PathPolicy.get_db_path",
        lambda self: str(target),
    )
    with pytest.raises(ValueError, match="configured application database"):
        build_fixture(tmp_path, 127)


def test_rejects_unsupported_origin(tmp_path):
    with pytest.raises(ValueError, match="unsupported origin"):
        build_fixture(tmp_path, 123)
