"""PC-WI-02 Stage-2 — backup & restore assurance.

Online backup via ``Connection.backup()`` over a read-only source URI (never a raw copy while WAL is
active), with a durable receipt + hash; independent restore to a new location; restored-database
integrity + logical-inventory validation; representative read-only ops on the restored database; and
an interrupted backup that cannot be mistaken for a valid one (PC-AC-030..035). All destinations live
under a caller rehearsal root; no production database or NAS path is touched.
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.store.source_index_migration_assurance import (
    collect_inventory,
    source_index_logical_hash,
)
from hb_assistant.store.sqlite_backup import (
    BackupError,
    backup_database,
    load_receipt,
    restore_backup,
    validate_restored,
    verify_backup,
)
from hb_assistant.store.startup_schema_policy import validate_startup_migration_backup_receipt
from tests.support.source_index_migration_fixture import HEAD_VERSION, build_fixture


def _fixture(tmp_path, name="src.sqlite", origin=HEAD_VERSION):
    root = tmp_path / "rehearsal"
    root.mkdir(exist_ok=True)
    return root, build_fixture(root, origin, row_count=6, filename=name)


def test_backup_is_consistent_and_hashed(tmp_path):  # PC-AC-030, PC-AC-031
    root, fx = _fixture(tmp_path)
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)

    assert result.backup_path.is_file()
    assert result.receipt.backup_sha256 and len(result.receipt.backup_sha256) == 64
    assert result.receipt.byte_size == result.backup_path.stat().st_size
    # consistent snapshot: backup's source-index logical state equals the source's
    assert result.receipt.source_logical_hash == source_index_logical_hash(fx.db_path)
    assert result.receipt.backup_logical_hash == result.receipt.source_logical_hash
    assert result.receipt.status == "complete"


def test_receipt_is_durable_and_matches_startup_convention(tmp_path):  # PC-AC-031
    root, fx = _fixture(tmp_path)
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)

    assert result.receipt_path.is_file()
    reloaded = load_receipt(result.receipt_path)
    assert reloaded.backup_sha256 == result.receipt.backup_sha256
    # the receipt satisfies the workspace startup-migration receipt contract (superset)
    payload = validate_startup_migration_backup_receipt(result.receipt_path)
    assert payload["schema_version"] == HEAD_VERSION
    assert payload["generated_utc"] and payload["backup_path"]


def test_restore_to_independent_location(tmp_path):  # PC-AC-032
    root, fx = _fixture(tmp_path)
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)

    restore_dir = root / "restored"
    restore_dir.mkdir()
    restored = restore_backup(result.backup_path, restore_dir / "restored.sqlite", rehearsal_root=root)

    assert restored.is_file()
    assert restored != result.backup_path and restored.parent != result.backup_path.parent


def test_restored_passes_integrity_and_logical_inventory(tmp_path):  # PC-AC-033
    root, fx = _fixture(tmp_path)
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)
    restore_dir = root / "restored"
    restore_dir.mkdir()
    restored = restore_backup(result.backup_path, restore_dir / "r.sqlite", rehearsal_root=root)

    ok, detail = validate_restored(restored, result.receipt.source_logical_hash)
    assert ok, detail
    inv = collect_inventory(restored)
    assert inv.integrity.integrity_check == "ok" and inv.integrity.quick_check == "ok"
    assert inv.integrity.foreign_key_violations == 0


def test_readonly_ops_on_restored(tmp_path):  # PC-AC-034
    root, fx = _fixture(tmp_path)
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)
    restore_dir = root / "restored"
    restore_dir.mkdir()
    restored = restore_backup(result.backup_path, restore_dir / "r.sqlite", rehearsal_root=root)

    conn = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        n = conn.execute("SELECT COUNT(*) FROM source_intelligence_sources").fetchone()[0]
        assert n > 0
    finally:
        conn.close()


def test_interrupted_backup_cannot_be_mistaken_for_valid(tmp_path):  # PC-AC-035
    root, fx = _fixture(tmp_path)
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)

    ok, _ = verify_backup(result.backup_path, result.receipt)
    assert ok  # the complete backup verifies

    # simulate an interrupted/partial write by truncating the backup file
    with open(result.backup_path, "r+b") as fh:
        fh.truncate(result.backup_path.stat().st_size // 2)

    ok, detail = verify_backup(result.backup_path, result.receipt)
    assert not ok  # size/hash/integrity mismatch -> not mistaken for valid
    assert detail in {"size_mismatch", "hash_mismatch", "integrity_failed"}


def test_backup_rejects_destination_outside_rehearsal_root(tmp_path):  # safety (PCR-001/008)
    root, fx = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(BackupError):
        backup_database(fx.db_path, outside, rehearsal_root=root)


def test_backup_rejects_symlinked_rehearsal_root(tmp_path):  # safety (PCR-001/008)
    root, fx = _fixture(tmp_path)
    real = tmp_path / "real_root"
    real.mkdir()
    link = tmp_path / "link_root"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(BackupError):
        backup_database(fx.db_path, link / "backups", rehearsal_root=link)
