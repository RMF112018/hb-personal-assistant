"""Phase 10H — bounded reconcile of ALL Tropical Work source cards (planner-level).

Exercises `_plan_all_tropical_identity` in scripts/obsidian_source_note_correct_graph.py: scope keyed on
the authoritative hb-project-identity block (NOT analyzer document_type), disagreement detection,
already-consistent no-op, skip reasons (no/ambiguous/malformed/other-project block), and managed-block
byte preservation. Pure planner over synthetic card text; no DB / no vault write.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tests.test_obsidian_source_graph_apply import _nf

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_note_correct_graph.py"
_spec = importlib.util.spec_from_file_location("correct_note_graph_10h", _SCRIPT)
assert _spec and _spec.loader
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_EMAIL_BLOCK = ('<!-- hb-email:start message_id_hash="mid1" thread_topic="t" -->\n'
                "<!-- hb-email:end -->\n")


def _idblock(num="23-435-01", key="tropical", procore="2525840", name="Tropical World Nursery Senior Living Facility"):
    return (f'<!-- hb-project-identity:start project_number="{num}" project_key="{key}" '
            f'procore_project_id="{procore}" -->\n'
            f"- Resolved project: {num} · {key} · {name}\n"
            f"- Procore project id: {procore}\n"
            "<!-- hb-project-identity:end -->\n")


def _card(*, fm_key="23-435-01", fm_num="23-435-01", placeholder=True, blocks=1,
          resolve_key="tropical", resolve_num="23-435-01", procore="2525840",
          email=False, doctype="general_document", extra=""):
    related = ("- Detected project number: 23-435-01; no project record linked yet.\n"
               if placeholder
               else "- Project: 23-435-01 — Tropical World Nursery Senior Living Facility · tropical\n")
    idblocks = "".join(_idblock(resolve_num, resolve_key, procore) for _ in range(blocks))
    email_block = _EMAIL_BLOCK if email else ""
    return (f"---\nnote_type: source_card\ndocument_type: \"{doctype}\"\n"
            f'project_key: "{fm_key}"\nproject_number: "{fm_num}"\ntags:\n  - project/{fm_num}\n---\n'
            f"# Card\n\n## Related Project\n{related}\n{idblocks}\n{email_block}{extra}")


def _run(cards):
    facts = {nid: _nf(nid, f"Source Notes/Work/{nid}.md") for nid in cards}
    plan: dict = {}
    stats = cg._plan_all_tropical_identity(facts, dict(cards), plan)
    return stats, plan


def test_scopes_and_counts_by_block_not_document_type():
    cards = {
        # non-email general_document, wrong fm key + placeholder → reconciled (non-email)
        "A": _card(fm_key="23-435-01", placeholder=True, doctype="general_document"),
        # email card, already consistent → no-op (already_consistent), NOT re-touched
        "B": _card(fm_key="tropical", placeholder=False, email=True, doctype="email"),
        # email card disagreeing → reconciled (email)
        "C": _card(fm_key="23-435-01", placeholder=True, email=True, doctype="email"),
        # submittal analyzer type but a resolving Tropical block + disagreement → reconciled (non-email)
        "D": _card(fm_key="23-435-01", placeholder=True, doctype="submittal"),
        # no identity block → skip_no_identity
        "E": ("---\ndocument_type: \"email\"\nproject_key: \"23-435-01\"\n---\n# e\n"
              "## Related Project\n- x\n"),
        # two identity blocks → skip_ambiguous
        "F": _card(fm_key="23-435-01", blocks=2),
        # resolves a different project → skip_other
        "G": _card(fm_key="99-000-00", resolve_key="other", resolve_num="99-000-00", procore="999"),
    }
    stats, plan = _run(cards)
    assert stats["cards_scanned"] == 7
    assert stats["tropical_identity_cards"] == 4  # A,B,C,D (single Tropical-resolving block)
    assert stats["cards_disagreeing"] == 3  # A,C,D (B already consistent)
    assert stats["cards_corrected"] == 3
    assert stats["email_cards_corrected"] == 1 and stats["non_email_cards_corrected"] == 2
    assert stats["email_cards_disagreeing"] == 1 and stats["non_email_cards_disagreeing"] == 2
    assert stats["cards_skipped_no_identity"] == 1  # E
    assert stats["cards_skipped_ambiguous_identity"] == 1  # F
    assert stats["cards_skipped_other_project"] == 1  # G
    assert set(plan) == {"A", "C", "D"}  # B (consistent), E/F/G (skipped) never planned


def test_already_consistent_card_is_byte_identical():
    consistent = _card(fm_key="tropical", placeholder=False, email=True, doctype="email")
    facts = {"B": _nf("B", "Source Notes/Work/B.md")}
    plan: dict = {}
    stats = cg._plan_all_tropical_identity(facts, {"B": consistent}, plan)
    assert stats["cards_corrected"] == 0 and "B" not in plan  # untouched


def test_reconcile_preserves_other_managed_blocks_byte_for_byte():
    other = ("<!-- hb-local-summary:start -->\n- summary line\n<!-- hb-local-summary:end -->\n\n"
             "<!-- gc-graph-links:start -->\n- [[Source Notes/Work/Z__zz|Z]] — same_company · x\n"
             "<!-- gc-graph-links:end -->\n")
    card = _card(fm_key="23-435-01", placeholder=True, extra="\n" + other)
    facts = {"A": _nf("A", "Source Notes/Work/A.md")}
    plan: dict = {}
    cg._plan_all_tropical_identity(facts, {"A": card}, plan)
    out = plan["A"]
    # identity + other managed blocks untouched; graph link not reordered/removed
    assert out.count("hb-project-identity:start") == 1
    assert "<!-- hb-local-summary:start -->\n- summary line\n<!-- hb-local-summary:end -->" in out
    assert "<!-- gc-graph-links:start -->\n- [[Source Notes/Work/Z__zz|Z]] — same_company · x\n" \
           "<!-- gc-graph-links:end -->" in out
    # only the frontmatter key + placeholder line changed
    assert 'project_key: "tropical"' in out and "no project record linked yet" not in out
    assert out.count("- project/23-435-01") == 1  # tag preserved, not duplicated


def test_project_tag_added_when_missing_only_once():
    # card carries a source-type tag but is missing the project tag (realistic 10D shape)
    card = _card(fm_key="23-435-01", placeholder=True).replace(
        "  - project/23-435-01\n", "  - source/type/spreadsheet\n")
    facts = {"A": _nf("A", "Source Notes/Work/A.md")}
    plan: dict = {}
    stats = cg._plan_all_tropical_identity(facts, {"A": card}, plan)
    assert stats["project_tags_added"] == 1
    assert plan["A"].count("- project/23-435-01") == 1
    assert "- source/type/spreadsheet" in plan["A"]  # pre-existing tag preserved
