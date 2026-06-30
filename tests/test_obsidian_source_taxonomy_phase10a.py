"""Phase 10A — source taxonomy/disposition cleanup + qwen2.5:14b summary readiness. Synthetic only.

Locks in: DWG/CAD→drawing (review-aware), strong-schedule precedence, blank submittal covers→
template_form, label-gated amounts for money docs, master cost-code→reference demotion, generic/matrix
spreadsheet restraint + the internal-consistency guard, the single hb-local-summary pending block, the
DB-only (no source-file read) render, and the replace_local_summary_block append contract.
"""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp import source_analyzers as sa
from hb_assistant.obsidian_mcp import source_notes as sn
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_value import (
    SourceValueDisposition as Disp,
)
from hb_assistant.obsidian_mcp.source_value import (
    classify_source_value,
    derive_confidence,
)
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

_CFG = ObsidianMcpConfig()
_CANONICAL = [
    "## Source Summary", "## Why This Matters", "## PM Review Cues", "## Key Facts",
    "## Related Project", "## Related People / Companies", "## Related Decisions",
    "## Related Meetings", "## Source Basis", "## Advisory Summary", "## Follow-Up",
]


def _detail(rel, ext, text="", **extra):
    return {"source_id": "s" * 32, "source_kind": "external_file", "rel_path": rel, "file_ext": ext,
            "text_excerpt": text, "content_sha256": "abc", "indexed_at": "2026-06-30", **extra}


def _dt(rel, ext, text=""):
    return sa.from_detail(_detail(rel, ext, text)).document_type


def _disp(rel, ext, text=""):
    return classify_source_value(_detail(rel, ext, text), _CFG).disposition


def _card(rel, ext, text="", **extra):
    return sn._render_card(_CFG, _detail(rel, ext, text, **extra), "2026-06-30T00:00:00Z")


def _section(card, heading):
    out, cap = [], False
    for ln in card.splitlines():
        if ln == heading:
            cap = True
            continue
        if cap and ln.startswith("## "):
            break
        if cap and ln.strip():
            out.append(ln)
    return "\n".join(out)


# ------------------------------------------------------------------------------- 3.1 DWG/CAD

@pytest.mark.parametrize("rel,ext", [
    ("ABL Building 4 Level 1 CAD.dwg", "dwg"), ("A201 Floor Plan.dwg", "dwg"),
    ("S101 Structural Foundation Plan.dxf", "dxf"), ("M301 Mechanical Schedule.dwg", "dwg"),
])
def test_cad_files_classify_as_drawing(rel, ext):
    assert _dt(rel, ext) == "drawing"  # incl. CAD ext winning over the "schedule" keyword in M301


def test_cad_drawing_card_is_review_aware_and_extraction_unsupported():
    card = _card("ABL Building 4 Level 1 CAD.dwg", "dwg", text="")  # binary → no extracted text
    assert 'review_status: "needs_review"' in card
    assert "Drawing extraction unsupported" in _section(card, "## Source Basis")


# ------------------------------------------------------------------------------- 3.2 schedule

@pytest.mark.parametrize("rel,ext", [
    ("BL_ConstructionSchedule_09202021.pdf", "pdf"), ("Baseline Schedule.pdf", "pdf"),
    ("Project Schedule Narrative.pdf", "pdf"), ("Construction Schedule Update 2026-06-15.pdf", "pdf"),
    ("Altis Blue Lake BIM Schedule.mpp", "mpp"), ("Baseline.xer", "xer"),
])
def test_strong_schedule_classifies_as_schedule(rel, ext):
    assert _dt(rel, ext) == "schedule"


@pytest.mark.parametrize("rel", [
    "Meeting Agenda - Schedule Discussion.pdf", "Email Print - Schedule Question.pdf",
])
def test_weak_schedule_does_not_classify_as_schedule(rel):
    assert _dt(rel, "pdf") != "schedule"


# ------------------------------------------------------------------------------- 3.3 submittal

@pytest.mark.parametrize("rel", [
    "Submittal Cover.pdf", "Submittal Cover Template.pdf", "Blank Submittal Cover Sheet.pdf",
    "Submittal Transmittal Form - Blank.pdf",
])
def test_blank_submittal_covers_are_template_form(rel):
    assert _dt(rel, "pdf") == "template_form"
    assert _disp(rel, "pdf") is Disp.METADATA_ONLY


@pytest.mark.parametrize("rel", [
    "Submittal 05 51 00 Metal Stairs.pdf", "Submittal 031000 Concrete Forming - Approved.pdf",
    "Submittal Package 07 Waterproofing.pdf",
])
def test_actual_submittals_stay_submittal(rel):
    assert _dt(rel, "pdf") == "submittal"
    assert _disp(rel, "pdf") is Disp.AUTO_CARD_HIGH


# ------------------------------------------------------------------------------- 3.4 amounts

def test_scope_bid_stray_dollars_suppressed():
    bid = "Provide all necessary labor for $1 each; unit price $42.00; insurance limit $1,000,000."
    assert sa.from_detail(_detail("Bid Package 08-03 Glass.txt", "txt", bid)).amount is None
    scope = "Exhibit A Scope of Work. Bond value $50,000. Phone 561-555-1212."
    assert sa.from_detail(_detail("Exhibit A_Scope of Work_03 Shell.docx", "docx", scope)).amount is None


@pytest.mark.parametrize("rel,text,expect", [
    ("PCCO 004.pdf", "Change Order Amount: $12,500.00", "$12,500.00"),
    ("Purchase Order 100245.pdf", "PO Amount: $8,250.00", "$8,250.00"),
    ("Pay Application 07.pdf", "Application Amount: $250,000.00", "$250,000.00"),
    ("Cost Report June.xlsx", "Grand Total: $1,250,000.00", "$1,250,000.00"),
])
def test_labeled_money_amounts_still_extract(rel, text, expect):
    ext = "xlsx" if rel.endswith(".xlsx") else "pdf"
    assert sa.from_detail(_detail(rel, ext, text)).amount == expect


def test_source_basis_explains_amount_suppression_only_when_detected():
    suppressed = _card("Bid Package 08-03 Glass.txt", "txt", text="unit price $42.00 each")
    assert "Amount not extracted: no strong amount label" in _section(suppressed, "## Source Basis")
    clean = _card("Bid Package 08-03 Glass.txt", "txt", text="scope of work, no figures")
    assert "Amount not extracted" not in _section(clean, "## Source Basis")


# ------------------------------------------------------------------------------- 3.5 reference

@pytest.mark.parametrize("rel,ext", [
    ("Master Cost Codes New construction Revised Feb 2018.xls", "xls"),
    ("Cost Code Master List.xlsx", "xlsx"), ("Standard Cost Codes.xlsx", "xlsx"),
    ("Chart of Accounts Cost Codes.csv", "csv"),
])
def test_master_cost_code_files_demote_to_reference(rel, ext):
    assert _dt(rel, ext) == "reference_document"
    assert _disp(rel, ext) is Disp.METADATA_ONLY


@pytest.mark.parametrize("rel", [
    "Project Cost Report June 2026.xlsx", "Forecast Cost Report 2026-06.xlsx",
    "Cost to Complete Report.xlsx",
])
def test_project_cost_reports_stay_high(rel):
    assert _disp(rel, "xlsx") is Disp.AUTO_CARD_HIGH


# ------------------------------------------------------------------------------- 3.6/3.7 spreadsheets

@pytest.mark.parametrize("rel", [
    "BIM Communications Matrix.xlsx", "Communications Matrix.xlsx", "Generic Tracker.xlsx",
    "Equipment List.xlsx",
])
def test_generic_spreadsheets_not_auto_card_high(rel):
    assert _disp(rel, "xlsx", "A | B") is not Disp.AUTO_CARD_HIGH


def test_consistency_guard_no_path_promotion_for_generic_or_reference():
    # A generic workbook / reference list under a high-signal "cost report" folder is NOT promoted.
    assert _disp("03 Cost Report/Communications Matrix.xlsx", "xlsx") is Disp.METADATA_ONLY
    assert _disp("03 Cost Report/Master Cost Codes.xls", "xls") is Disp.METADATA_ONLY


def test_low_confidence_implies_needs_review():
    card = _card("Generic Tracker.xlsx", "xlsx", text="A | B")
    assert 'review_status: "needs_review"' in card
    assert derive_confidence(classify_source_value(_detail("Generic Tracker.xlsx", "xlsx"), _CFG)) == "low"


def test_metadata_only_card_does_not_imply_verified_instrument():
    card = _card("Master Cost Codes.xls", "xls")
    basis = _section(card, "## Source Basis")
    assert "not a project cost instrument" in basis.lower() or "not a project cost" in basis.lower()


# ------------------------------------------------------------------------------- 4 Qwen readiness

def test_advisory_summary_has_single_pending_block_naming_qwen():
    card = _card("RFI 5.pdf", "pdf", text="RFI #5")
    assert card.count("hb-local-summary:start") == 1
    assert card.count("hb-local-summary:end") == 1
    block = _section(card, "## Advisory Summary")
    assert 'model="qwen2.5:14b" status="pending"' in block
    assert "ready for local summarization" in block


def test_renderer_emits_no_fabricated_advisory_content():
    card = _card("RFI 5.pdf", "pdf", text="RFI #5")
    block = _section(card, "## Advisory Summary")
    # only the marker lines + the pending notice — no model summary prose
    assert "not authoritative" not in block  # that label only appears on a real (generated) advisory


def test_card_keeps_canonical_11_sections_and_no_old_sections():
    card = _card("Project Cost Report June 2026.xlsx", "xlsx", text="--- Summary ---\nTotal | 1")
    assert [ln for ln in card.splitlines() if ln.startswith("## ")] == _CANONICAL
    for old in ("## Overview", "## Indexed Text Preview", "## Source Reference", "## File Analysis",
                "## Drawing Identity", "## Spreadsheet Identity", "## Bid Package Identity"):
        assert old not in card


def test_replace_local_summary_block_replaces_only_interior():
    card = _card("RFI 5.pdf", "pdf", text="RFI #5")
    fm_before = card.split("# Source Card:")[0]
    key_facts_before = _section(card, "## Key Facts")
    basis_before = _section(card, "## Source Basis")
    followup_before = _section(card, "## Follow-Up")
    updated = sn.replace_local_summary_block(
        card, ["A concise local advisory.", "", "**Key points:**", "- one"],
        model="qwen2.5:14b", generated_at="2026-06-30T01:00:00Z")
    # interior replaced + status flipped
    assert 'status="generated"' in updated and "A concise local advisory." in updated
    assert updated.count("hb-local-summary:start") == 1 and updated.count("hb-local-summary:end") == 1
    # deterministic sections untouched, canonical order preserved
    assert updated.split("# Source Card:")[0] == fm_before
    assert _section(updated, "## Key Facts") == key_facts_before
    assert _section(updated, "## Source Basis") == basis_before
    assert _section(updated, "## Follow-Up") == followup_before
    assert [ln for ln in updated.splitlines() if ln.startswith("## ")] == _CANONICAL


def test_replace_local_summary_block_requires_the_block():
    with pytest.raises(ObsidianMcpToolError):
        sn.replace_local_summary_block("no markers here", ["x"], model="qwen2.5:14b",
                                       generated_at="2026-06-30T01:00:00Z")


# ------------------------------------------------------------------------------- 6 no source read

def test_render_is_db_only_and_does_not_read_source_file(tmp_path, monkeypatch):
    # rel_path points at a file that does NOT exist; rendering must still succeed purely from detail,
    # proving no external source-file read / parse / scan happens during card render.
    import builtins
    real_open = builtins.open

    def _guard(path, *a, **k):
        p = str(path)
        if "/syn-source/" in p:  # the (nonexistent) external source location
            raise AssertionError(f"source file was read during render: {p}")
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", _guard)
    card = _card("/syn-source/Never Read.dwg", "dwg", text="")  # binary, no excerpt
    assert "## Source Summary" in card and 'card_version: "phase10a-v1"' in card
