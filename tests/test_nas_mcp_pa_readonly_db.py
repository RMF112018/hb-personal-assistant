"""Workspace-DB behavior for the pa_* staging repositories on the RO-snapshot serve profile.

The internet-facing NAS MCP reads a bind-mounted **read-only** DB snapshot (``HB_ASSISTANT_DB_READONLY=1``).
The staging repositories (session capture / artifact proposals / promotion / generated output / tool
manifest) write to a **self-contained** cluster of tables with no joins to authoritative data, so on this
profile they route their reads+writes to a separate writable *workspace* DB (``HB_ASSISTANT_WORKSPACE_DB``)
while the authoritative snapshot stays strictly read-only. This suite proves:

* reads succeed (empty), as before;
* writes now PERSIST to the workspace DB (they used to fail closed ``read_only_db_surface``);
* the RO snapshot is never written;
* the local/ingest host (no ``HB_ASSISTANT_DB_READONLY``) keeps its ambient read-write path.
"""

from __future__ import annotations

import os
import sqlite3
import stat
import tempfile
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.artifact_workspace import ArtifactWorkspaceRepository
from hb_assistant.obsidian_mcp.client_tool_manifest import (
    ClientToolManifestRepository,
    build_manifest,
)
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def ro_profile(monkeypatch):
    """Simulate the internet-facing profile: a read-only snapshot mount + a writable workspace DB."""
    root = Path(tempfile.mkdtemp(prefix="pa-ro-db-"))
    snap_dir = root / "snapshot" / "db"
    snap_dir.mkdir(parents=True)
    snapshot = str(snap_dir / "hb-personal-assistant.sqlite")
    SQLiteMigrator(db_path=snapshot).apply()

    ws_dir = root / "mcp-workspace" / "db"
    ws_dir.mkdir(parents=True)
    workspace = str(ws_dir / "hb-personal-assistant.sqlite")

    # Simulate the read-only snapshot mount: parent dir not writable + the serve-profile env flags.
    os.chmod(snap_dir, stat.S_IRUSR | stat.S_IXUSR)
    monkeypatch.setenv("HB_ASSISTANT_DB_READONLY", "1")
    monkeypatch.setenv("HB_ASSISTANT_WORKSPACE_DB", workspace)
    try:
        yield {"snapshot": snapshot, "workspace": workspace}
    finally:
        os.chmod(snap_dir, stat.S_IRWXU)  # restore so tempdir cleanup can remove it


def _table_count(db: str, table: str) -> int:
    # immutable=1 mirrors the production RO-snapshot open (_ro_connect): needed to read a WAL-mode DB
    # whose containing dir is read-only without SQLite attempting a WAL/journal write.
    conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def test_artifact_reads_succeed(ro_profile):
    repo = ArtifactWorkspaceRepository(ro_profile["snapshot"])
    # The repo routes to the writable workspace DB; reads return empty, never "Database unavailable".
    assert repo.db_path == ro_profile["workspace"]
    assert repo.list_proposals() == []
    assert repo.list_canonical() == []
    assert repo.get_proposal("nope") is None


def test_artifact_writes_persist_to_workspace(ro_profile):
    repo = ArtifactWorkspaceRepository(ro_profile["snapshot"])
    out = repo.stage_session_capture({
        "source_client": "chatgpt", "session_title": "t", "capture_trigger": "document this session",
        "session_summary": "s",
    })
    assert out["session_id"]
    # Row lands in the workspace DB, and the RO snapshot is untouched.
    assert _table_count(ro_profile["workspace"], "pa_session_captures") == 1
    assert _table_count(ro_profile["snapshot"], "pa_session_captures") == 0


def test_full_staging_pipeline_persists(ro_profile):
    repo = ArtifactWorkspaceRepository(ro_profile["snapshot"])
    s = repo.stage_session_capture({
        "source_client": "chatgpt", "session_title": "t", "capture_trigger": "x", "session_summary": "s",
    })
    b = repo.stage_proposal_bundle(s["session_id"], [
        {"artifact_type": "decision", "title": "D", "body_markdown": "body", "domain": "nas"},
    ])
    pid = b["proposal_ids"][0]
    r = repo.review_proposal(pid, "approve", operator_id="op")
    assert r["operator_approval_id"]
    v = repo.validate_promotion(b["proposal_bundle_id"], operator_id="op")
    assert v["passed"] is True and v["promotion_bundle_id"]
    # Everything persisted to the workspace DB; the snapshot never received a proposal row.
    assert _table_count(ro_profile["workspace"], "pa_artifact_proposals") == 1
    assert _table_count(ro_profile["snapshot"], "pa_artifact_proposals") == 0


def test_manifest_persists_and_reads_back(ro_profile):
    repo = ClientToolManifestRepository(ro_profile["snapshot"])
    assert repo.db_path == ro_profile["workspace"]
    assert repo.get_active() is None  # nothing persisted yet
    manifest = build_manifest({"hb_mcp_status": {"group": "status"}}, runtime_commit="test", now="2026-07-08T00:00:00Z")
    manifest_id = repo.save_manifest(manifest)
    assert manifest_id
    active = repo.get_active()
    assert active is not None and active["manifest_status"] == "active"
    assert _table_count(ro_profile["workspace"], "pa_client_tool_manifests") == 1
    assert _table_count(ro_profile["snapshot"], "pa_client_tool_manifests") == 0


def test_output_repo_routes_db_to_workspace_but_writes_files(ro_profile, tmp_path):
    from hb_assistant.nas_mcp.client_output_workspace import ClientOutputWorkspaceRepository
    from tests.n8c24_helpers import make_env, stage_and_commit

    env = make_env(tmp_path)
    repo = ClientOutputWorkspaceRepository(env["config"], env["db"])
    assert repo.db_path == ro_profile["workspace"]  # DB routed to the workspace DB under RO profile
    out = stage_and_commit(repo, title="Doc", file_type="md", content_mode="markdown_text", content="# hi")
    assert out["commit"]["status"] == "committed"
    # Generated file lands on the RW outputs mount; the staging row lands in the workspace DB.
    assert (env["outputs"] / out["commit"]["relative_path"]).exists()
    assert _table_count(ro_profile["workspace"], "assistant_output_files") == 1
    assert _table_count(ro_profile["snapshot"], "assistant_output_files") == 0


def test_read_only_mode_off_still_writes(tmp_path):
    # Without HB_ASSISTANT_DB_READONLY (local/ingest host), the repo keeps its ambient read-write path.
    db = str(tmp_path / "rw.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = ArtifactWorkspaceRepository(db)
    assert repo.db_path == db
    out = repo.stage_session_capture({
        "source_client": "local", "session_title": "t", "capture_trigger": "x", "session_summary": "s",
    })
    assert out["session_id"]
