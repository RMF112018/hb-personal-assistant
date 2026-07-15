"""Opened-database identity for the migration-ownership guard (NF-F-001, plan §8).

Path-string authorization is insufficient: a symlink, an ``ATTACH``, or an in-memory/temp handle can
make a *declared* managed path resolve to a different file at open time. Before any migration DDL the
migrator must bind authorization to the database SQLite ACTUALLY opened, discovered from the live
connection via ``PRAGMA database_list`` (the real ``main`` file), not from the caller-declared path.

Guarantees:
- The effective path comes from the open connection, so a substituted/symlinked/attached target is
  revealed and re-classified — it can never inherit the declared path's storage class.
- ``resolved_path`` is canonicalized (symlinks followed) for exact-path authorization matching.
- Fails closed: if no ``main`` database is attached (identity cannot be established), raise
  ``OpenedDatabaseIdentityUnavailable`` rather than silently downgrading the target-binding guarantee.
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

    ``declared_path`` is only used for diagnostics; the enforced identity is derived from the live
    connection. Raises ``OpenedDatabaseIdentityUnavailable`` when no ``main`` database is attached.
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

    device: int | None = None
    inode: int | None = None
    if effective_path:
        try:
            st = os.stat(effective_path)
            device, inode = st.st_dev, st.st_ino
        except OSError:
            # File not yet materialized (fresh DB about to be created). Identity still rests on the
            # canonical path; device/inode remain unavailable for this pre-creation call.
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
    )
