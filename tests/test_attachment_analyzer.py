"""Phase 06 Prompt 08 — attachment analyzer (pure, metadata-only)."""

from __future__ import annotations

import pytest

from hb_assistant.construction.email.attachment_analyzer import (
    SENSITIVITY_KEYWORDS,
    analyze_attachment,
    detect_drive_links,
)

_PDF = "application/pdf"


def test_document_pdf_is_source_link_candidate() -> None:
    a = analyze_attachment("RFI 12 response.pdf", _PDF, is_inline=False)
    assert a.is_document is True
    assert a.source_link_candidate is True
    assert a.candidate_target_system == "sharepoint"
    assert a.sensitivity_hint is None
    assert a.review_required is False


def test_inline_image_is_not_a_candidate() -> None:
    a = analyze_attachment("logo.png", "image/png", is_inline=True)
    assert a.is_document is False
    assert a.source_link_candidate is False
    assert a.review_required is False


def test_url_attachment_is_link() -> None:
    a = analyze_attachment("Project Folder.url", "text/plain", is_inline=False)
    assert a.link_detected is True
    assert a.source_link_candidate is True


def test_onedrive_named_attachment_targets_onedrive() -> None:
    a = analyze_attachment("onedrive shortcut.url", "text/plain", is_inline=False)
    assert a.link_detected is True
    assert a.candidate_target_system == "onedrive"


@pytest.mark.parametrize(
    "name,expected_category",
    [
        ("Subcontract Agreement.pdf", "contracts"),
        ("Change Order 5.pdf", "change_orders"),
        ("Pay Application G702.pdf", "pay_applications"),
        ("Invoice 1042.pdf", "invoices"),
        ("Certificate of Insurance.pdf", "insurance_or_bonding"),
        ("Lien Waiver.pdf", "lien_releases"),
        ("Privileged and Confidential memo.docx", "privileged_or_confidential_markers"),
        ("Claim notice.pdf", "claims"),
        ("Injury report.pdf", "injuries"),
        ("Notice to Cure.pdf", "default_or_termination_language"),
    ],
)
def test_sensitive_filenames_route_to_review(name: str, expected_category: str) -> None:
    a = analyze_attachment(name, _PDF, is_inline=False)
    assert a.sensitivity_hint == expected_category
    assert a.sensitivity_level in ("high", "medium")
    assert a.review_required is True


def test_categories_match_package_set() -> None:
    # Every keyword category we use is a package sensitivity category name.
    package_categories = {
        "contracts", "change_orders", "claims", "notices", "legal_correspondence",
        "insurance_or_bonding", "pay_applications", "invoices", "lien_releases",
        "personnel_or_hr", "incidents", "injuries", "medical_detail", "disputes",
        "default_or_termination_language", "liquidated_damages",
        "delay_or_time_extension_language", "additional_compensation_language",
        "privileged_or_confidential_markers",
    }
    used = {c for c, _kw, _lvl in SENSITIVITY_KEYWORDS}
    assert used <= package_categories, f"unknown categories: {used - package_categories}"


def test_name_is_redacted_not_raw() -> None:
    a = analyze_attachment("Tropical RFI 23-435-01.pdf", _PDF, is_inline=False)
    assert a.name_redacted is not None
    assert "Tropical" not in a.name_redacted
    assert "23-435-01" not in a.name_redacted
    assert a.name_redacted.endswith(".pdf")  # extension retained (non-identifying)


def test_detect_drive_links_in_body_preview() -> None:
    assert detect_drive_links("doc at https://hbcc.sharepoint.com/sites/x/d.pdf") is not None
    assert detect_drive_links("see my onedrive folder") is not None
    assert detect_drive_links("lunch at noon") is None
    assert detect_drive_links(None) is None
