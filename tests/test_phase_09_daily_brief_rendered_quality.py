"""Phase 09 Addendum V2 — rendered daily-brief quality + guardrail proof tests (Prompt 03).

The rendered-output proof must FAIL when the executive brief carries internal proof/governance
commentary: packet provenance table, guardrail matrix, source-coverage wall, more than one advisory
disclaimer, a count-only schedule table without rows or a detail-unavailable notice, JSON blobs, final
determination language, or a source-system writeback claim.
"""

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


def test_required_sections_present() -> None:
    result = validate_rendered_brief(_packet(), _SAMPLE_RENDERED_BRIEF)
    assert result["checks"]["required_sections_present"] is True
    # Missing a required section fails.
    tampered = _SAMPLE_RENDERED_BRIEF.replace("## Focus", "## Wrap-Up")
    bad = validate_rendered_brief(_packet(), tampered)
    assert bad["checks"]["required_sections_present"] is False
    assert bad["passed"] is False


def test_packet_provenance_table_fails() -> None:
    tampered = (
        _SAMPLE_RENDERED_BRIEF
        + "\n\n## Provenance\n\n| packet_id | source_ref_hash |\n|---|---|\n| dbp_x | a1b2 |\n"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_provenance_table"] is False
    assert result["passed"] is False


def test_guardrail_matrix_fails() -> None:
    tampered = (
        _SAMPLE_RENDERED_BRIEF
        + "\n\n| guardrail | value |\n|---|---|\n| advisory_only | true |\n| no_writeback | true |\n"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_guardrail_matrix"] is False
    assert result["passed"] is False


def test_source_coverage_wall_fails() -> None:
    tampered = (
        _SAMPLE_RENDERED_BRIEF
        + "\n\n## Source Coverage and Confidence Notes\n\nsource_coverage_summary: families_present.\n"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_source_coverage_section"] is False
    assert result["passed"] is False


def test_more_than_one_disclaimer_fails() -> None:
    tampered = (
        _SAMPLE_RENDERED_BRIEF + "\n\n_This is an advisory brief and makes no determinations._\n"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["single_advisory_disclaimer"] is False
    assert result["passed"] is False


def test_count_only_schedule_table_fails() -> None:
    tampered = (
        _SAMPLE_RENDERED_BRIEF + "\n\n## Schedule\n\n257 critical-path activities are flagged.\n"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["schedule_detail_or_unavailable"] is False
    assert result["passed"] is False


def test_json_blob_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + '\n\n```json\n{"packet_version": "V2"}\n```\n'
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_json_blobs"] is False
    assert result["passed"] is False


def test_final_determination_language_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nDecision: we approve payment of the claim.\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_final_determinations"] is False
    assert result["passed"] is False


def test_source_system_writeback_claim_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nI updated Procore and the email was sent.\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_source_system_update_claims"] is False
    assert result["passed"] is False


def test_raw_shaped_value_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\nExport: https://example.com/raw\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["no_raw_shaped_values"] is False
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


# --- Prompt 05: new executive-utility checks ------------------------------------------------------

_NEW_CHECKS = (
    "brief_length_within_max",
    "agenda_today_or_none",
    "next_7_days_deadlines_or_none",
    "focus_count_in_range_or_none",
    "attention_counts_backed_or_unavailable",
)


def test_safe_fixture_satisfies_new_checks() -> None:
    result = validate_rendered_brief(_packet(), _SAMPLE_RENDERED_BRIEF)
    for key in _NEW_CHECKS:
        assert result["checks"][key] is True, key


def test_brief_length_over_max_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + ("\nfiller padding line." * 700)
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["brief_length_within_max"] is False
    assert result["passed"] is False


def _replace_section(brief: str, header: str, new_body: str, next_header: str) -> str:
    return re.sub(
        rf"{re.escape(header)}\n.*?\n{re.escape(next_header)}",
        f"{header}\n{new_body}{next_header}",
        brief,
        flags=re.DOTALL,
    )


def test_empty_today_section_fails_agenda() -> None:
    tampered = _replace_section(_SAMPLE_RENDERED_BRIEF, "## Today", "", "## Next 7 Days")
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["agenda_today_or_none"] is False
    assert result["passed"] is False


def test_today_states_none_passes_agenda() -> None:
    tampered = _replace_section(
        _SAMPLE_RENDERED_BRIEF, "## Today", "No calendar items present.\n\n", "## Next 7 Days"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["agenda_today_or_none"] is True


def test_empty_next_7_days_fails() -> None:
    tampered = _replace_section(_SAMPLE_RENDERED_BRIEF, "## Next 7 Days", "", "## Needs Attention")
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["next_7_days_deadlines_or_none"] is False
    assert result["passed"] is False


def test_focus_below_min_fails() -> None:
    tampered = _replace_section(
        _SAMPLE_RENDERED_BRIEF,
        "## Focus",
        "1. Do the one thing.\n2. Do the other thing.\n",
        "---",
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["focus_count_in_range_or_none"] is False
    assert result["passed"] is False


def test_focus_states_none_passes() -> None:
    tampered = _replace_section(
        _SAMPLE_RENDERED_BRIEF, "## Focus", "No focus items at this time.\n", "---"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["focus_count_in_range_or_none"] is True


def test_count_only_attention_line_fails() -> None:
    tampered = _SAMPLE_RENDERED_BRIEF + "\n\n## Backlog\n\n5 RFIs are outstanding this week.\n"
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["attention_counts_backed_or_unavailable"] is False
    assert result["passed"] is False


def test_count_with_detail_unavailable_passes_attention() -> None:
    tampered = (
        _SAMPLE_RENDERED_BRIEF
        + "\n\n## Backlog\n\n5 RFIs outstanding — detail unavailable; review the RFI log.\n"
    )
    result = validate_rendered_brief(_packet(), tampered)
    assert result["checks"]["attention_counts_backed_or_unavailable"] is True
