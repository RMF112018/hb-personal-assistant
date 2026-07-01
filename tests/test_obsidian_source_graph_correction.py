"""Phase 10G correction script — entry-level link removal + email identity reconcile planning.

Exercises the pure planners in scripts/obsidian_source_note_correct_graph.py (no DB / no vault write):
offending-only removal, reciprocity, conditional graph-tag stripping (only when no valid link remains),
and bounded email-identity reconciliation. Synthetic facts/text only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from hb_assistant.obsidian_mcp import source_note_graph as ng
from tests.test_obsidian_source_graph_apply import _nf

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_note_correct_graph.py"
_spec = importlib.util.spec_from_file_location("correct_note_graph", _SCRIPT)
assert _spec and _spec.loader
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


def _card(*, rel, links, tags=("source/type/correspondence", "related/company", "review/qwen-vetted")):
    tag_lines = "".join(f"  - {t}\n" for t in tags)
    link_lines = "".join(f"- {ln}\n" for ln in links)
    return (f"---\nnote_type: source_card\ndocument_type: \"email\"\ntags:\n{tag_lines}---\n"
            f"# Card\n\n## Related Project\n- Detected project number: 25-1; no project record linked yet.\n\n"
            f"{ng.REL_BLOCK_BEGIN}\n{link_lines}{ng.REL_BLOCK_END}\n")


def _linkline(rel, rtype, conf="1.00"):
    stem = rel[:-3] if rel.endswith(".md") else rel
    return f"[[{stem}|X]] — {rtype} · qwen-vetted · confidence {conf}"


def test_link_parse_helpers():
    ln = _linkline("Source Notes/Work/B__bbbbbbbb2222.md", "same_project")
    assert cg._link_target_rel(ln) == "Source Notes/Work/B__bbbbbbbb2222.md"
    assert cg._link_rel_type(ln) == "same_project"


def test_plan_removals_reciprocal_and_strips_tags_when_no_link_remains():
    a_rel, b_rel = "Source Notes/Work/A__aaaaaaaa1111.md", "Source Notes/Work/B__bbbbbbbb2222.md"
    facts = {  # duplicate email pair (shared message-id) linked (wrongly) as same_project
        "A": _nf("A", a_rel, message_id_hash="mid", thread_topic="t", subject_norm="s"),
        "B": _nf("B", b_rel, message_id_hash="mid", thread_topic="t", subject_norm="s"),
    }
    text = {"A": _card(rel=a_rel, links=[_linkline(b_rel, "same_project")]),
            "B": _card(rel=b_rel, links=[_linkline(a_rel, "same_project")])}
    detail: list = []
    plan, stats = cg._plan_removals(facts, text, detail)
    assert stats["offending_pairs"] == 1
    assert set(plan) == {"A", "B"}
    for nid in ("A", "B"):
        assert ng.REL_BLOCK_BEGIN not in plan[nid]  # block removed (was the only entry)
        assert "- related/company" not in plan[nid] and "- review/qwen-vetted" not in plan[nid]
        assert "- source/type/correspondence" in plan[nid]  # non-graph tag preserved
    assert stats["graph_tag_notes_stripped"] == 2


def test_plan_removals_preserves_tags_when_a_valid_link_remains():
    a_rel = "Source Notes/Work/A__aaaaaaaa1111.md"
    b_rel = "Source Notes/Work/B__bbbbbbbb2222.md"  # offending (duplicate) partner
    c_rel = "Source Notes/Work/C__cccccccc3333.md"  # valid same_company partner
    facts = {
        "A": _nf("A", a_rel, message_id_hash="mid", thread_topic="t", subject_norm="s"),
        "B": _nf("B", b_rel, message_id_hash="mid", thread_topic="t", subject_norm="s"),
        "C": _nf("C", c_rel, vendor="acme"),
    }
    text = {
        "A": _card(rel=a_rel, links=[_linkline(b_rel, "same_project"), _linkline(c_rel, "same_company")]),
        "B": _card(rel=b_rel, links=[_linkline(a_rel, "same_project")]),
        "C": _card(rel=c_rel, links=[_linkline(a_rel, "same_company")]),
    }
    plan, stats = cg._plan_removals(facts, text, [])
    assert stats["offending_pairs"] == 1  # only (A,B)
    # A keeps its valid same_company link to C AND its graph tags
    assert "C__cccccccc3333" in plan["A"] and "B__bbbbbbbb2222" not in plan["A"]
    assert "- related/company" in plan["A"] and ng.REL_BLOCK_BEGIN in plan["A"]
    # B had only the offending link → block removed + tags stripped
    assert ng.REL_BLOCK_BEGIN not in plan["B"] and "- related/company" not in plan["B"]
    assert "C" not in plan  # C's valid link to A is untouched


_TROP_MARK = ('<!-- hb-project-identity:start project_number="23-435-01" project_key="tropical" '
              'procore_project_id="2525840" -->\n- Resolved project: 23-435-01 · tropical · Tropical\n'
              "<!-- hb-project-identity:end -->\n")


# A real hb-email managed block is what DEFINES an email source card for the reconcile scope — NOT the
# (drift-prone) analyzer document_type. This mirrors the live-correction lesson.
_EMAIL_BLOCK = ('<!-- hb-email:start message_id_hash="mid1" thread_topic="t" -->\n'
                "<!-- hb-email:end -->\n")


def _email_card_with_block(rel, *, key='"23-435-01"'):
    return (f"---\nnote_type: source_card\ndocument_type: \"email\"\nproject_key: {key}\n"
            f'project_number: "23-435-01"\ntags:\n  - project/23-435-01\n---\n# E\n\n'
            f"## Related Project\n- Detected project number: 23-435-01; no project record linked yet.\n\n"
            f"{_EMAIL_BLOCK}\n{_TROP_MARK}")


def test_plan_identity_scopes_to_email_block_not_analyzer_document_type():
    e_rel = "Source Notes/Work/E__eeeeeeee0000.md"
    g_rel = "Source Notes/Work/G__gggggggg0000.md"
    d_rel = "Source Notes/Work/D__dddddddd0000.md"
    # G is document_type=="email" per the analyzer but has NO hb-email block (the exact over-scope trap):
    # it must be SKIPPED. D is a normal non-email card. E is a genuine email card (has the block).
    facts = {
        "E": _nf("E", e_rel, document_type="email", thread_topic="t"),
        "G": _nf("G", g_rel, document_type="email"),  # analyzer says email but no block below
        "D": _nf("D", d_rel, document_type="cost_report"),
    }
    text = {
        "E": _email_card_with_block(e_rel),
        "G": (f'---\ndocument_type: "general_document"\nproject_key: "23-435-01"\n'
              f'project_number: "23-435-01"\n---\n# g\n\n## Related Project\n'
              f"- Detected project number: 23-435-01; no project record linked yet.\n\n{_TROP_MARK}"),
        "D": "---\ndocument_type: \"cost_report\"\n---\n# d\n",
    }
    plan: dict = {}
    stats = cg._plan_identity(facts, text, plan)
    assert stats["email_cards_scanned"] == 1  # only E (has an hb-email block)
    assert stats["email_cards_reconciled"] == 1
    assert set(plan) == {"E"}  # G (no email block) and D (non-email) are never touched
    import re
    assert re.search(r'(?m)^project_key:\s*"tropical"', plan["E"])
    assert "no project record linked yet" not in plan["E"]
