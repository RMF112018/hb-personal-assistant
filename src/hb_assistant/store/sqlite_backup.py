"""Online SQLite backup + independent restore assurance for Source-Index Phase C (PC-WI-02).

Provides a **consistent online backup** of a source-index database via ``sqlite3.Connection.backup()``
over a **read-only source URI** (``mode=ro``) — never a raw file copy while a WAL is active — with a
durable, redacted receipt carrying the backup's SHA-256 and a logical-inventory hash; an **independent
restore** to a new location; **restored-database validation** (integrity + logical inventory); and
**interrupted-backup detection** so a partial/corrupt backup cannot be mistaken for a valid one
(PC-AC-030..035).

Safety (PCR-001 / PCR-008): every backup/restore destination must live under a **caller-provided
rehearsal root** — destinations outside it, or a symlinked root, are rejected fail-closed; the
configured application database is refused. ``config.path_policy`` may be inspected for naming/receipt
conventions only and never determines a destination. This module performs no migration, repair,
reindex, or production/NAS access.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.store.source_index_migration_assurance import (
    collect_inventory,
    source_index_logical_hash,
)


class BackupError(Exception):
    """Raised fail-closed on any unsafe or invalid backup/restore request."""


@dataclass
class BackupReceipt:
    generated_utc: str
    schema_version: int
    backup_path: str  # resolvable path to the backup file (a rehearsal-root location, not source content)
    backup_sha256: str
    byte_size: int
    source_logical_hash: str
    backup_logical_hash: str
    status: str


@dataclass
class BackupResult:
    backup_path: Path
    receipt_path: Path
    receipt: BackupReceipt


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configured_app_db() -> Path | None:
    """Best-effort resolution of the configured application DB path (naming inspection only)."""
    try:
        from hb_assistant.config.path_policy import PathPolicy

        return Path(PathPolicy().get_db_path()).resolve()
    except Exception:
        return None


def _refuse_app_db(path: Path) -> None:
    app_db = _configured_app_db()
    if app_db is not None and Path(path).resolve() == app_db:
        raise BackupError(f"refusing to target the configured application database: {path}")


def _validated_rehearsal_root(rehearsal_root: Path) -> Path:
    root = Path(rehearsal_root)
    if root.is_symlink():
        raise BackupError(f"rehearsal_root is a symlink (rejected): {root}")
    if not root.is_dir():
        raise BackupError(f"rehearsal_root is not an existing directory: {root}")
    return root.resolve()


def _validated_dest_dir(dest_dir: Path, rehearsal_root: Path) -> Path:
    root = _validated_rehearsal_root(rehearsal_root)
    target = Path(dest_dir)
    if not target.is_dir():
        raise BackupError(f"destination directory does not exist: {target}")
    resolved = target.resolve()
    if resolved != root and root not in resolved.parents:
        raise BackupError(f"destination escapes the rehearsal root {root}: {dest_dir}")
    return resolved


def _online_backup(source_db: Path, dest_file: Path) -> None:
    """Consistent online backup over a read-only source URI; leaves no WAL on the destination."""
    src = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dest_file))
    try:
        src.backup(dst)
        dst.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dst.commit()
    finally:
        dst.close()
        src.close()


def backup_database(source_db: Path, dest_dir: Path, *, rehearsal_root: Path) -> BackupResult:
    """Create a consistent online backup of ``source_db`` under ``dest_dir`` with a durable receipt."""
    source = Path(source_db)
    if not source.is_file():
        raise BackupError(f"source database does not exist (fail-closed): {source}")
    _refuse_app_db(source)
    dest = _validated_dest_dir(dest_dir, rehearsal_root)

    backup_path = dest / (source.name + ".backup")
    _online_backup(source, backup_path)

    schema_head = collect_inventory(backup_path).schema_head
    if schema_head is None:
        raise BackupError(f"backup has no schema_migrations head: {backup_path}")

    receipt = BackupReceipt(
        generated_utc=_now_utc(),
        schema_version=int(schema_head),
        backup_path=str(backup_path.resolve()),
        backup_sha256=_sha256(backup_path),
        byte_size=backup_path.stat().st_size,
        source_logical_hash=source_index_logical_hash(source),
        backup_logical_hash=source_index_logical_hash(backup_path),
        status="complete",
    )
    receipt_path = dest / (backup_path.name + ".receipt.json")
    receipt_path.write_text(
        json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return BackupResult(backup_path=backup_path, receipt_path=receipt_path, receipt=receipt)


def load_receipt(receipt_path: Path) -> BackupReceipt:
    payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    return BackupReceipt(**payload)


def verify_backup(backup_path: Path, receipt: BackupReceipt) -> tuple[bool, str]:
    """Return (valid, reason). A partial/corrupt backup fails size/hash/integrity — never mistaken as valid."""
    path = Path(backup_path)
    if not path.is_file():
        return False, "missing"
    if path.stat().st_size != receipt.byte_size:
        return False, "size_mismatch"
    if _sha256(path) != receipt.backup_sha256:
        return False, "hash_mismatch"
    try:
        inv = collect_inventory(path)
    except Exception:
        return False, "integrity_failed"
    if inv.integrity.quick_check != "ok" or inv.integrity.integrity_check != "ok":
        return False, "integrity_failed"
    return True, "valid"


def restore_backup(backup_path: Path, dest_path: Path, *, rehearsal_root: Path) -> Path:
    """Restore a verified backup to an independent ``dest_path`` under the rehearsal root."""
    backup = Path(backup_path)
    if not backup.is_file():
        raise BackupError(f"backup does not exist (fail-closed): {backup}")
    target = Path(dest_path)
    _validated_dest_dir(target.parent, rehearsal_root)
    _refuse_app_db(target)
    if target.exists():
        raise BackupError(f"restore destination already exists (fail-closed): {target}")
    _online_backup(backup, target)
    return target


def validate_restored(restored_db: Path, expected_source_logical_hash: str) -> tuple[bool, str]:
    """Restored DB passes integrity + logical-inventory validation and matches the source (PC-AC-033)."""
    restored = Path(restored_db)
    inv = collect_inventory(restored)
    if inv.integrity.quick_check != "ok":
        return False, "quick_check"
    if inv.integrity.integrity_check != "ok":
        return False, "integrity_check"
    if inv.integrity.foreign_key_violations != 0:
        return False, "foreign_key_violations"
    if source_index_logical_hash(restored) != expected_source_logical_hash:
        return False, "logical_inventory_mismatch"
    return True, "valid"
