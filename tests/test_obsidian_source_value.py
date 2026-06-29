"""A1.11 PM Source Value classifier — disposition mapping, file-type policy, ordering."""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_value import (
    SourceValueDisposition as D,
)
from hb_assistant.obsidian_mcp.source_value import (
    classify_source_value,
)


@pytest.fixture
def config() -> ObsidianMcpConfig:
    return ObsidianMcpConfig.model_validate({"enabled": True})


def _cls(config, rel, ext, text=""):
    return classify_source_value({"rel_path": rel, "file_ext": ext, "text_excerpt": text}, config)


@pytest.mark.parametrize(
    "rel,ext,text,expected",
    [
        ("25-244/Change Orders/PCCO 014.pdf", "pdf", "", D.AUTO_CARD_HIGH),
        ("25-244/Dwg/A-312-WALL-SECTIONS.pdf", "pdf", "", D.AUTO_CARD_HIGH),
        ("25-244/Bid/WLP Bid Package 03.docx", "docx", "bid package", D.AUTO_CARD_HIGH),
        ("25-244/PayApps/Pay App 12.xlsx", "xlsx", "payment application", D.AUTO_CARD_HIGH),
        ("25-244/Cost/Cost Report June.xlsx", "xlsx", "cost report", D.AUTO_CARD_HIGH),
        ("25-244/Misc/Generic Tracker.xlsx", "xlsx", "random data", D.METADATA_ONLY),
        ("25-244/Marketing/WLP Project Overview.pdf", "pdf", "marketing brochure", D.AUTO_CARD_NORMAL),
        ("HB INSURANCE RENEWALS/2026/GL.pdf", "pdf", "", D.DEFERRED),
        ("clients/COI/cert.pdf", "pdf", "", D.DEFERRED),
        ("links/Portal.url", "url", "", D.UNSUPPORTED),
        ("web/SharePoint.aspx", "aspx", "", D.UNSUPPORTED),
        ("screens/Screenshot.png", "png", "", D.UNSUPPORTED),
        ("node_modules/pkg/readme.md", "md", "", D.EXCLUDED),
    ],
)
def test_disposition_mapping(config, rel, ext, text, expected):
    assert _cls(config, rel, ext, text).disposition is expected


def test_screenshot_never_auto_cards(config):
    sv = _cls(config, "screens/Screenshot 2026.png", "png")
    assert sv.disposition is D.UNSUPPORTED
    assert sv.allow_auto_card is False
    assert sv.allow_metadata_index is False  # not indexed (skipped before indexing)
    assert sv.skip_code == "unsupported_file_type"


def test_uppercase_and_dotted_ext_normalize(config):
    for ext in ("PNG", ".png", ".PNG", "png"):
        assert _cls(config, "a/Shot.png", ext).disposition is D.UNSUPPORTED


def test_bare_cost_xlsx_not_promoted(config):
    # "cost" alone (not "cost report"/"cost entries") must NOT promote a generic workbook to high.
    assert _cls(config, "a/Cost.xlsx", "xlsx", "cost").disposition is D.METADATA_ONLY


def test_coi_segment_equality_not_substring(config):
    # A folder merely CONTAINING "coi" (e.g. 'COImaging') must NOT be deferred; an exact COI segment is.
    assert _cls(config, "ProjectX/COImaging/photo.pdf", "pdf").disposition is not D.DEFERRED
    assert _cls(config, "ProjectX/COI/cert.pdf", "pdf").disposition is D.DEFERRED


def test_deferred_allows_metadata_index_and_manual_override(config):
    sv = _cls(config, "HB INSURANCE RENEWALS/x.pdf", "pdf")
    assert sv.disposition is D.DEFERRED
    assert sv.allow_auto_card is False
    assert sv.allow_metadata_index is True  # searchable; manual generate may still override


def test_metadata_only_auto_card_opt_in(config):
    base = {"rel_path": "a/Generic.xlsx", "file_ext": "xlsx", "text_excerpt": ""}
    assert classify_source_value(base, config).allow_auto_card is False
    on = ObsidianMcpConfig.model_validate({"enabled": True, "source_card_auto_metadata_only_enabled": True})
    assert classify_source_value(base, on).allow_auto_card is True


def test_priority_high_before_normal_before_metadata(config):
    high = _cls(config, "a/A-312-PLAN.pdf", "pdf").priority_score
    normal = _cls(config, "a/Marketing Deck.pdf", "pdf", "presentation").priority_score
    meta = _cls(config, "a/Generic.xlsx", "xlsx").priority_score
    assert high < normal < meta


def test_high_path_signal_promotes(config):
    # A weak doc-type under a 'Pay Apps' folder is promoted by the high path signal.
    sv = _cls(config, "25-244/03 Pay Applications/scan.pdf", "pdf", "")
    assert sv.disposition is D.AUTO_CARD_HIGH
    assert "high_path_signal" in sv.reasons
