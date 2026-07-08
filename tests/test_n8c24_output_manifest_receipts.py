"""N8C-24 — receipts + manifest content."""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.nas_mcp.client_output_workspace import ClientOutputWorkspaceRepository
from tests.n8c24_helpers import good_zip_b64, make_env, stage_and_commit


def _repo(tmp_path: Path):
    env = make_env(tmp_path)
    return env, ClientOutputWorkspaceRepository(env["config"], env["db"])


def test_commit_receipt_has_integrity_and_provenance(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    out = stage_and_commit(repo, title="Brief", file_type="md", content_mode="markdown_text", content="hi")
    receipt = repo.get_output_receipt(out["commit"]["receipt_id"])
    assert receipt["receipt_type"] == "commit" and receipt["sha256"]
    card = (env["outputs"] / out["commit"]["receipt_path"]).read_text()
    assert "Output File Receipt" in card and "SHA256:" in card and "chatgpt" in card


def test_zip_receipt_records_validation(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    s = repo.stage_output_file({"title": "Pkg", "file_type": "zip", "content_mode": "zip_base64",
                                "content_base64": good_zip_b64(), "destination_state": "final"})
    r = repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                                idempotency_key=s["idempotency_key"])
    card = (env["outputs"] / r["receipt_path"]).read_text()
    assert "ZIP Validation" in card and "Member count:" in card


def test_manifest_json_lists_committed(tmp_path: Path) -> None:
    env, repo = _repo(tmp_path)
    stage_and_commit(repo, title="One", file_type="md", content_mode="markdown_text", content="a")
    stage_and_commit(repo, title="Two", file_type="txt", content_mode="text", content="b")
    entries = json.loads((env["outputs"] / "99 Manifests/client-output-manifest.json").read_text())
    assert len(entries) == 2 and all(e["status"] == "committed" for e in entries)
    m = repo.get_output_manifest()
    assert m["entry_count"] == 2
