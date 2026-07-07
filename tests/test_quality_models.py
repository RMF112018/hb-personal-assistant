"""N8C-20 — quality models: deterministic + idempotent ids, bounded text, pinned advisory policy, enum
validation, advisory-only (no accept/reject/repair field on a finding row)."""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp import quality_models as M


def test_policy_block_is_fixed_advisory() -> None:
    assert M.QUALITY_POLICY_BLOCK == {
        "action_policy": "no_execution",
        "execution_policy": "evaluate_only",
        "review_policy": "advisory_review_loop",
        "source_policy": "preserve_source_truth",
        "citation_policy": "preserve_citations",
        "requires_operator_review": 1,
    }


def test_finding_to_row_pins_advisory_policy() -> None:
    f = M.QualityFinding(finding_type="missing_citation", severity="warn", target_kind="action_stage",
                         target_id="s1", detail="d", advice="review it",
                         anchors={"stage_id": "s1", "stage_item_id": "i1"})
    row = f.to_row("run1", 0)
    assert row["action_policy"] == "no_execution"
    assert row["execution_policy"] == "evaluate_only"
    assert row["review_policy"] == "advisory_review_loop"
    assert row["requires_operator_review"] == 1
    assert row["stage_id"] == "s1" and row["stage_item_id"] == "i1"


def test_finding_row_has_no_disposition_field() -> None:
    f = M.QualityFinding(finding_type="policy_mismatch")
    row = f.to_row("run1", 0)
    for forbidden in ("accepted", "rejected", "deferred", "disposed", "repaired", "executed", "applied"):
        assert forbidden not in row


def test_finding_rejects_unknown_type() -> None:
    with pytest.raises(M.QualityValidationError):
        M.QualityFinding(finding_type="auto_repaired").to_row("r", 0)


def test_finding_rejects_unknown_severity() -> None:
    with pytest.raises(M.QualityValidationError):
        M.QualityFinding(finding_type="missing_citation", severity="fatal").to_row("r", 0)


def test_finding_detail_is_bounded() -> None:
    f = M.QualityFinding(finding_type="unbounded_payload_risk", detail="x" * 5000, advice="y" * 5000)
    row = f.to_row("r", 0)
    assert len(row["detail"]) <= M.DETAIL_HARD_CAP
    assert len(row["advice"]) <= M.ADVICE_HARD_CAP


def test_target_requires_target_id() -> None:
    with pytest.raises(M.QualityValidationError):
        M.QualityTarget(target_kind="feedback", target_id="").to_row("r", 0)


def test_target_rejects_unknown_kind() -> None:
    with pytest.raises(M.QualityValidationError):
        M.QualityTarget(target_kind="nope", target_id="x").to_row("r", 0)


def test_ids_are_deterministic_and_idempotent() -> None:
    args = ("feedback", "f1", "reqd", "inpd")
    assert M.compute_quality_run_id(*args) == M.compute_quality_run_id(*args)
    a = M.compute_finding_id("run", "missing_citation", "t", 0)
    b = M.compute_finding_id("run", "missing_citation", "t", 0)
    assert a == b and len(a) == 24


def test_target_digest_changes_with_signals() -> None:
    base = M.compute_target_digest("feedback", "f1", ["a", "b"])
    changed = M.compute_target_digest("feedback", "f1", ["a", "c"])
    assert base != changed


def test_input_digest_folds_target_digest() -> None:
    a = M.compute_input_digest("req", "tg1")
    b = M.compute_input_digest("req", "tg2")
    assert a != b


def test_severity_counts() -> None:
    rows = [{"severity": "risk"}, {"severity": "warn"}, {"severity": "warn"}, {"severity": "info"}]
    assert M.severity_counts(rows) == {"risk": 1, "warn": 2, "info": 1}
