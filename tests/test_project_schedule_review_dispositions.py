"""Phase 17 review disposition taxonomy tests."""

from __future__ import annotations

import pytest

from hb_assistant.construction.analytics.project_schedule_review_disposition import (
    DISPOSITION_ACCEPTED_FOR_FOLLOW_UP,
    DISPOSITION_BLOCKED_BY_IDENTITY,
    DISPOSITION_NEEDS_REVIEW,
    DISPOSITION_PM_LABELS,
    OPERATOR_SELECTABLE_DISPOSITIONS,
    enrich_item_disposition_pm_fields,
    normalize_disposition,
    validate_disposition_change,
)


def test_normalize_accepts_legacy_aliases() -> None:
    assert normalize_disposition("open") == DISPOSITION_NEEDS_REVIEW
    assert normalize_disposition("reviewed") == DISPOSITION_ACCEPTED_FOR_FOLLOW_UP
    assert normalize_disposition("dismissed") == "dismissed_not_material"


def test_unknown_disposition_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_review_status"):
        normalize_disposition("ready")


def test_pm_labels_safe_and_no_forbidden_terms() -> None:
    forbidden = ("claim", "liability", "fault", "compensable", "entitlement", "causation")
    for meta in DISPOSITION_PM_LABELS.values():
        combined = f"{meta['label']} {meta['pm_description']}".lower()
        for term in forbidden:
            assert term not in combined


def test_operator_cannot_select_blocked_dispositions() -> None:
    with pytest.raises(ValueError, match="operator_disposition_not_allowed"):
        validate_disposition_change(
            prior_disposition=DISPOSITION_NEEDS_REVIEW,
            new_disposition=DISPOSITION_BLOCKED_BY_IDENTITY,
            disposition_reason=None,
        )


def test_reason_required_for_dismiss() -> None:
    with pytest.raises(ValueError, match="disposition_reason_required"):
        validate_disposition_change(
            prior_disposition=DISPOSITION_NEEDS_REVIEW,
            new_disposition="dismissed_not_material",
            disposition_reason="",
        )


def test_public_item_enrichment_redacts_internal_keys() -> None:
    from hb_assistant.construction.analytics.project_schedule_review_service import (
        ProjectScheduleReviewService,
    )

    item = ProjectScheduleReviewService._public_item(
        {
            "review_item_id": "psri-abc",
            "review_status": "needs_review",
            "schedule_version_key": "secret|key",
            "project_key": "tropical",
            "evidence": {},
        }
    )
    assert "schedule_version_key" not in item
    assert item["disposition_label"] == "Needs review"
    assert item["is_persisted"] is True


def test_operator_selectable_excludes_system_dispositions() -> None:
    assert DISPOSITION_BLOCKED_BY_IDENTITY not in OPERATOR_SELECTABLE_DISPOSITIONS
