"""Writable workspace DB for the internet-facing NAS MCP (isolated from the read-only snapshot).

WHY: the ``remote_cloudflare`` MCP reads a bind-mounted **read-only** DB snapshot
(``HB_ASSISTANT_DB_READONLY=1``) — the live production DB is NEVER mounted into the
internet-facing container. That makes the connected-client *staging* pipeline (session
capture → artifact proposal → review → promotion, generated-output stage/commit, tool-manifest
refresh) structurally unable to persist rows.

These staging repos write to a **self-contained** cluster of tables (no joins to source/vault/
authoritative data), so we route their reads+writes to a separate writable "workspace" SQLite DB
on a RW mount while the authoritative snapshot stays strictly read-only. The workspace DB is
created with the standard ``SQLiteMigrator`` (full head schema) so it can never drift from the
main schema — the repos simply use their own tables there.

The workspace path lands at ``.../app-support/mcp-workspace/db/hb-personal-assistant.sqlite`` so it
satisfies the NAS DB-storage guard unchanged (NAS-volume prefix + ``db`` parent + managed filename).
A later operator-run ``workspace → live`` merge job (mirror of ``snapshot-mcp-db.sh``) folds promoted
rows into the authoritative DB; that is deliberately out of the request path.
"""

from __future__ import annotations

import os
from pathlib import Path

# Default location for non-standard deployments; the NAS compose pins HB_ASSISTANT_WORKSPACE_DB
# explicitly. Only consulted under db_readonly() (the internet-facing profile), so this NAS-shaped
# default is never exercised on a dev/Mac host.
DEFAULT_WORKSPACE_DB_PATH = (
    "/volume2/personal-assistant/app-support/mcp-workspace/db/hb-personal-assistant.sqlite"
)


def workspace_db_path() -> Path:
    """Resolve the writable workspace DB path (``HB_ASSISTANT_WORKSPACE_DB`` or the NAS default)."""
    raw = os.environ.get("HB_ASSISTANT_WORKSPACE_DB", "").strip()
    return Path(raw) if raw else Path(DEFAULT_WORKSPACE_DB_PATH)


def ensure_workspace_db() -> Path:
    """Ensure the workspace DB exists and is migrated to the head schema; return its path.

    Idempotent and cheap on the hot path: only runs the migrator when the DB is below the head
    version (first container start), then no-ops. Reuses ``SQLiteMigrator`` so the workspace schema
    is byte-identical to the authoritative schema — no hand-maintained table list to drift.
    """
    path = workspace_db_path()
    from .migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator  # noqa: PLC0415

    migrator = SQLiteMigrator(str(path))
    if migrator.current_version() < LATEST_SCHEMA_VERSION:
        migrator.apply()
    return path
