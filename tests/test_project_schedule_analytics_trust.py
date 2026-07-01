"""Tests for analytics_trust_status gate rules (Phase 14)."""

from __future__ import annotations

import pytest

from hb_assistant.construction.analytics.project_schedule_analytics_trust_service import (
    build_analytics_trust_ledger,
    resolve_analytics_trust_status,
)
from hb_assistant.construction.analytics.schedule_cpm_trust import (
    public_cpm_trust_fields,
    redact_cpm_failure_message,
)
from hb_assistant.store.project_schedule_hub_repository import MEMBERSHIP_EXCLUDED


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"phase": "preview", "parse_status": "failed"}, "blocked"),
        ({"phase": "preview", "supersede_blocked": True}, "blocked"),
        ({"phase": "preview", "parse_status": "complete"}, "ready"),
        (
            {
                "phase": "preview",
                "trust_warnings": [{"code": "low_activity_overlap", "message": "Review identity."}],
            },
            "degraded",
        ),
        ({"phase": "committed", "cpm_status": "failed"}, "blocked"),
        ({"phase": "committed", "quality_status": "failed"}, "blocked"),
        (
            {"phase": "hub", "identity_membership_status": MEMBERSHIP_EXCLUDED},
            "blocked",
        ),
        (
            {
                "phase": "hub",
                "cpm_status": "partial",
                "quality_status": "complete",
                "identity_status": "complete",
            },
            "degraded",
        ),
        (
            {
                "phase": "hub",
                "cpm_status": "complete",
                "quality_status": "complete",
                "identity_status": "complete",
            },
            "ready",
        ),
    ],
)
def test_resolve_analytics_trust_status_gate_rules(kwargs: dict, expected: str) -> None:
    assert resolve_analytics_trust_status(**kwargs) == expected


def test_cpm_failure_message_is_redacted_not_raw() -> None:
    redacted = redact_cpm_failure_message(
        failure_code="cpm_chain_failed",
        failed_step="forward_pass",
        raw_message="RuntimeError: synthetic forward-pass failure with secret/path",
    )
    assert redacted is not None
    assert "RuntimeError" not in redacted
    assert "synthetic" not in redacted
    assert "forward pass" in redacted.lower()


def test_public_cpm_trust_fields_omit_raw_failure_message() -> None:
    fields = public_cpm_trust_fields(
        observability={
            "status": "failed",
            "failure_code": "cpm_chain_failed",
            "failure_message": "RuntimeError: raw operator detail",
            "failed_step": "forward_pass",
        },
        cpm_recompute_status="failed",
    )
    assert fields["failure_message_redacted"]
    assert "RuntimeError" not in str(fields)
    assert "failure_message" not in fields


def test_build_analytics_trust_ledger_includes_capability_limitation_not_defect() -> None:
    ledger = build_analytics_trust_ledger(
        phase="hub",
        cpm_status="complete",
        quality_status="complete",
        identity_status="complete",
    )
    joined = " ".join(ledger.get("capability_limitations") or [])
    assert "Out-of-sequence progress analysis is not implemented" in joined
    assert "research_not_implemented" not in joined


def test_build_analytics_trust_ledger_surfaces_ignored_companion_files() -> None:
    ledger = build_analytics_trust_ledger(
        phase="preview",
        ignored_companion_files=[
            {"filename": "report.html", "reason": "unsupported HTML companion ignored"},
        ],
    )
    assert any("report.html" in reason for reason in ledger["trust_reasons"])


def test_identity_gate_blocked_overrides_ready_cpm_and_quality() -> None:
    assert (
        resolve_analytics_trust_status(
            phase="hub",
            cpm_status="complete",
            quality_status="complete",
            identity_status="complete",
            identity_membership_status="accepted",
            identity_gate="blocked",
        )
        == "blocked"
    )


def test_identity_gate_degraded_caps_ready_even_when_other_gates_pass() -> None:
    assert (
        resolve_analytics_trust_status(
            phase="hub",
            cpm_status="complete",
            quality_status="complete",
            identity_status="complete",
            identity_membership_status="accepted",
            identity_gate="degraded",
        )
        == "degraded"
    )


def test_preview_source_project_mismatch_blocks_analytics() -> None:
    assert (
        resolve_analytics_trust_status(
            phase="preview",
            parse_status="complete",
            trust_warnings=[
                {
                    "code": "source_project_mismatch",
                    "message": "Source project ID in the file does not match the linked project record.",
                }
            ],
        )
        == "blocked"
    )
