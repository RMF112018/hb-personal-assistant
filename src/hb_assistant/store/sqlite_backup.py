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
import os
import sqlite3
from collections.abc import Callable
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


def _assert_under_root(path: Path, root_resolved: Path) -> None:
    """Fail closed if ``path``'s resolved location is not under the rehearsal root."""
    resolved = path.parent.resolve() / path.name
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise BackupError(f"destination escapes the rehearsal root {root_resolved}: {path}")


def _open_dir_nofollow(dir_path: Path, root_resolved: Path) -> int:
    """Open a directory fd under the rehearsal root, rejecting a symlinked final component.

    Subsequent file creation uses ``openat`` relative to this fd, which is bound to the directory
    *inode* — so the write target cannot be redirected by later replacing a path component.
    """
    _assert_under_root(dir_path, root_resolved)
    try:
        return os.open(str(dir_path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise BackupError(f"destination directory is a symlink or unusable (fail-closed): {dir_path}") from exc


def _write_bytes_nofollow(dir_fd: int, name: str, data: bytes) -> None:
    """Race-resistantly create+write a NEW file under ``dir_fd`` (PC-WI02-EXT-REV-F-001).

    A single ``openat(dir_fd, name, O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW)`` atomically creates the file
    or fails — there is no create-then-reopen-by-path window, and a symlink/existing name at ``name``
    is rejected (``O_NOFOLLOW``/``O_EXCL``). The bytes are written to *that* descriptor, so the write
    cannot be redirected outside the rehearsal root even under a concurrent target swap.
    """
    if "/" in name or name in ("", ".", ".."):
        raise BackupError(f"unsafe destination filename: {name!r}")
    try:
        fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
    except FileExistsError as exc:
        raise BackupError(f"destination already exists (fail-closed): {name}") from exc
    except OSError as exc:  # ELOOP when the final component is a symlink under O_NOFOLLOW
        raise BackupError(f"destination is a symlink or unusable (fail-closed): {name}") from exc
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
    finally:
        os.close(fd)


def _snapshot_to_bytes(source_db: Path) -> bytes:
    """Consistent online snapshot via ``Connection.backup()`` over a read-only source URI, as bytes.

    The snapshot is taken into an in-memory database and serialized, so the on-disk backup is written
    from an already-captured image via a symlink-safe descriptor (no ``sqlite3.connect`` reopen of the
    destination path).
    """
    src = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:")
    try:
        src.backup(mem)
        return bytes(mem.serialize())
    finally:
        mem.close()
        src.close()


def backup_database(
    source_db: Path,
    dest_dir: Path,
    *,
    rehearsal_root: Path,
    _after_snapshot: Callable[[], None] | None = None,
    _before_write: Callable[[], None] | None = None,
) -> BackupResult:
    """Create a consistent online backup of ``source_db`` under ``dest_dir`` with a durable receipt.

    The snapshot is captured with ``Connection.backup()`` and written to disk via a symlink-safe
    ``openat`` descriptor (no reopen of the destination path), so a concurrent target swap cannot
    redirect the write outside the rehearsal root (PC-WI02-EXT-REV-F-001).

    The receipt's identity is bound to the **backup snapshot**: ``backup_logical_hash`` is the
    authoritative snapshot state, and ``status`` is ``"complete"`` only when the live source still
    equals the snapshot; otherwise ``"source_advanced_during_backup"`` (PC-WI02-EXT-REV-F-003).

    ``_after_snapshot`` / ``_before_write`` are test-only injectable hooks (fired after the snapshot,
    and immediately before the on-disk write, respectively).
    """
    source = Path(source_db)
    if not source.is_file():
        raise BackupError(f"source database does not exist (fail-closed): {source}")
    _refuse_app_db(source)
    root_resolved = _validated_rehearsal_root(rehearsal_root)
    dest = _validated_dest_dir(dest_dir, rehearsal_root)

    data = _snapshot_to_bytes(source)  # consistent online snapshot (Connection.backup over mode=ro)
    if _after_snapshot is not None:
        _after_snapshot()

    backup_name = source.name + ".backup"
    dir_fd = _open_dir_nofollow(dest, root_resolved)
    try:
        if _before_write is not None:
            _before_write()
        _write_bytes_nofollow(dir_fd, backup_name, data)  # race-resistant; rejects swapped-in symlink

        backup_path = dest / backup_name
        schema_head = collect_inventory(backup_path).schema_head
        if schema_head is None:
            raise BackupError(f"backup has no schema_migrations head: {backup_path}")

        snapshot_logical = source_index_logical_hash(backup_path)  # authoritative snapshot identity
        live_source_logical = source_index_logical_hash(source)
        status = (
            "complete" if live_source_logical == snapshot_logical else "source_advanced_during_backup"
        )

        receipt = BackupReceipt(
            generated_utc=_now_utc(),
            schema_version=int(schema_head),
            backup_path=str(backup_path.resolve()),
            backup_sha256=_sha256(backup_path),
            byte_size=backup_path.stat().st_size,
            source_logical_hash=live_source_logical,
            backup_logical_hash=snapshot_logical,
            status=status,
        )
        receipt_name = backup_name + ".receipt.json"
        _write_bytes_nofollow(
            dir_fd, receipt_name, (json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    finally:
        os.close(dir_fd)
    return BackupResult(
        backup_path=dest / backup_name, receipt_path=dest / receipt_name, receipt=receipt
    )


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


def restore_backup(
    backup_path: Path,
    dest_path: Path,
    *,
    rehearsal_root: Path,
    _before_write: Callable[[], None] | None = None,
) -> Path:
    """Restore a verified backup to an independent ``dest_path`` under the rehearsal root.

    The restore image is captured with ``Connection.backup()`` and written via a symlink-safe
    ``openat`` descriptor (no path reopen), so a concurrent target swap cannot redirect the restore
    outside the rehearsal root (PC-WI02-EXT-REV-F-001). ``_before_write`` is a test-only hook fired
    immediately before the on-disk write.
    """
    backup = Path(backup_path)
    if not backup.is_file():
        raise BackupError(f"backup does not exist (fail-closed): {backup}")
    target = Path(dest_path)
    root_resolved = _validated_rehearsal_root(rehearsal_root)
    dest_dir = _validated_dest_dir(target.parent, rehearsal_root)
    _refuse_app_db(target)

    data = _snapshot_to_bytes(backup)
    dir_fd = _open_dir_nofollow(dest_dir, root_resolved)
    try:
        if _before_write is not None:
            _before_write()
        _write_bytes_nofollow(dir_fd, target.name, data)  # race-resistant; rejects swapped-in symlink
    finally:
        os.close(dir_fd)
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
