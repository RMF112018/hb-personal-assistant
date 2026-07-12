"""N8C-24 — workspace repository lifecycle (stage/commit/idempotency/approval/archive)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.client_output_workspace import (
    ClientOutputError,
    ClientOutputWorkspaceRepository,
)
from tests.n8c24_helpers import make_env, stage_and_commit


def _repo(tmp_path: Path):
    env = make_env(tmp_path)
    return env, ClientOutputWorkspaceRepository(env["config"], env["db"])


def test_stage_does_not_write_and_mints_approval(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "Doc", "file_type": "docx",
                                "content_mode": "docx_from_markdown_or_text", "content_text": "# H\np",
                                "destination_state": "final"})
    assert s["writes"] is False and s["operator_approval_id"] and s["idempotency_key"]
    # nothing under 01 Final yet
    assert not list((env["outputs"] / "01 Final").rglob("*.docx"))


def test_commit_writes_real_file_receipt_manifest(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    out = stage_and_commit(repo, title="Checklist", file_type="docx",
                           content_mode="docx_from_markdown_or_text", content="# H\np")
    r = out["commit"]
    assert r["status"] == "committed"
    assert (env["outputs"] / r["relative_path"]).exists()
    assert (env["outputs"] / r["receipt_path"]).exists()
    assert (env["outputs"] / "99 Manifests/client-output-manifest.md").exists()
    assert (env["outputs"] / "99 Manifests/client-output-manifest.json").exists()


def test_commit_is_idempotent(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "x", "file_type": "md", "content_mode": "markdown_text",
                                "content_text": "hi", "destination_state": "final"})
    a = repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                                idempotency_key=s["idempotency_key"])
    b = repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                                idempotency_key=s["idempotency_key"])
    assert b["idempotent_reuse"] is True and a["sha256"] == b["sha256"]
    assert len(list((env["outputs"] / "01 Final").rglob("*.md"))) == 1  # no duplicate file


def test_forged_approval_rejected(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "x", "file_type": "md", "content_mode": "markdown_text",
                                "content_text": "hi"})
    with pytest.raises(ClientOutputError, match="operator_approval_mismatch"):
        repo.commit_output_file(output_id=s["output_id"], operator_approval_id="FORGED")


def test_idempotency_key_mismatch_rejected(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "x", "file_type": "md", "content_mode": "markdown_text",
                                "content_text": "hi"})
    with pytest.raises(ClientOutputError, match="idempotency_key_mismatch"):
        repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                                idempotency_key="WRONG")


def test_archive_moves_never_deletes(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    out = stage_and_commit(repo)
    oid = out["stage"]["output_id"]
    plan = repo.plan_archive_output(oid)
    assert plan["deletes"] is False and plan["writes"] is False
    ac = repo.commit_archive_output(output_id=oid, operator_approval_id=out["stage"]["operator_approval_id"])
    assert ac["status"] == "archived" and ac["deletes"] is False
    assert (env["outputs"] / ac["archive_relative_path"]).exists()  # file still present, just moved


def test_cancel_staged_output_is_terminal(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "x", "file_type": "md", "content_mode": "markdown_text",
                                "content_text": "hi"})
    oid = s["output_id"]
    c = repo.cancel_output_file(output_id=oid, operator_approval_id=s["operator_approval_id"])
    assert c["status"] == "cancelled" and c["idempotent_reuse"] is False and c["deletes"] is False
    # no longer stuck in staged (terminal), and the staged payload is dropped
    rec = repo.get_output_file(oid)
    assert rec["status"] == "superseded"
    import sqlite3
    raw = sqlite3.connect(str(repo.db_path)).execute(
        "SELECT staged_content_b64 FROM assistant_output_files WHERE output_id=?", (oid,)
    ).fetchone()
    assert raw[0] is None


def test_cancel_is_idempotent(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "x", "file_type": "md", "content_mode": "markdown_text",
                                "content_text": "hi"})
    a = repo.cancel_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"])
    b = repo.cancel_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"])
    assert a["idempotent_reuse"] is False and b["idempotent_reuse"] is True


def test_cancel_forged_approval_rejected(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "x", "file_type": "md", "content_mode": "markdown_text",
                                "content_text": "hi"})
    with pytest.raises(ClientOutputError, match="operator_approval_mismatch"):
        repo.cancel_output_file(output_id=s["output_id"], operator_approval_id="FORGED")


def test_cancel_rejects_committed_output(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    out = stage_and_commit(repo)
    with pytest.raises(ClientOutputError, match="only_staged_can_cancel"):
        repo.cancel_output_file(output_id=out["stage"]["output_id"],
                                operator_approval_id=out["stage"]["operator_approval_id"])


def test_read_excerpt_bounds_binary_and_text(tmp_path: Path) -> None:
    _, repo = _repo(tmp_path)
    md = stage_and_commit(repo, file_type="md", content_mode="markdown_text", content="hello world")
    ex = repo.read_output_excerpt(md["stage"]["output_id"])
    assert ex["preview_mode"] == "bounded_text_excerpt" and "hello" in ex["excerpt"]
    docx = stage_and_commit(repo, file_type="docx", content_mode="docx_from_markdown_or_text", content="# h")
    exb = repo.read_output_excerpt(docx["stage"]["output_id"])
    assert exb["preview_mode"] == "metadata_only"
