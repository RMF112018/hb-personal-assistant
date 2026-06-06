"""Phase 09 Addendum — rendered daily-brief quality + guardrail proof tests."""

from __future__ import annotations

import re

from hb_assistant.construction.second_brain.daily_brief import rendered_quality as rq
from hb_assistant.construction.second_brain.daily_brief.rendered_quality import (
    _SAMPLE_RENDERED_BRIEF,
    build_daily_brief_rendered_quality_proof,
    validate_rendered_brief,
)

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)


def _packet():
    return rq._sample_packet()


def test_safe_rendered_brief_passes() -> None:
    result = validate_rendered_brief(_packet(), _SAMPLE_RENDERED_BRIEF)
    assert result["passed"] is True, [k for k, v in result["checks"].items() if not v]


def test_missing_advisory_notice_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF.replace(rq._ADVISORY_HEADER, "## Closing Notes")
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["advisory_notice_present"] is False
    assert result["passed"] is False


def test_missing_stale_warning_fails_when_packet_has_stale() -> None:
    packet = _packet()
    assert packet["stale_or_low_confidence_warnings"]  # precondition
    tampered = _SAMPLE_RENDERED_BRIEF.replace(
        rq._STALE_LINE, "All aging items are current."
    ).replace(rq._CONFIDENCE_LINE, "Confidence is adequate across the available items.")
    result = validate_rendered_brief(packet, tampered)
    assert result["checks"]["stale_low_confidence_warnings_present"] is False
    assert result["passed"] is False


def test_final_determination_language_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nDecision: we approve payment of the claim.\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_final_determinations"] is False
    assert result["passed"] is False


def test_raw_shaped_value_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nExport: https://example.com/raw\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_raw_shaped_values"] is False
    assert result["passed"] is False


def test_unsupported_claim_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nI updated Procore and the email was sent.\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_source_system_update_claims"] is False
    assert result["passed"] is False


def test_source_coverage_omission_fails_when_coverage_weak() -> None:
    packet = _packet()
    assert rq._is_weak_coverage(packet)  # precondition
    tampered = _SAMPLE_RENDERED_BRIEF.replace(
        rq._COVERAGE_LIMITATION_LINE, "Source coverage is complete and consistent."
    )
    result = validate_rendered_brief(packet, tampered)
    assert result["checks"]["coverage_limitations_not_omitted"] is False
    assert result["passed"] is False


def test_unsupported_source_family_fails() -> None:
    packet = _packet()
    # generated_outputs has no seeded data → not in families_present → unsupported if cited raw.
    assert "generated_outputs" not in packet["source_coverage_summary"]["families_present"]
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nDerived from generated_outputs.\n"
    result = validate_rendered_brief(packet, tampered)
    assert result["checks"]["no_unsupported_source_families"] is False
    assert result["passed"] is False


def test_proof_passes_and_writes_artifacts(tmp_path) -> None:
    proof = build_daily_brief_rendered_quality_proof(
        evidence_dir=str(tmp_path), write_evidence=True
    )
    assert proof["proof_passed"] is True
    assert proof["safe_fixture_passed"] is True
    for name, rep in proof["tampered_variants"].items():
        assert rep["expected_check_failed"] is True, name
        assert rep["overall_passed"] is False, name
    for fname in (
        "daily-brief-rendered-quality-proof.json",
        "daily-brief-rendered-quality-proof.md",
        "daily-brief-rendered-quality-fixture.md",
    ):
        assert (tmp_path / fname).exists(), fname
    assert not _SECRET_OR_URL.search(
        (tmp_path / "daily-brief-rendered-quality-proof.json").read_text()
    )
