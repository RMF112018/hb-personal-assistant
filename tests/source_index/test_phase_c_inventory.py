"""Phase C Stage 1 (C3) — read-only inventory/parity engine tests.

Covers: fail-closed read-only behavior (S1-AUD-008), deterministic logical hashing, redaction,
integrity checks, structural inventory + mutation detection (S1-AUD-007), and source-text / FTS
linkage corruption detection (S1-AUD-009). (PC-AC-027..029, PC-AC-047.)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3

import pytest

from hb_assistant.store.source_index_migration_assurance import (
    collect_inventory,
    to_redacted_dict,
)
from tests.support.source_index_migration_fixture import build_fixture


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _writable_copy(src, dst_dir, name="mut.sqlite"):
    dst = dst_dir / name
    shutil.copy(src, dst)
    return dst


def _logical_hash(path) -> str:
    return collect_inventory(path).logical_inventory_hash


# --- Read-only / fail-closed (S1-AUD-008) -----------------------------------------------------


def test_inventory_is_read_only(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    before = _sha(res.db_path)
    report = collect_inventory(res.db_path)
    after = _sha(res.db_path)
    assert before == after
    assert report.schema_head == 127


def test_inventory_creates_no_sidecar_files(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    # Remove any WAL/SHM the builder left, then inspect and prove none are created.
    for suf in ("-wal", "-shm"):
        p = res.db_path.with_name(res.db_path.name + suf)
        if p.exists():
            p.unlink()
    collect_inventory(res.db_path)
    for suf in ("-wal", "-shm", "-journal"):
        assert not res.db_path.with_name(res.db_path.name + suf).exists()


def test_inventory_fails_closed_on_missing_path(tmp_path):
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(FileNotFoundError):
        collect_inventory(missing)
    assert not missing.exists(), "inspection must not create the database"


def test_inventory_rejects_non_regular_file(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        collect_inventory(d)


def test_inventory_rejects_uncheckpointed_wal(tmp_path):
    """A non-empty -wal must be rejected so immutable read cannot ignore committed WAL state (S1-AUD-014)."""
    res = build_fixture(tmp_path, 127, row_count=6)
    db_before = _sha(res.db_path)
    wal = res.db_path.with_name(res.db_path.name + "-wal")
    wal.write_bytes(b"\x00" * 128)
    wal_before = _sha(wal)
    with pytest.raises(ValueError, match="uncheckpointed_wal_present"):
        collect_inventory(res.db_path)
    # Rejection must not mutate the DB or the WAL, and must create no new sidecar.
    assert _sha(res.db_path) == db_before
    assert _sha(wal) == wal_before
    assert not res.db_path.with_name(res.db_path.name + "-shm").exists()


# --- Logical hash -----------------------------------------------------------------------------


def test_logical_hash_is_deterministic_and_matches_builder(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    a = collect_inventory(res.db_path)
    b = collect_inventory(res.db_path)
    assert a.logical_inventory_hash == b.logical_inventory_hash == res.logical_inventory_hash


def test_logical_hash_differs_across_origins(tmp_path):
    h = {
        origin: build_fixture(tmp_path, origin, row_count=6).logical_inventory_hash
        for origin in (121, 124, 127)
    }
    assert len(set(h.values())) == 3


# --- Structural mutation detection (S1-AUD-007) -----------------------------------------------


def test_structural_signature_present(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    report = collect_inventory(res.db_path)
    sig = report.structural_signature
    assert "tables" in sig and "indexes" in sig
    src = sig["tables"]["source_intelligence_sources"]  # type: ignore[index]
    colnames = {c["name"] for c in src["columns"]}  # type: ignore[index]
    assert {"source_id", "source_root_key", "rel_path", "renamed_from_source_id"} <= colnames
    assert any(c["name"] == "source_id" and c["pk"] == 1 for c in src["columns"])  # type: ignore[index]


def test_added_column_changes_logical_hash(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute("ALTER TABLE source_intelligence_sources ADD COLUMN injected_col TEXT")
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_dropped_index_changes_logical_hash(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute("DROP INDEX idx_si_metadata_fts_rowid")
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_index_uniqueness_change_changes_logical_hash(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    # Replace a non-unique index with a unique one of the same name/columns → structural change.
    conn.execute("DROP INDEX idx_si_sources_active")
    conn.execute(
        "CREATE UNIQUE INDEX idx_si_sources_active "
        "ON source_intelligence_sources(active, deleted, source_id)"
    )
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


# --- Source-text / FTS corruption detection (S1-AUD-009) --------------------------------------


def test_deleted_fts_row_is_detected(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = collect_inventory(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute("DELETE FROM source_intelligence_fts WHERE rowid = (SELECT MIN(rowid) FROM source_intelligence_fts)")
    conn.commit()
    conn.close()
    after = collect_inventory(mut)
    assert after.fts_parity.dangling > base.fts_parity.dangling
    assert after.logical_inventory_hash != base.logical_inventory_hash


def test_stale_fts_rowid_is_detected(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = collect_inventory(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute(
        "UPDATE source_intelligence_metadata SET fts_rowid = 999999 "
        "WHERE fts_rowid = (SELECT MIN(fts_rowid) FROM source_intelligence_metadata WHERE fts_rowid IS NOT NULL)"
    )
    conn.commit()
    conn.close()
    after = collect_inventory(mut)
    assert after.fts_parity.dangling > base.fts_parity.dangling
    assert after.logical_inventory_hash != base.logical_inventory_hash


def test_changed_text_excerpt_is_detected(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute(
        "UPDATE source_intelligence_text SET text_excerpt = 'tampered' "
        "WHERE source_id = (SELECT source_id FROM source_intelligence_text LIMIT 1)"
    )
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_missing_source_text_is_detected(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute("DELETE FROM source_intelligence_text WHERE source_id = (SELECT source_id FROM source_intelligence_text LIMIT 1)")
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_same_rowid_fts_content_corruption_is_detected(tmp_path):
    """Corrupting an existing referenced FTS row's TEXT while keeping its rowid must change the hash.

    Row-ID linkage parity (matched/dangling/orphan) is unchanged by this, so it is caught only by the
    per-row FTS content digest (S1-AUD-015).
    """
    res = build_fixture(tmp_path, 127, row_count=6)
    before = collect_inventory(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute(
        "UPDATE source_intelligence_fts SET text_excerpt = 'tampered content' "
        "WHERE rowid = (SELECT MIN(rowid) FROM source_intelligence_fts)"
    )
    conn.commit()
    conn.close()
    after = collect_inventory(mut)
    # Linkage parity is unchanged (rowid preserved) — proving the digest, not parity, caught it.
    assert after.fts_parity == before.fts_parity
    assert after.logical_inventory_hash != before.logical_inventory_hash


def test_fts_path_or_aux_corruption_is_detected(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute(
        "UPDATE source_intelligence_fts SET aux = 'wrong-project' "
        "WHERE rowid = (SELECT MIN(rowid) FROM source_intelligence_fts)"
    )
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_obsidian_fts_content_corruption_is_detected(tmp_path):
    """Content coverage must include obsidian_note_fts, not only source_intelligence_fts (S1-AUD-015)."""
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute(
        "UPDATE obsidian_note_fts SET text_excerpt = 'tampered note' "
        "WHERE rowid = (SELECT MIN(rowid) FROM obsidian_note_fts)"
    )
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_omitted_structural_table_change_is_detected(tmp_path):
    """A schema change to a previously-omitted source-index table must change the hash (S1-AUD-016)."""
    res = build_fixture(tmp_path, 127, row_count=6)
    base = _logical_hash(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute("ALTER TABLE source_structure_folders ADD COLUMN injected_col TEXT")
    conn.commit()
    conn.close()
    assert _logical_hash(mut) != base


def test_orphan_fts_row_is_detected(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    base = collect_inventory(res.db_path)
    mut = _writable_copy(res.db_path, tmp_path)
    conn = sqlite3.connect(str(mut))
    conn.execute(
        "INSERT INTO source_intelligence_fts (text_excerpt, rel_path, aux) VALUES ('orphan', 'x/y.pdf', 'p')"
    )
    conn.commit()
    conn.close()
    after = collect_inventory(mut)
    assert after.fts_parity.orphan > base.fts_parity.orphan
    assert after.logical_inventory_hash != base.logical_inventory_hash


# --- Integrity + redaction --------------------------------------------------------------------


def test_integrity_checks_pass_on_fixture(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    report = collect_inventory(res.db_path)
    assert report.integrity.quick_check == "ok"
    assert report.integrity.integrity_check == "ok"
    assert report.integrity.foreign_key_violations == 0


def test_redacted_report_has_no_path_or_content_values(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    report = collect_inventory(res.db_path)
    blob = json.dumps(to_redacted_dict(report))
    assert "shared/dup.pdf" not in blob
    assert "docs/file_" not in blob
    assert "excerpt for" not in blob
    assert "/Users/" not in blob
    assert "logical_inventory_hash" in blob
    assert "structural_signature" in blob


def test_reports_multi_root_and_fts_parity(tmp_path):
    res = build_fixture(tmp_path, 127, row_count=6)
    report = collect_inventory(res.db_path)
    assert report.root_count == 2
    assert report.duplicate_relpath_across_roots > 0
    assert report.fts_present_count > 0
    assert report.fts_missing_count > 0
