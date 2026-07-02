"""Phase 10K — first-class rendering for the three repaired document types.

Proves value_analysis / specification_template / clarification_memo are first-class across PM guidance,
the content-tag vocabulary + doctype map (never "unknown"), and that PM cues carry no forbidden
liability language.
"""

from __future__ import annotations

from hb_assistant.obsidian_mcp import source_note_graph as ng
from hb_assistant.obsidian_mcp import source_notes as sn
from tests.test_obsidian_source_graph_apply import _nf

_NEW_TYPES = ("value_analysis", "specification_template", "clarification_memo")
_NEW_SLUGS = {"value_analysis": "value-analysis",
              "specification_template": "specification-template",
              "clarification_memo": "clarification-memo"}
_FORBIDDEN = ("liability", "claim", "compensable", "entitlement", "fault", "causation",
              "delay damages", "responsibility", "forensic")


def test_pm_guidance_defined_for_new_types():
    for t in _NEW_TYPES:
        g = sn._pm_guidance(t)
        assert g is not sn._PM_GUIDANCE_FALLBACK, f"{t} falls back to generic guidance"
        assert g["why"] and g["cues"] and g["followup"]


def test_value_analysis_guidance_wording():
    g = sn._pm_guidance("value_analysis")
    assert "value-analysis log" in g["why"][0].lower()
    assert any("pending" in c.lower() or "budget" in c.lower() for c in g["cues"])
    # Phase 10K.1 Follow-Up: VA-log language (pending/conditional items, #REF/value issues, budget)
    fu = " ".join(g["followup"]).lower()
    assert "#ref" in fu and "pending" in fu and "budget" in fu
    assert "o&m" not in fu and "coverage term" not in fu  # no warranty carry-over


def test_specification_template_guidance_wording():
    g = sn._pm_guidance("specification_template")
    assert "template" in g["why"][0].lower()
    assert any("adopted" in c.lower() for c in g["cues"])
    # Phase 10K.1 Follow-Up: adopted / edited / superseded template question
    fu = " ".join(g["followup"]).lower()
    assert "adopted" in fu and "edited" in fu and "superseded" in fu


def test_clarification_memo_guidance_wording():
    g = sn._pm_guidance("clarification_memo")
    assert "clarification memo" in g["why"][0].lower()
    assert any("open" in c.lower() or "question" in c.lower() for c in g["cues"])
    # Phase 10K.1 Follow-Up: responses / owners on open items (not scope/addenda language)
    fu = " ".join(g["followup"]).lower()
    assert ("responses" in fu or "owners" in fu) and "clarification" in fu
    assert "scope inclusions" not in fu and "addenda" not in fu


def test_content_tags_map_to_own_slug_not_unknown():
    for t, slug in _NEW_SLUGS.items():
        assert ng._DOCTYPE_CONTENT.get(t) == slug
        fact = _nf("n1", "Source Notes/Work/x.md", document_type=t)
        tags = ng.content_tags_for(fact)
        assert f"source/type/{slug}" in tags
        assert "source/type/unknown" not in tags


def test_new_source_type_tags_are_approved():
    for slug in _NEW_SLUGS.values():
        assert ng.sanitize_tag(f"source/type/{slug}") == f"source/type/{slug}"


def test_pm_cues_have_no_forbidden_language():
    for t in _NEW_TYPES:
        g = sn._pm_guidance(t)
        blob = " ".join(g["why"] + g["cues"] + g["followup"]).lower()
        for banned in _FORBIDDEN:
            assert banned not in blob, f"{banned!r} present in {t} guidance"
