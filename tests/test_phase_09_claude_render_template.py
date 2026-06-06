"""Phase 09 Addendum — Claude scheduled-task render template proof tests."""

from __future__ import annotations

import re

import pytest

from hb_assistant.construction.second_brain.financial_review_routing import _assert_no_raw
from hb_assistant.construction.second_brain.mcp import render_template_proof as rtp
from hb_assistant.construction.second_brain.mcp.render_template_proof import (
    ClaudeRenderTemplateError,
    build_claude_render_template_proof,
)

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)


def test_both_templates_exist() -> None:
    d = rtp._templates_dir()
    for name in rtp._TEMPLATES:
        assert (d / name).exists(), name


def test_proof_passes_with_all_required_clauses() -> None:
    proof = build_claude_render_template_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["template_count"] == 2
    for name, report in proof["templates"].items():
        assert report["all_present"] is True, f"{name} missing: " + str(
            sorted(k for k, v in report["checks"].items() if not v)
        )


def test_templates_forbid_direct_tools_and_determinations() -> None:
    proof = build_claude_render_template_proof(write_evidence=False)
    for report in proof["templates"].values():
        c = report["checks"]
        assert c["calls_packet_tool"]
        assert c["no_raw_records"]
        assert c["forbid_database"] and c["forbid_graph"] and c["forbid_procore"]
        assert c["forbid_vector"] and c["forbid_memory_mutation"]
        assert c["no_determinations"]


def test_templates_preserve_warnings_and_coverage() -> None:
    proof = build_claude_render_template_proof(write_evidence=False)
    for report in proof["templates"].values():
        c = report["checks"]
        assert c["preserve_review_required"]
        assert c["preserve_stale"] and c["preserve_low_confidence"]
        assert c["include_source_coverage"]
        assert c["include_follow_up_questions"]


def test_templates_state_storage_policy() -> None:
    proof = build_claude_render_template_proof(write_evidence=False)
    for report in proof["templates"].values():
        c = report["checks"]
        assert c["storage_not_source_truth"]
        assert c["storage_no_accepted_memory"]
        assert c["storage_no_vector_index"]
        assert c["storage_no_source_manifest"]
        assert c["storage_no_source_linked_proof"]


def test_templates_have_seven_sections_and_advisory_notice() -> None:
    proof = build_claude_render_template_proof(write_evidence=False)
    section_keys = [
        "section_what_matters_today",
        "section_review_required_items",
        "section_aging_stale_items",
        "section_meeting_prep",
        "section_risk_watchlist",
        "section_source_coverage_notes",
        "section_follow_up_questions",
    ]
    for report in proof["templates"].values():
        for k in section_keys:
            assert report["checks"][k], k
        assert report["checks"]["advisory_notice"]


def test_templates_are_no_raw_clean() -> None:
    d = rtp._templates_dir()
    for name in rtp._TEMPLATES:
        _assert_no_raw((d / name).read_text(encoding="utf-8"), name)


def test_proof_writes_evidence_artifacts(tmp_path) -> None:
    proof = build_claude_render_template_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert proof["proof_passed"] is True
    for fname in (
        "claude-rendering-template-proof.json",
        "claude-rendering-template-proof.md",
        "claude-daily-brief-scheduled-task-template.md",
        "claude-daily-brief-manual-run-template.md",
    ):
        assert (tmp_path / fname).exists(), fname
    assert not _SECRET_OR_URL.search(
        (tmp_path / "claude-rendering-template-proof.json").read_text()
    )


def test_missing_template_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Point the templates dir at an empty location → fail closed.
    monkeypatch.setattr(rtp, "_templates_dir", lambda: tmp_path)
    with pytest.raises(ClaudeRenderTemplateError):
        build_claude_render_template_proof(write_evidence=False)
