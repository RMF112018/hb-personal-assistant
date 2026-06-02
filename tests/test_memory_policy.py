"""Phase 08A Prompt 10 — memory + operator-preference policy."""

from __future__ import annotations

import pytest

from hb_assistant.construction.second_brain.memory import (
    apply_operator_preferences,
    classify_memory_tier,
    classify_preference,
    sensitive_high_impact_categories,
    validate_memory_policy,
)


def test_sensitive_categories_include_high_impact() -> None:
    cats = sensitive_high_impact_categories()
    for c in ("legal", "contractual", "claim", "personnel", "safety", "financial", "entitlement"):
        assert c in cats


@pytest.mark.parametrize("category", ["legal", "financial", "personnel", "safety", "claim"])
def test_sensitive_memory_routes_tier_3(category: str) -> None:
    tier, reason = classify_memory_tier(
        sensitivity_category=category, confidence_class="high", source_linked=True
    )
    assert tier == 3
    assert reason == "T3_SENSITIVE_HIGH_IMPACT"


def test_high_confidence_source_backed_is_tier_1() -> None:
    tier, reason = classify_memory_tier(
        sensitivity_category=None, confidence_class="high", source_linked=True
    )
    assert tier == 1
    assert reason == "T1_DETERMINISTIC_SOURCE_BACKED"


def test_unsupported_and_model_only_and_conflict_are_tier_3() -> None:
    assert classify_memory_tier(sensitivity_category=None, confidence_class="high", source_linked=False)[0] == 3
    assert classify_memory_tier(sensitivity_category=None, confidence_class="high", source_linked=True, model_only=True)[0] == 3
    assert classify_memory_tier(sensitivity_category=None, confidence_class="high", source_linked=True, conflict=True)[0] == 3


def test_medium_confidence_is_tier_2() -> None:
    tier, _ = classify_memory_tier(
        sensitivity_category=None, confidence_class="medium", source_linked=True
    )
    assert tier == 2


def test_sensitive_preference_routes_tier_3_and_never_auto_accepted() -> None:
    tier, reason, status = classify_preference(preference_type="personnel", sensitive=True)
    assert tier == 3
    assert status == "pending_review"
    # Low-risk presentation preference is Tier 2, still pending review.
    tier2, _, status2 = classify_preference(preference_type="detail_level")
    assert tier2 == 2
    assert status2 == "pending_review"


def test_accepted_preferences_cannot_override_safety() -> None:
    applied, dropped = apply_operator_preferences(
        [
            {"preference_key": "detail_level", "preference_value_redacted": "concise", "review_status": "accepted"},
            {"preference_key": "review_tier_override", "preference_value_redacted": "tier_1", "review_status": "accepted"},
            {"preference_key": "suppress_warnings", "preference_value_redacted": "true", "review_status": "accepted"},
            {"preference_key": "disable_high_impact_review", "preference_value_redacted": "1", "review_status": "accepted"},
            {"preference_key": "terminology", "preference_value_redacted": "RFI", "review_status": "pending_review"},
        ]
    )
    assert applied == {"detail_level": "concise"}
    assert any("review_tier_override" in d for d in dropped)
    assert any("suppress_warnings" in d for d in dropped)
    assert any("disable_high_impact_review" in d for d in dropped)
    assert any("terminology" in d for d in dropped)  # not accepted


def test_validate_memory_policy_clean() -> None:
    v = validate_memory_policy()
    assert v["valid"] is True, v["violations"]
