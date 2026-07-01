"""Phase 10K — deterministic classifier-repair + provenance (pure unit tests).

Proves the guarded three-family repair: value-analysis logs, generic specification templates, and
clarification/question memos are corrected only when strong filename/title AND excerpt evidence
contradict/refine a weak-or-conflicting base type; true warranty/submittal/scope/contract are never
touched; thin/ambiguous documents stay unchanged and are flagged review_required; path/title alone
never repairs; provenance signals carry no raw paths. Also proves the upstream ``from_detail`` wire-in
corrects the three families while leaving every other existing type byte-identical.
"""

from __future__ import annotations

from hb_assistant.obsidian_mcp import source_analyzers as sa
from hb_assistant.obsidian_mcp import source_document_classifier as dc

_VA_TXT = ("VALUE ANALYSIS TRACKING LOG\nItem 1 Alternate glazing  Status Open   Value #REF!\n"
           "Item 2 Roofing membrane  Status Accepted Value 45000\nItem 3 HVAC  Status Rejected")
_SPEC_TXT = ("SECTION 02 87 13 MOLD REMEDIATION — MasterWorks generic specification.\n"
             "PART 1 GENERAL. Specifier shall retain or delete sections. Submittals: SDS, product data, "
             "VOC content. Provide manufacturer remediation products.")
_MEMO_TXT = ("PRECONSTRUCTION CLARIFICATION MEMO. Open questions for the team: What is the final "
             "foundation elevation? Who provides temporary power? When is the geotech report issued?")


def _type(fn, ext, text, existing, path="Source Notes/Work/x"):
    return dc.classify_source_document(filename=fn, source_path=path, extension=ext,
                                       extracted_text_excerpt=text,
                                       existing_document_type=existing)


# --------------------------------------------------------------------------- three-family repair
def test_va_log_repaired_despite_warranty_hint():
    c = _type("20241016_TWN_VA_Log.pdf", "pdf", _VA_TXT, "warranty")
    assert c.document_type == "value_analysis" and c.classification_conflict is True
    assert c.confidence == "high" and c.review_required is False


def test_generic_spec_repaired_despite_submittals_path():
    c = _type("Masterworks-Specification-02-87-13-Mold.doc", "doc", _SPEC_TXT, "submittal",
              path="NAS/Projects/23-435-01/20_Construction/Submittals/Fiberlock/spec.docx")
    assert c.document_type == "specification_template" and c.classification_conflict is True


def test_clarification_memo_repaired_despite_scope_path():
    c = _type("1.docx", "docx", _MEMO_TXT, "scope_of_work",
              path="NAS/Projects/23-435-01/Contracts/Subcontracts/Div_26/1.docx")
    assert c.document_type == "clarification_memo" and c.classification_conflict is True


# --------------------------------------------------------------------------- existing types preserved
def test_true_warranty_unchanged():
    c = _type("Roof Warranty Certificate.pdf", "pdf",
              "This warranty covers the roofing membrane for twenty years against defects.", "warranty")
    assert c.document_type == "warranty" and c.classification_conflict is False


def test_true_submittal_unchanged():
    c = _type("Submittal 03 20 00 Rebar Shop Drawings.pdf", "pdf",
              "Submittal for reinforcing steel shop drawings; reviewed and approved as noted.", "submittal")
    assert c.document_type == "submittal"


def test_true_scope_unchanged():
    c = _type("Exhibit A Scope of Work Concrete.pdf", "pdf",
              "Scope of work: furnish all labor and material for site concrete. Inclusions and "
              "exclusions are listed below.", "scope_of_work")
    assert c.document_type == "scope_of_work"


def test_true_contract_unchanged():
    c = _type("Prime Contract Executed.pdf", "pdf",
              "This agreement between owner and contractor defines the contract value and terms.",
              "contract")
    assert c.document_type == "contract"


# --------------------------------------------------------------------------- guard behaviour
def test_thin_va_hint_stays_and_flags_review():
    # Filename hints VA but there is no excerpt evidence -> keep existing, review_required.
    c = _type("VA Log.pdf", "pdf", "", "warranty")
    assert c.document_type == "warranty" and c.review_required is True and c.confidence == "low"


def test_spec_section_in_name_but_real_submittal_not_repaired():
    # A real submittal for section 02 87 13 lacks specifier/template structure -> NOT repaired.
    real = ("Submittal package for Section 02 87 13. Product data and approved shop drawings for the "
            "mold-resistant coating installed on this project.")
    c = _type("Submittal 02 87 13 Product Data.pdf", "pdf", real, "submittal")
    assert c.document_type == "submittal" and c.review_required is True


def test_path_alone_does_not_repair():
    # Scope-ish path + no memo/question structure in text -> no repair.
    c = _type("agreement.docx", "docx", "The subcontractor shall perform electrical work per plans.",
              "scope_of_work", path="NAS/.../Subcontracts/Div_26/agreement.docx")
    assert c.document_type == "scope_of_work"


def test_weak_base_type_refined_medium_confidence():
    # A generic base type refined by strong family evidence -> medium confidence, not a hard conflict.
    c = _type("VA Log.pdf", "pdf", _VA_TXT, "general_pdf")
    assert c.document_type == "value_analysis" and c.confidence == "medium"
    assert c.classification_conflict is False


# --------------------------------------------------------------------------- provenance hygiene
def test_signals_carry_no_raw_path():
    c = _type("1.docx", "docx", _MEMO_TXT, "scope_of_work",
              path="/Users/bobby/Documents/Obsidian Vault/Source Notes/Work/1.docx")
    joined = " ".join(c.classification_signals)
    assert "/" not in joined and "Users" not in joined and ".docx" not in joined
    assert c.classification_signals  # non-empty deterministic tokens


def test_reason_is_pm_safe_no_liability_language():
    c = _type("20241016_TWN_VA_Log.pdf", "pdf", _VA_TXT, "warranty")
    low = c.classification_reason.lower()
    for banned in ("liability", "claim", "compensable", "entitlement", "fault", "causation"):
        assert banned not in low


# --------------------------------------------------------------------------- repair decision helper
def test_detect_classification_repair_hard_conflict():
    d = dc.detect_classification_repair(existing_document_type="warranty",
                                        proposed_document_type="value_analysis", signals=["title:va-log"])
    assert d.repaired and d.confidence == "high" and d.to_type == "value_analysis"


def test_detect_classification_repair_no_change():
    d = dc.detect_classification_repair(existing_document_type="value_analysis",
                                        proposed_document_type="value_analysis")
    assert d.repaired is False


# --------------------------------------------------------------------------- from_detail wire-in
def _fd(rel, ext, text):
    return sa.from_detail({"rel_path": rel, "file_ext": ext, "text_excerpt": text}).document_type


def test_from_detail_repairs_three_families():
    assert _fd("NAS/.../Exhibits/20241016_TWN_VA_Log.pdf", "pdf", _VA_TXT) == "value_analysis"
    assert _fd("NAS/.../Submittals/Masterworks-Spec-02-87-13-Mold.docx", "docx", _SPEC_TXT) \
        == "specification_template"


def test_from_detail_leaves_existing_types_unchanged():
    # A representative spread of non-family documents must classify exactly as before the wire-in.
    cases = [
        ("NAS/.../A-101 Floor Plan.pdf", "pdf", "Architectural floor plan sheet A-101."),
        ("NAS/.../Roof Warranty.pdf", "pdf", "This warranty covers roofing for twenty years."),
        ("NAS/.../Submittal 03 20 00 Rebar.pdf", "pdf", "Submittal shop drawings approved as noted."),
        ("NAS/.../Meeting Minutes 2024-10-01.pdf", "pdf", "Meeting minutes: attendees, action items."),
        ("NAS/.../Prime Contract.pdf", "pdf", "This agreement defines contract value and terms."),
        ("NAS/.../Schedule.xer", "xer", "Primavera schedule export."),
        ("NAS/.../Change Order Template.docx", "docx", "Change order template form."),
        ("NAS/.../message.eml", "eml", "From: a@b.com Subject: hello"),
    ]
    got = [_fd(*c) for c in cases]
    assert got == ["architectural_drawing", "warranty", "submittal", "meeting_minutes", "contract",
                   "schedule", "template_form", "email"]
