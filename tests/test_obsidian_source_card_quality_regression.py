"""Phase 8 source-card quality regression: renderer template alignment + tightened taxonomy.

Fixture-driven and synthetic only — no production cards, no DB, no model. Locks in the 11-section
template renderer, template/form demotion, tightened status/amount/date extraction, and the
disposition tuning so the card-quality issues found in the Phase 7 review cannot silently regress.
"""

from __future__ import annotations

from hb_assistant.obsidian_mcp import source_analyzers, source_notes
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_value import (
    SourceValueDisposition,
    classify_source_value,
    derive_confidence,
)

# The canonical card body, in order (mirrors Templates/Source Cards/source-card-template.md).
_SECTIONS = [
    "## Source Summary", "## Why This Matters", "## PM Review Cues", "## Key Facts",
    "## Related Project", "## Related People / Companies", "## Related Decisions",
    "## Related Meetings", "## Source Basis", "## Advisory Summary", "## Follow-Up",
]


def _analyze(rel: str, ext: str = "pdf", text: str = ""):
    return source_analyzers.from_detail({"rel_path": rel, "file_ext": ext, "text_excerpt": text})


def _card(rel: str, ext: str = "pdf", text: str = "", **extra) -> str:
    detail = {
        "source_id": "s" * 32, "source_kind": "external_file", "rel_path": rel,
        "source_root_key": "syn-work", "file_ext": ext, "text_excerpt": text,
        "project_number": "25-123-01", "content_sha256": "abc", "indexed_at": "2026-06-30", **extra,
    }
    return source_notes._render_card(ObsidianMcpConfig(), detail, "2026-06-30T00:00:00Z")


def _section_body(card: str, heading: str) -> list[str]:
    out: list[str] = []
    capturing = False
    for line in card.splitlines():
        if line == heading:
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing and line.strip():
            out.append(line)
    return out


def test_card_has_all_eleven_template_sections_in_order() -> None:
    card = _card("25-123-01/RFI 032 - Door Hardware.pdf", text="Request for Information RFI #032")
    headings = [ln for ln in card.splitlines() if ln.startswith("## ")]
    assert headings == _SECTIONS, headings
    # No legacy/competing top-level type sections survive.
    for legacy in ("## Overview", "## Indexed Text Preview", "## Source Reference",
                   "## Drawing Identity", "## Spreadsheet Identity", "## Bid Package Identity",
                   "## Document Identity", "## File Analysis", "## AI Summary", "## AI PM Summary"):
        assert legacy not in card, legacy


def test_template_form_demoted_never_high_even_in_change_orders_folder() -> None:
    cfg = ObsidianMcpConfig()
    assert _analyze("25-123-01 Change Order Template.pdf").document_type == "template_form"
    # A template filed inside a "Change Orders" folder must NOT be path-signal promoted to high.
    sv = classify_source_value(
        {"rel_path": "03 Change Orders/Owner Change Order Request Template.pdf",
         "file_ext": "pdf", "text_excerpt": ""}, cfg)
    assert sv.disposition is SourceValueDisposition.METADATA_ONLY
    assert sv.allow_auto_card is False
    assert derive_confidence(sv) == "low"
    # The card flags it for human review and labels it a blank instrument.
    card = _card("03 Change Orders/Owner Change Order Request Template.pdf")
    assert 'review_status: "needs_review"' in card
    assert any("blank instrument" in ln for ln in _section_body(card, "## Source Basis"))


def test_various_template_form_filenames_detected() -> None:
    for name in ("Submittal Cover Template.pdf", "BIM Coordination Sign-Off Form.pdf",
                 "Punch List Template.pdf", "Safety Inspection Checklist Template.pdf",
                 "Pay Application Form - Blank.pdf"):
        assert _analyze(f"25-123-01 {name}").document_type == "template_form", name
    # Real instruments with no template signal keep their real type.
    assert _analyze("25-123-01 Executed Change Order 004.pdf").document_type == "change_order"
    assert _analyze("25-123-01 Submittal 05 51 00 Metal Stairs.pdf").document_type == "submittal"
    assert _analyze("25-123-01 Safety Inspection 2026-06-15.pdf").document_type == "safety"


def test_template_status_and_amount_are_suppressed() -> None:
    a = _analyze("25-123-01 Change Order Template.pdf", "pdf",
                 "Status: Approved\nAmount: $5,000.00\nfor template use only")
    assert a.doc_status is None and a.amount is None


def test_schedule_stays_schedule() -> None:
    assert _analyze("25-123-01 Baseline Schedule Update 04.xer", "xer").document_type == "schedule"


def test_drawing_without_text_is_extraction_unsupported() -> None:
    a = _analyze("25-123-01 A-101 Cover.pdf")
    assert a.is_drawing
    card = _card("25-123-01 A-101 Cover.pdf", text="")  # no extracted text
    facts = _section_body(card, "## Key Facts")
    assert any("Extraction unsupported" in ln for ln in facts), facts


def test_pcp_and_internal_app_files_unsupported() -> None:
    cfg = ObsidianMcpConfig()
    for ext in ("pcp", "bak", "ini", "db"):
        sv = classify_source_value(
            {"rel_path": f"03 Change Orders/internal.{ext}", "file_ext": ext, "text_excerpt": ""}, cfg)
        assert sv.disposition is SourceValueDisposition.UNSUPPORTED, ext
        assert sv.allow_metadata_index is False


def test_rfi_closed_status_from_filename_segment() -> None:
    a = _analyze("25-123-01 RFI 032 - Closed - Door Hardware.pdf")
    assert a.doc_status == "closed" and a.document_number == "032"
    # The status segment is not mistaken for the title.
    assert a.title == "Door Hardware"


def test_purchase_order_status_only_when_explicit() -> None:
    # No status anywhere → None.
    bare = _analyze("25-123-01 Purchase Order 100245 - Steel Supply.pdf")
    assert bare.doc_status is None
    # Bare keyword in the body (unlabeled) → still None (the old keyword scan is gone).
    unlabeled = _analyze("25-123-01 Purchase Order 100245 - Steel Supply.pdf", "pdf",
                         "This purchase order was approved by the PM yesterday.")
    assert unlabeled.doc_status is None
    # Labeled field → extracted.
    labeled = _analyze("25-123-01 Purchase Order 100245 - Steel Supply.pdf", "pdf", "Status: Approved")
    assert labeled.doc_status == "approved"


def test_status_rejects_dropdown_lists() -> None:
    dropdown = _analyze("25-123-01 Submittal 05 51 00.pdf", "pdf",
                        "Status: Approved / Rejected / Revise and Resubmit")
    assert dropdown.doc_status is None
    single = _analyze("25-123-01 Submittal 05 51 00.pdf", "pdf", "Submittal Status: Approved")
    assert single.doc_status == "approved"


def test_amount_rejects_zero_example_and_range_keeps_explicit() -> None:
    # change_order is a label-gated money type (Phase 10A): unlabeled/zero/example/range/stray → None.
    assert _analyze("25-123-01 PCCO 5.pdf", "pdf", "Total: $0.00").amount is None
    assert _analyze("25-123-01 PCCO 5.pdf", "pdf", "for example $5,000.00 budget").amount is None
    assert _analyze("25-123-01 PCCO 5.pdf", "pdf", "range of $1,000.00 - $2,000.00").amount is None
    assert _analyze("25-123-01 PCCO 5.pdf", "pdf", "incidental scope value $42.00 each").amount is None
    # A strong, type-appropriate label extracts.
    assert _analyze("25-123-01 PCCO 5.pdf", "pdf",
                    "Change Order Amount: $12,500.00").amount == "$12,500.00"


def test_date_only_filename_iso_or_labeled() -> None:
    assert _analyze("25-123-01 Daily Log 2026-06-15.pdf").doc_date == "2026-06-15"
    assert _analyze("25-123-01 Cost Report.pdf", "pdf", "Issued: 2026-06-15").doc_date == "2026-06-15"
    # An unlabeled ISO date in the body is NOT a document date anymore.
    assert _analyze("25-123-01 Cost Report.pdf", "pdf", "see meeting 2026-06-15 agenda").doc_date is None


def test_spreadsheet_promotion_requires_strong_evidence() -> None:
    cfg = ObsidianMcpConfig()

    def disp(rel: str, text: str = "") -> SourceValueDisposition:
        return classify_source_value(
            {"rel_path": rel, "file_ext": "xlsx", "text_excerpt": text}, cfg).disposition

    assert disp("25-123-01 Cost Report June.xlsx") is SourceValueDisposition.AUTO_CARD_HIGH
    assert disp("25-123-01 Pay Application 07.xlsx") is SourceValueDisposition.AUTO_CARD_HIGH
    assert disp("25-123-01 Misc Tracker.xlsx", "A | B") is SourceValueDisposition.METADATA_ONLY


def test_source_basis_is_meaningful_without_a_model() -> None:
    card = _card("25-123-01/RFI 032 - Door Hardware.pdf", text="Request for Information RFI #032")
    basis = "\n".join(_section_body(card, "## Source Basis"))
    for needle in ("Card basis:", "Document type: rfi", "Classification reason:",
                   "Matched filename tokens:", "Source ID:"):
        assert needle in basis, needle
    # Deterministic card: the advisory section is the qwen2.5:14b pending block, not fabricated text.
    advisory = "\n".join(_section_body(card, "## Advisory Summary"))
    assert 'hb-local-summary:start model="qwen2.5:14b" status="pending"' in advisory
    assert "ready for local summarization" in advisory
    assert "## AI Summary" not in card


def test_follow_up_is_document_type_specific_not_boilerplate() -> None:
    co = "\n".join(_section_body(_card("25-123-01 Executed Change Order 004.pdf"), "## Follow-Up"))
    rfi = "\n".join(_section_body(_card("25-123-01 RFI 032.pdf"), "## Follow-Up"))
    sched = "\n".join(_section_body(_card("25-123-01 Baseline Schedule.pdf"), "## Follow-Up"))
    assert co and rfi and sched
    assert co != rfi != sched
    assert "change event" in co.lower()
    assert "open" in rfi.lower() or "closed" in rfi.lower()
    assert "data date" in sched.lower()


def test_related_sections_state_detected_not_resolved() -> None:
    card = _card("25-123-01 Subcontract - MEP Prime.pdf")
    proj = "\n".join(_section_body(card, "## Related Project"))
    people = "\n".join(_section_body(card, "## Related People / Companies"))
    assert "Detected project number: 25-123-01; no project record linked yet." in proj
    assert "Detected counterparty: MEP Prime; no company record linked yet." in people
    assert "No related decisions linked yet." in card
    assert "No related meetings linked yet." in card
