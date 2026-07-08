"""Read-only-DB behavior for the pa_* workspace repositories (RO-snapshot serve profile).

The internet-facing NAS MCP reads a bind-mounted read-only DB snapshot. The workspace repositories must
open reads immutable/read-only (so list/get/manifest tools work) and fail writes closed with an honest
``read_only_db_surface`` error — NOT the misleading "Database unavailable" the writable-parent readiness
check used to raise. Simulated by a migrated temp DB whose parent dir is chmod read-only + the
``HB_ASSISTANT_DB_READONLY`` env the compose sets.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.artifact_workspace import (
    ArtifactWorkspaceError,
    ArtifactWorkspaceRepository,
)
from hb_assistant.obsidian_mcp.client_tool_manifest import ClientToolManifestRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def ro_db(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="pa-ro-db-"))
    dbdir = root / "db"
    dbdir.mkdir()
    db = str(dbdir / "snapshot.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # Simulate the read-only snapshot mount: parent dir not writable + the serve-profile env flag.
    os.chmod(dbdir, stat.S_IRUSR | stat.S_IXUSR)
    monkeypatch.setenv("HB_ASSISTANT_DB_READONLY", "1")
    try:
        yield db
    finally:
        os.chmod(dbdir, stat.S_IRWXU)  # restore so tempdir cleanup can remove it


def test_artifact_reads_succeed_read_only(ro_db):
    repo = ArtifactWorkspaceRepository(ro_db)
    # These are the tools the client audit saw fail with "Database unavailable" — must now return data.
    assert repo.list_proposals() == []
    assert repo.list_canonical() == []
    assert repo.get_proposal("nope") is None
    assert repo.get_canonical("nope") is None


def test_artifact_writes_fail_closed_honestly(ro_db):
    repo = ArtifactWorkspaceRepository(ro_db)
    with pytest.raises(ArtifactWorkspaceError) as ei:
        repo.stage_session_capture({
            "source_client": "chatgpt", "session_title": "t", "capture_trigger": "x",
            "session_summary": "s",
        })
    # Honest, actionable error — never the misleading "Database unavailable".
    assert "read_only_db_surface" in str(ei.value)
    assert "Database unavailable" not in str(ei.value)


def test_manifest_reads_succeed_writes_fail_closed(ro_db):
    repo = ClientToolManifestRepository(ro_db)
    assert repo.get_active() is None  # read works read-only
    with pytest.raises(ArtifactWorkspaceError) as ei:
        repo.save_manifest({"generated_at": "2026-07-08T00:00:00Z", "checksum": "abc"})
    assert "read_only_db_surface" in str(ei.value)


def test_read_only_mode_off_still_writes(tmp_path):
    # Without HB_ASSISTANT_DB_READONLY (local/ingest host), the repo keeps its normal read-write path.
    db = str(tmp_path / "rw.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = ArtifactWorkspaceRepository(db)
    out = repo.stage_session_capture({
        "source_client": "local", "session_title": "t", "capture_trigger": "x", "session_summary": "s",
    })
    assert out["session_id"]
