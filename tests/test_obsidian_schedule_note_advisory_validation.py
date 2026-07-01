"""Tests for schedule_note_advisory_validation."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.schedule_note_advisory_validation import validate_schedule_advisory


def _payload() -> dict:
    return {
        "analytics_trust_status": "degraded",
        "identity_trust_status": "trusted",
        "cpm_trust_status": "degraded",
        "quality_trust_status": "unavailable",
    }


def _safe_advisory() -> str:
    return (
        "### Summary\nAdvisory summary for PM review.\n\n"
        "### PM Attention\n- Review trust posture before disposition.\n\n"
        "### Follow-Up Questions\n- Are milestone movements material?\n\n"
        "### Limits / Uncertainty\n- Advisory only; verify against schedule surfaces.\n"
    )


def test_validate_schedule_advisory_accepts_safe_output() -> None:
    result = validate_schedule_advisory(_safe_advisory(), payload=_payload())
    assert result["passed"] is True


def test_validate_schedule_advisory_rejects_causation_language() -> None:
    bad = _safe_advisory().replace("Review", "This caused delay damages")
    result = validate_schedule_advisory(bad, payload=_payload())
    assert result["passed"] is False


def test_validate_schedule_advisory_rejects_raw_ids() -> None:
    bad = _safe_advisory() + "\nimport_id=abc\n"
    result = validate_schedule_advisory(bad, payload=_payload())
    assert result["passed"] is False
