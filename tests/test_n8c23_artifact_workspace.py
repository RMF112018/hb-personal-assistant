"""N8C-23 — session capture, proposal staging, review, versioning, plan, and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.artifact_workspace import (
    ArtifactWorkspaceError,
    ArtifactWorkspaceRepository,
)
from tests.n8c23_helpers import DEFAULT_CANDIDATES, make_env, staged_bundle


@pytest.fixture()
def repo(tmp_path: Path) -> ArtifactWorkspaceRepository:
    return ArtifactWorkspaceRepository(make_env(tmp_path)["db"])


def test_stage_session_capture_and_get(repo) -> None:
    sc = repo.stage_session_capture({
        "source_client": "chatgpt", "session_title": "Plan", "capture_trigger": "document this session",
        "session_summary": "summary", "selected_excerpts": ["a", "b"], "redaction_state": "redacted"})
    assert sc["session_id"].startswith("SESSION-")
    got = repo.get_session_capture(sc["session_id"])
    assert got["source_client"] == "chatgpt" and got["content_hash"] == sc["content_hash"]


def test_capture_rejects_raw_transcript_and_missing_fields(repo) -> None:
    with pytest.raises(ArtifactWorkspaceError, match="raw_transcript_not_allowed"):
        repo.stage_session_capture({"source_client": "x", "session_title": "t", "capture_trigger": "c",
                                    "session_summary": "s", "raw_transcript": "..."})
    with pytest.raises(ArtifactWorkspaceError, match="missing_source_client"):
        repo.stage_session_capture({"session_title": "t", "capture_trigger": "c", "session_summary": "s"})


def test_capture_rejects_oversized(repo) -> None:
    with pytest.raises(ArtifactWorkspaceError, match="session_summary_too_large"):
        repo.stage_session_capture({"source_client": "x", "session_title": "t", "capture_trigger": "c",
                                    "session_summary": "z" * 9000})
    with pytest.raises(ArtifactWorkspaceError, match="excerpts_too_large"):
        repo.stage_session_capture({"source_client": "x", "session_title": "t", "capture_trigger": "c",
                                    "session_summary": "s", "selected_excerpts": ["z" * 21000]})


def test_stage_proposal_bundle_and_packet(repo) -> None:
    bundle = staged_bundle(repo)
    assert bundle["proposal_bundle_id"].startswith("BUNDLE-")
    assert len(bundle["proposal_ids"]) == len(DEFAULT_CANDIDATES)
    assert "Session Capture Review Packet" in bundle["review_packet_markdown"]
    assert bundle["review_packet"]["count"] == len(DEFAULT_CANDIDATES)


def test_unknown_artifact_type_rejected(repo) -> None:
    sc = repo.stage_session_capture({"source_client": "x", "session_title": "t", "capture_trigger": "c",
                                     "session_summary": "s"})
    with pytest.raises(ArtifactWorkspaceError, match="unknown_artifact_type"):
        repo.stage_proposal_bundle(sc["session_id"], [{"artifact_type": "bogus", "title": "t"}])


def test_review_decisions_and_approval_minting(repo) -> None:
    bundle = staged_bundle(repo)
    pid = bundle["proposal_ids"][0]
    res = repo.review_proposal(pid, "approve", operator_id="bobby")
    assert res["review_status"] == "approved" and res["operator_approval_id"]
    # reject mints no approval id
    rej = repo.review_proposal(bundle["proposal_ids"][1], "reject", operator_id="bobby")
    assert rej["operator_approval_id"] is None
    decisions = repo.get_review_decisions(pid)
    assert decisions and decisions[0]["decision"] == "approve"


def test_revision_creates_new_version_never_overwrites_v1(repo) -> None:
    bundle = staged_bundle(repo)
    pid = bundle["proposal_ids"][2]
    before = repo.get_proposal(pid)
    r = repo.revise_proposal(pid, body_markdown="revised body", revision_summary="clarify",
                             created_by_client="chatgpt")
    assert r["version"] == 2 and r["content_hash"] != before["content_hash"]
    after = repo.get_proposal(pid)
    assert after["version"] == 2 and after["review_status"] == "revised"


def test_plan_promotion_advisory_no_write(repo) -> None:
    bundle = staged_bundle(repo)
    for pid in bundle["proposal_ids"][:3]:
        repo.review_proposal(pid, "approve", operator_id="bobby")
    plan = repo.plan_promotion(bundle["proposal_bundle_id"])
    assert plan["writes"] is False and plan["approved_count"] == 3
    for item in plan["would_create"]:
        assert item["proposed_vault_path"].split("/", 1)[0] in {"Work", "Home", "AI Outputs", "Source Notes",
                                                                "00 Inbox", "99 System"}
        assert "second-brain/canonical" in item["tags"]


def test_validate_binds_plan_and_mints_server_ids(repo) -> None:
    bundle = staged_bundle(repo)
    for pid in bundle["proposal_ids"][:2]:
        repo.review_proposal(pid, "approve", operator_id="bobby")
    val = repo.validate_promotion(bundle["proposal_bundle_id"], operator_id="bobby")
    assert val["passed"] and val["promotion_bundle_id"].startswith("PROMOB-")
    assert val["operator_approval_id"] and val["validation_hash"] and val["idempotency_key"]
    # recomputed hash is stable while nothing changes
    assert repo.recompute_validation_hash(val["promotion_bundle_id"]) == val["validation_hash"]


def test_validate_refuses_when_nothing_approved(repo) -> None:
    bundle = staged_bundle(repo)
    with pytest.raises(ArtifactWorkspaceError, match="no_approved_proposals_to_promote"):
        repo.validate_promotion(bundle["proposal_bundle_id"])
