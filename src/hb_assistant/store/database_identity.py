"""Opened-database identity for the migration-ownership guard (NF-F-001 / NF-F-011, NF-AUD-005).

Path-string authorization is insufficient: a symlink, an ``ATTACH``, or a rename/replace can make a
*declared* managed path resolve to a different file, and a file can be swapped between validation and
commit (TOCTOU). Before any migration DDL the migrator must bind authorization to the database SQLite
ACTUALLY opened, discovered from the live connection via ``PRAGMA database_list`` (the real ``main``
file), and to that file's **device/inode via a retained read-only guard FD** so identity stays pinned
across the migration boundary.

Guarantees:
- The effective path comes from the open connection, so a substituted/symlinked/attached target is
  revealed and re-classified — it can never inherit the declared path's storage class.
- A read-only ``guard_fd`` is opened on the effective file and returned; ``os.fstat`` on it yields
  device/inode that remain valid even if the path is renamed, letting the migrator revalidate at the
  critical boundary. The caller (migrator) owns and closes the FD.
- Fails closed: if no ``main`` database is attached, raise ``OpenedDatabaseIdentityUnavailable`` rather
  than silently downgrading the target-binding guarantee.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from hb_assistant.config.db_storage_guard import DatabaseStorageClass, classify_storage_class

from .errors import OpenedDatabaseIdentityUnavailable
from .migration_authorization import OpenedDatabaseIdentity


def describe_opened_database(
    conn: sqlite3.Connection, declared_path: str | None
) -> OpenedDatabaseIdentity:
    """Return the identity of the ``main`` database actually attached to ``conn``.

    ``declared_path`` is only diagnostic; the enforced identity is derived from the live connection.
    Opens and retains a read-only guard FD on the effective file (when it exists) — the caller MUST
    close ``guard_fd``. Raises ``OpenedDatabaseIdentityUnavailable`` when no ``main`` DB is attached.
    """
    main_file: str | None = None
    for _seq, name, file in conn.execute("PRAGMA database_list").fetchall():
        if name == "main":
            main_file = file
            break
    if main_file is None:
        raise OpenedDatabaseIdentityUnavailable(
            "could not establish opened-database identity: no 'main' database attached"
        )

    # An empty file string means an in-memory / private-temp database — never a managed target.
    effective_path = main_file or ""
    resolved_path = str(Path(effective_path).resolve()) if effective_path else ""

    guard_fd: int | None = None
    device: int | None = None
    inode: int | None = None
    if effective_path:
        try:
            guard_fd = os.open(effective_path, os.O_RDONLY)
            st = os.fstat(guard_fd)
            device, inode = st.st_dev, st.st_ino
        except OSError:
            # File not yet materialized (fresh DB about to be created) or unopenable. Identity then
            # rests on the canonical path; the migrator's revalidation enforces fail-closed rules for
            # managed targets that require a pinned guard FD.
            if guard_fd is not None:
                os.close(guard_fd)
                guard_fd = None
            device = inode = None

    storage_class = (
        classify_storage_class(resolved_path) if resolved_path else DatabaseStorageClass.BLOCKED
    )
    return OpenedDatabaseIdentity(
        effective_path=effective_path,
        resolved_path=resolved_path,
        device=device,
        inode=inode,
        pragma_database_name="main",
        storage_class=storage_class,
        guard_fd=guard_fd,
    )
