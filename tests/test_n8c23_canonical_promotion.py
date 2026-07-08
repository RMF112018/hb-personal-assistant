"""N8C-23 — canonical promotion + Obsidian materialization (idempotency, trust gates, partial failure)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.artifact_promotion import promote_bundle
from hb_assistant.obsidian_mcp.artifact_workspace import (
    ArtifactWorkspaceError,
    ArtifactWorkspaceRepository,
)
from tests.n8c23_helpers import make_env, staged_bundle


def _approve_and_validate(repo, n=3):
    bundle = staged_bundle(repo)
    for pid in bundle["proposal_ids"][:n]:
        repo.review_proposal(pid, "approve", operator_id="bobby")
    return bundle, repo.validate_promotion(bundle["proposal_bundle_id"], operator_id="bobby")


def test_promote_writes_canonical_cards_receipt_and_manifest(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ArtifactWorkspaceRepository(env["db"])
    _, val = _approve_and_validate(repo, n=3)
    res = promote_bundle(env["config"], env["db"], promotion_bundle_id=val["promotion_bundle_id"],
                         operator_approval_id=val["operator_approval_id"], idempotency_key=val["idempotency_key"],
                         operator_id="bobby", runtime_commit="vTEST")
    assert res["status"] == "promoted" and res["created_count"] == 3 and res["failed_count"] == 0
    vault = env["vault"]
    for rel in res["created_paths"]:
        p = vault / rel
        assert p.exists()
        txt = p.read_text()
        assert "canonical_id:" in txt and "second-brain/canonical" in txt and "[[SESSION-" in txt
    assert (vault / res["receipt_vault_path"]).exists()
    assert (vault / "99 System/Manifests/canonical-artifact-manifest.md").exists()
    assert (vault / "99 System/Manifests/canonical-artifact-manifest.json").exists()
    # canonical rows readable for future retrieval
    assert len(repo.list_canonical(limit=50)) == 3


def test_promotion_is_idempotent(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ArtifactWorkspaceRepository(env["db"])
    _, val = _approve_and_validate(repo, n=2)
    a = promote_bundle(env["config"], env["db"], promotion_bundle_id=val["promotion_bundle_id"],
                       operator_approval_id=val["operator_approval_id"], idempotency_key=val["idempotency_key"])
    b = promote_bundle(env["config"], env["db"], promotion_bundle_id=val["promotion_bundle_id"],
                       operator_approval_id=val["operator_approval_id"], idempotency_key=val["idempotency_key"])
    assert b["idempotent_reuse"] is True
    assert a["promotion_receipt_id"] == b["receipt"]["promotion_receipt_id"]
    assert len(repo.list_canonical(limit=50)) == 2  # no duplication


def test_promotion_rejects_forged_approval_on_fresh_bundle(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ArtifactWorkspaceRepository(env["db"])
    _, val = _approve_and_validate(repo, n=2)
    with pytest.raises(ArtifactWorkspaceError, match="operator_approval_mismatch"):
        promote_bundle(env["config"], env["db"], promotion_bundle_id=val["promotion_bundle_id"],
                       operator_approval_id="FORGED-APPROVAL")


def test_promotion_requires_revalidation_if_plan_changed(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ArtifactWorkspaceRepository(env["db"])
    bundle, val = _approve_and_validate(repo, n=2)
    # Approve one MORE proposal after validation -> the recomputed hash no longer matches.
    repo.review_proposal(bundle["proposal_ids"][2], "approve", operator_id="bobby")
    with pytest.raises(ArtifactWorkspaceError, match="revalidation_required"):
        promote_bundle(env["config"], env["db"], promotion_bundle_id=val["promotion_bundle_id"],
                       operator_approval_id=val["operator_approval_id"])


def test_partial_failure_marks_repair(tmp_path: Path, monkeypatch) -> None:
    env = make_env(tmp_path)
    repo = ArtifactWorkspaceRepository(env["db"])
    _, val = _approve_and_validate(repo, n=2)
    # Force the card write to fail for every artifact.
    import hb_assistant.obsidian_mcp.artifact_promotion as ap

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(ap, "create_card", boom)
    res = promote_bundle(env["config"], env["db"], promotion_bundle_id=val["promotion_bundle_id"],
                         operator_approval_id=val["operator_approval_id"])
    assert res["status"] == "partial_failure" and res["failed_count"] == 2
    # canonical rows exist but marked needing repair; repair tasks recorded
    canon = repo.list_canonical(limit=50)
    assert canon and all(c["status"] == "promotion_partial_failure" for c in canon)
