"""Phase 06 Prompt 10 — sensitive review-category registry.

Proves the 23-category registry covers the package-required ids, reproduces the 19
legacy attachment categories exactly (ids/levels/keywords), routes each category by
trigger term, and stays in sync with the resources JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.email.attachment_analyzer import SENSITIVITY_KEYWORDS
from hb_assistant.construction.email.review_categories import (
    REVIEW_CATEGORIES,
    REVIEW_CATEGORIES_BY_ID,
    classify_review_categories,
)

_ROOT = Path(__file__).resolve().parents[1]

# The full set the Phase 06 package requires (19 legacy + 4 Prompt 10 additions).
_REQUIRED_IDS = {
    "contracts", "change_orders", "claims", "notices", "legal_correspondence",
    "insurance_or_bonding", "pay_applications", "invoices", "lien_releases",
    "personnel_or_hr", "incidents", "injuries", "medical_detail", "disputes",
    "default_or_termination_language", "liquidated_damages",
    "delay_or_time_extension_language", "additional_compensation_language",
    "privileged_or_confidential_markers", "confidential_bid_or_estimate",
    "owner_directive", "subcontractor_default", "schedule_recovery_or_acceleration",
}


def test_registry_covers_all_required_categories() -> None:
    ids = {c.id for c in REVIEW_CATEGORIES}
    assert ids == _REQUIRED_IDS
    assert len(REVIEW_CATEGORIES) == 23
    assert len(REVIEW_CATEGORIES_BY_ID) == 23  # ids are unique


def test_preserves_legacy_attachment_categories_exactly() -> None:
    legacy = {cid: (kw, level) for cid, kw, level in SENSITIVITY_KEYWORDS}
    for cid, (keywords, level) in legacy.items():
        cat = REVIEW_CATEGORIES_BY_ID[cid]
        assert cat.trigger_terms == keywords, f"{cid} keywords drifted"
        assert cat.sensitivity_level == level, f"{cid} level drifted"


def test_every_category_routes_by_trigger_term() -> None:
    for cat in REVIEW_CATEGORIES:
        sample = f"prefix {cat.trigger_terms[0]} suffix"
        assert cat.id in classify_review_categories(sample), f"{cat.id} did not route"


def test_classify_handles_empty_and_multiple() -> None:
    assert classify_review_categories(None) == []
    assert classify_review_categories("") == []
    hits = classify_review_categories("this invoice references a change order and a lien waiver")
    assert {"invoices", "change_orders", "lien_releases"}.issubset(set(hits))


def test_every_category_permits_encrypted_capture_but_requires_review_first() -> None:
    # Policy posture: encryption permitted, review precedes body-derived conclusions.
    for cat in REVIEW_CATEGORIES:
        assert cat.encrypted_body_capture_allowed is True
        assert cat.encrypted_body_capture_requires_review_first is True
        assert cat.sensitivity_level in ("high", "medium")
        assert cat.evidence_safe_explanation


def test_resources_json_matches_module() -> None:
    path = _ROOT / "resources/config/email_sensitivity_review_categories.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in data["categories"]}
    assert set(by_id) == {c.id for c in REVIEW_CATEGORIES}
    for cat in REVIEW_CATEGORIES:
        row = by_id[cat.id]
        assert tuple(row["trigger_terms"]) == cat.trigger_terms
        assert row["sensitivity_level"] == cat.sensitivity_level
        assert row["encrypted_body_capture_allowed"] == cat.encrypted_body_capture_allowed
        assert (
            row["encrypted_body_capture_requires_review_first"]
            == cat.encrypted_body_capture_requires_review_first
        )
