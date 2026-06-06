"""Phase 09 Addendum V2 — daily-brief executive-quality golden-fixture proof tests (Prompt 05).

Golden fixture A (full detail) and B (detail unavailable) must pass every executive-utility check; the
unsafe/internal fixture C must be rejected. Rendered text is never imported into trusted surfaces.
"""

from __future__ import annotations

import re

from hb_assistant.construction.second_brain.daily_brief.rendered_quality import (
    _GOLDEN_DETAIL_UNAVAILABLE,
    _GOLDEN_FULL_DETAIL,
    _GOLDEN_REJECTED_INTERNAL,
    build_daily_brief_v2_quality_proof,
    validate_rendered_brief,
)

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)


def test_golden_full_detail_passes() -> None:
    result = validate_rendered_brief({}, _GOLDEN_FULL_DETAIL)
    assert result["passed"] is True, [k for k, v in result["checks"].items() if not v]


def test_golden_detail_unavailable_passes() -> None:
    result = validate_rendered_brief({}, _GOLDEN_DETAIL_UNAVAILABLE)
    assert result["passed"] is True, [k for k, v in result["checks"].items() if not v]


def test_golden_rejected_internal_fails() -> None:
    result = validate_rendered_brief({}, _GOLDEN_REJECTED_INTERNAL)
    assert result["passed"] is False
    failing = {k for k, v in result["checks"].items() if not v}
    # The internal/unsafe fixture trips governance + determination checks.
    assert {
        "no_provenance_table",
        "no_guardrail_matrix",
        "no_source_coverage_section",
        "no_final_determinations",
    } <= failing


def test_synthetic_raw_value_is_rejected() -> None:
    # Raw-shaped rejection is verified with an in-memory synthetic token (never persisted to evidence).
    synthetic = _GOLDEN_REJECTED_INTERNAL + "\n\nToken: Bearer abc123def456\n"
    result = validate_rendered_brief({}, synthetic)
    assert result["checks"]["no_raw_shaped_values"] is False


def test_v2_quality_proof_passes_and_writes_artifacts(tmp_path) -> None:
    proof = build_daily_brief_v2_quality_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert proof["proof_passed"] is True
    assert proof["fixtures"]["full_detail"]["passed"] is True
    assert proof["fixtures"]["detail_unavailable"]["passed"] is True
    assert proof["fixtures"]["rejected_internal"]["passed"] is False
    for fname in (
        "daily-brief-v2-quality-proof.json",
        "daily-brief-v2-quality-proof.md",
        "daily-brief-v2-golden-full-detail.md",
        "daily-brief-v2-golden-detail-unavailable.md",
        "daily-brief-v2-golden-rejected-internal.md",
    ):
        assert (tmp_path / fname).exists(), fname
    blob = (tmp_path / "daily-brief-v2-quality-proof.json").read_text()
    assert not _SECRET_OR_URL.search(blob)
    # No raw-shaped values in any golden fixture evidence file.
    for fname in (
        "daily-brief-v2-golden-full-detail.md",
        "daily-brief-v2-golden-detail-unavailable.md",
        "daily-brief-v2-golden-rejected-internal.md",
    ):
        assert not _SECRET_OR_URL.search((tmp_path / fname).read_text())
