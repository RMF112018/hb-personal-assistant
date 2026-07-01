"""Phase 15 schedule identity trust read model tests."""

from __future__ import annotations

import json

import pytest

from hb_assistant.construction.analytics.project_schedule_analytics_trust_service import (
    build_analytics_trust_ledger,
    resolve_analytics_trust_status,
)
from hb_assistant.construction.analytics.project_schedule_identity_trust_service import (
    assert_pm_identity_payload_redacted,
    build_identity_trust_from_committed,
    build_identity_trust_from_hub,
    build_identity_trust_from_preview,
    map_identity_gate,
    pm_identity_trust_payload,
)
from hb_assistant.store.project_schedule_hub_repository import MEMBERSHIP_EXCLUDED, MEMBERSHIP_PENDING


def test_trusted_identity_gate_ready() -> None:
    payload = build_identity_trust_from_committed(
        project_key="tropical",
        project_display_name="Tropical Wind",
        schedule_label="TWNU19",
        identity_match={"match_status": "resolved", "requires_review": 0},
        membership={"membership_status": "accepted"},
    )
    assert payload["identity_trust_status"] == "trusted"
    assert payload["identity_gate"] == "ready"
    assert payload["review_required"] is False
    assert assert_pm_identity_payload_redacted(payload) == []


def test_ambiguous_identity_is_degraded_gate() -> None:
    payload = build_identity_trust_from_committed(
        project_key="tropical",
        project_display_name="Tropical Wind",
        schedule_label="TWNU19",
        identity_match={"match_status": "ambiguous", "candidate_count": 2, "requires_review": 1},
        membership={"membership_status": "pending_review"},
    )
    assert payload["identity_trust_status"] == "ambiguous"
    assert map_identity_gate(identity_trust_status="ambiguous") == "degraded"


def test_project_mismatch_preview_blocks_gate() -> None:
    payload = build_identity_trust_from_preview(
        preview={"schedule_name": "Demo", "activity_count": 10},
        trust_preview={
            "warnings": [
                {
                    "code": "source_project_mismatch",
                    "message": "Source project ID in the file does not match the linked project record.",
                }
            ]
        },
        project_display_name="Tropical Wind",
    )
    assert payload["identity_trust_status"] == "mismatch"
    assert payload["identity_gate"] == "blocked"


def test_excluded_membership_is_blocked() -> None:
    payload = build_identity_trust_from_hub(
        project_display_name="Tropical Wind",
        schedule_trust={"status": "excluded", "review_reasons": ["excluded_from_series"]},
        identity_review={"status": "excluded"},
        current_schedule={"friendly_label": "TWNU19", "data_date": "2026-06-23"},
        identity_match={"requires_review": 0},
        membership={"membership_status": MEMBERSHIP_EXCLUDED},
    )
    assert payload["identity_trust_status"] == "blocked"
    assert payload["identity_gate"] == "blocked"


def test_cpm_ready_identity_blocked_forces_analytics_blocked() -> None:
    identity = pm_identity_trust_payload(
        identity_trust_status="blocked",
        identity_gate="blocked",
        review_required=True,
        operator_action_required=True,
        safe_project_label="Tropical Wind",
        safe_schedule_label="TWNU19",
        safe_reasons=["Series excluded."],
        recommended_operator_actions=["Resolve identity review."],
        pm_message="Blocked.",
        technical_identity={"membership_status": MEMBERSHIP_EXCLUDED},
    )
    status = resolve_analytics_trust_status(
        phase="hub",
        quality_status="complete",
        cpm_status="complete",
        identity_status="partial",
        identity_membership_status=MEMBERSHIP_EXCLUDED,
        identity_gate="blocked",
    )
    assert status == "blocked"
    ledger = build_analytics_trust_ledger(
        phase="hub",
        quality_status="complete",
        cpm_status="complete",
        identity_status="complete",
        identity_membership_status="accepted",
        identity_trust=identity,
    )
    assert ledger["analytics_trust_status"] == "blocked"


@pytest.mark.parametrize(
    ("identity_trust_status", "expected_gate"),
    [
        ("trusted", "ready"),
        ("review_required", "degraded"),
        ("ambiguous", "degraded"),
        ("mismatch", "blocked"),
        ("blocked", "blocked"),
        ("unavailable", "degraded"),
    ],
)
def test_identity_gate_mapping(identity_trust_status: str, expected_gate: str) -> None:
    assert map_identity_gate(identity_trust_status=identity_trust_status) == expected_gate


def test_default_payload_has_no_forbidden_identity_keys() -> None:
    payload = build_identity_trust_from_preview(
        preview={"schedule_name": "Demo", "source_filename": "demo.xer"},
        trust_preview={"warnings": [{"code": "identity_requires_review", "message": "Review identity."}]},
    )
    serialized = json.dumps(payload)
    for forbidden in ("schedule_version_key", "import_id", "package_id", "schedule_identity_key"):
        assert forbidden not in serialized
