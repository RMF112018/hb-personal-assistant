"""PM-grade source-card taxonomy + deterministic extraction (Phase 4). Synthetic fixtures only."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp import source_analyzers, source_notes
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_value import (
    HIGH_DOCUMENT_TYPES,
    SourceValueDisposition,
    classify_source_value,
    derive_confidence,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _analyze(rel_path: str, ext: str = "pdf", text: str = ""):
    return source_analyzers.from_detail({"rel_path": rel_path, "file_ext": ext, "text_excerpt": text})


# (filename, ext, expected document_type) — synthetic, no real project data.
_CASES = [
    ("25-123-01 - PCCO 004 - Added Lobby Millwork.pdf", "pdf", "change_order"),
    ("25-123-01 COR 011 - Owner Requested Change.pdf", "pdf", "potential_change_order"),
    ("25-123-01 Pay Application 07 - ABC Concrete.xlsx", "xlsx", "pay_application"),
    ("25-123-01 Subcontract - MEP Prime.pdf", "pdf", "subcontract"),
    ("25-123-01 Purchase Order 100245 - Steel Supply.pdf", "pdf", "purchase_order"),
    ("25-123-01 RFI 032 - Door Hardware Conflict.pdf", "pdf", "rfi"),
    ("25-123-01 Submittal 05 51 00 Metal Stairs.pdf", "pdf", "submittal"),
    ("25-123-01 OAC Meeting Minutes 2026-06-15.pdf", "pdf", "meeting_minutes"),
    ("25-123-01 Baseline Schedule Update 04.xer", "xer", "schedule"),
    ("25-123-01 Specifications Div 08 Openings.pdf", "pdf", "specification"),
    ("25-123-01 A201 Floor Plan.pdf", "pdf", "drawing"),
    ("25-123-01 GMP Bid Package 03 Concrete.pdf", "pdf", "bid_package"),
    ("25-123-01 Daily Log 2026-06-15.pdf", "pdf", "daily_log"),
    ("25-123-01 Manpower Log 2026-06-15.pdf", "pdf", "manpower_log"),
    ("25-123-01 Cost Report June 2026.xlsx", "xlsx", "cost_report"),
    ("25-123-01 Closeout O and M Manuals.pdf", "pdf", "operations_maintenance"),
    ("25-123-01 Warranty - Roofing 20yr.pdf", "pdf", "warranty"),
    ("25-123-01 Punch List Area B.pdf", "pdf", "punch_list"),
    ("25-123-01 Safety Inspection 2026-06-15.pdf", "pdf", "safety"),
    ("25-123-01 Special Inspection Report.pdf", "pdf", "inspection"),
    ("25-123-01 Quality NCR 005.pdf", "pdf", "quality"),
]


def test_synthetic_documents_classify_to_expected_type() -> None:
    for name, ext, expected in _CASES:
        a = _analyze(name, ext)
        assert a.document_type == expected, f"{name} -> {a.document_type} (expected {expected})"


def test_high_value_types_are_auto_card() -> None:
    cfg = ObsidianMcpConfig()
    for name, ext, expected in _CASES:
        assert expected in HIGH_DOCUMENT_TYPES, expected
        sv = classify_source_value({"rel_path": name, "file_ext": ext, "text_excerpt": ""}, cfg)
        assert sv.disposition is SourceValueDisposition.AUTO_CARD_HIGH, f"{name} -> {sv.disposition}"
        assert sv.allow_auto_card is True


def test_generic_spreadsheet_stays_metadata_only() -> None:
    cfg = ObsidianMcpConfig()
    sv = classify_source_value(
        {"rel_path": "25-123-01 Misc Tracker.xlsx", "file_ext": "xlsx", "text_excerpt": "A | B"}, cfg)
    assert sv.disposition is SourceValueDisposition.METADATA_ONLY


def test_pm_critical_spreadsheet_promotes_only_with_evidence() -> None:
    cfg = ObsidianMcpConfig()
    # "Cost Report" filename → cost_report (HIGH); bare "cost" stays metadata-only.
    hi = classify_source_value(
        {"rel_path": "25-123-01 Cost Report June.xlsx", "file_ext": "xlsx", "text_excerpt": ""}, cfg)
    lo = classify_source_value(
        {"rel_path": "25-123-01 costs.xlsx", "file_ext": "xlsx", "text_excerpt": "cost\n"}, cfg)
    assert hi.disposition is SourceValueDisposition.AUTO_CARD_HIGH
    assert lo.disposition is SourceValueDisposition.METADATA_ONLY


def test_deterministic_field_extraction() -> None:
    a = _analyze("25-123-01 - PCCO 004 - Added Lobby Millwork.pdf")
    assert a.document_number == "004" and a.title == "Added Lobby Millwork"
    rfi = _analyze("25-123-01 RFI 032 - Door Hardware Conflict.pdf")
    assert rfi.document_number == "032" and rfi.title == "Door Hardware Conflict"
    pay = _analyze("25-123-01 Pay Application 07 - ABC Concrete.xlsx", "xlsx")
    assert pay.document_number == "07" and pay.vendor == "ABC Concrete"
    sub = _analyze("25-123-01 Subcontract - MEP Prime.pdf")
    assert sub.vendor == "MEP Prime"
    po = _analyze("25-123-01 Purchase Order 100245 - Steel Supply.pdf")
    assert po.document_number == "100245" and po.vendor == "Steel Supply"
    daily = _analyze("25-123-01 Daily Log 2026-06-15.pdf")
    assert daily.doc_date == "2026-06-15"


def test_amount_status_only_when_explicit() -> None:
    # No explicit $ or status in the filename → fields stay None (never invented).
    bare = _analyze("25-123-01 - PCCO 004 - Added Lobby Millwork.pdf")
    assert bare.amount is None and bare.doc_status is None
    # Explicit $ and status in the excerpt → extracted.
    rich = _analyze("25-123-01 - PCCO 005 - HVAC.pdf", "pdf",
                    "This change order is APPROVED for the amount of $12,500.00 total.")
    assert rich.amount == "$12,500.00" and rich.doc_status == "approved"


def test_punchlist_backward_compatible() -> None:
    # New canonical spelling classifies as punch_list...
    assert _analyze("25-123-01 Punch List Area B.pdf").document_type == "punch_list"
    # ...and BOTH spellings remain recognized high-value (legacy data not orphaned).
    assert "punch_list" in HIGH_DOCUMENT_TYPES
    assert "punchlist" in HIGH_DOCUMENT_TYPES


def _env(tmp_path: Path):
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    root = tmp_path / "proj"
    (root / "25-123-01").mkdir(parents=True, exist_ok=True)
    cfg = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_sources": [{"source_root_key": "syn-work", "path": str(root), "enabled": True}],
    })
    return SourceIndexRepository(db), cfg, root


def test_card_has_pm_sections_and_frontmatter(tmp_path: Path) -> None:
    _repo, cfg, _root = _env(tmp_path)
    detail = {
        "source_id": "s1", "source_kind": "external_file",
        "rel_path": "25-123-01/RFI 032 - Door Hardware Conflict.pdf",
        "source_root_key": "syn-work", "file_ext": "pdf",
        "text_excerpt": "Request for Information RFI #032 regarding door hardware.",
        "project_number": "25-123-01", "content_sha256": "abc", "indexed_at": "2026-06-30",
    }
    md = source_notes._render_card(cfg, detail, "2026-06-30T00:00:00Z")
    for section in ("## Why This Matters", "## PM Review Cues", "## Source Basis", "## Follow-Up"):
        assert section in md, section
    for fm in ('document_type: "rfi"', "domain: \"work\"", "source_disposition:",
               "source_confidence:", "review_status:", 'template_version: "source-card-v1"',
               "card_version:"):
        assert fm in md, fm
    # Deterministic confidence, not model-derived; advisory summary absent on the deterministic card.
    assert "## AI Summary" not in md and "## AI PM Summary" not in md


def test_confidence_and_review_status_deterministic() -> None:
    cfg = ObsidianMcpConfig()
    high = classify_source_value(
        {"rel_path": "25-123-01 RFI 032.pdf", "file_ext": "pdf", "text_excerpt": "RFI #032"}, cfg)
    assert derive_confidence(high) == "high"
    # An ambiguous general PDF → NORMAL/medium but card review_status should be needs_review.
    amb = classify_source_value(
        {"rel_path": "25-123-01 Some Notes.pdf", "file_ext": "pdf", "text_excerpt": "misc notes"}, cfg)
    assert amb.disposition is SourceValueDisposition.AUTO_CARD_NORMAL
    assert derive_confidence(amb) == "medium"
