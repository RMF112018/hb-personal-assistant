"""Phase 10G — bounded note-graph apply (project-scoped selection, eligibility, checkpoints).

Proves the Phase 10G additions on top of the Phase 10C applier: bounded project selection,
primary+secondary eligibility, direct-lineage exclusion (amendment 1), same-sha duplicate review-only
(amendment 2), the post-vet approved-count checkpoint (amendment 3), the max-apply cap, project confirm
gates, and post-apply backlink integrity. Synthetic temp only; no real Ollama, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_note_graph as ng
from tests.test_obsidian_source_note_graph import (
    _args,
    _env,
    _FakeClient,
    _run,
    mod,
)


@pytest.fixture(autouse=True)
def _no_backend(monkeypatch):
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    monkeypatch.setattr(mod, "list_ollama_models", lambda **k: ["qwen2.5:14b"])


def _nf(nid, rel, **kw):
    base = Path(rel).stem
    d = {"note_id": nid, "note_rel": rel, "basename": base, "display": ng._display_name(base),
         "project": None, "vendor": None, "document_type": "rfi", "document_number": None,
         "doc_date": None, "disposition": "auto_card_high", "review_needed": False,
         "title_tokens": ng._title_tokens(base), "existing_tags": (), "summary_text": "s"}
    d.update(kw)
    return ng.NoteFact(**d)


# --------------------------------------------------------------------------- helpers (pure)

def test_classify_from_graph_facts():
    email = _nf("e", "x/E.md", thread_topic="tt")
    att = _nf("a", "x/A.md", attachment_extension="pdf", parent_email_hash="H")
    proj = _nf("p", "x/P.md", procore_project_id="2525840")
    assert mod._classify(email) == "email"
    assert mod._classify(att) == "attachment"
    assert mod._classify(proj) == "project"


def test_matches_project_by_number_key_or_procore():
    import argparse
    a = argparse.Namespace(project_number="23-435-01", project_key="", procore_project_id="")
    b = argparse.Namespace(project_number="", project_key="tropical", procore_project_id="")
    c = argparse.Namespace(project_number="", project_key="", procore_project_id="2525840")
    f_num = _nf("1", "x/1.md", project="23-435-01")
    f_key = _nf("2", "x/2.md", canonical_project_key="tropical")
    f_pro = _nf("3", "x/3.md", procore_project_id="2525840")
    other = _nf("4", "x/4.md", project="99-000-00")
    assert mod._matches_project(f_num, a) and not mod._matches_project(other, a)
    assert mod._matches_project(f_key, b) and not mod._matches_project(other, b)
    assert mod._matches_project(f_pro, c) and not mod._matches_project(other, c)


def test_parent_email_rel_parses_wiki_target():
    text = ("## Source Basis\n<!-- hb-email-attachment:start -->\n"
            "- Parent email card: [[Source Notes/Work/Parent Email__deadbeef1234|Parent Email]]\n"
            "<!-- hb-email-attachment:end -->\n")
    assert mod._parent_email_rel(text) == "Source Notes/Work/Parent Email__deadbeef1234.md"
    assert mod._parent_email_rel("no link here") is None


# ----------------------------------------------------------------- eligibility (primary+secondary)

def test_primary_secondary_requires_primary_plus_one_more_strong():
    # project-only → durable-rejected in bounded mode (still eligible in Phase-10C default mode).
    a = _nf("a", "w/A.md", project="25-1")
    b = _nf("b", "w/B.md", project="25-1")
    assert ng.is_candidate(a, b, mode="primary_secondary")[0] is False
    assert ng.is_candidate(a, b)[0] is True

    # primary-only (same document number, nothing else strong) → rejected (needs >=2 strong).
    c = _nf("c", "w/C.md", project="25-1", document_number="RFI-100")
    d = _nf("d", "w/D.md", project="25-2", document_number="RFI-100")
    assert ng.is_candidate(c, d, mode="primary_secondary")[0] is False

    # primary + secondary(vendor) → eligible.
    e = _nf("e", "w/E.md", project="25-1", document_number="RFI-9", vendor="acme")
    f = _nf("f", "w/F.md", project="25-2", document_number="RFI-9", vendor="acme")
    assert ng.is_candidate(e, f, mode="primary_secondary")[0] is True

    # primary + project(secondary) → eligible (project counts only as the secondary, never alone).
    g = _nf("g", "w/G.md", project="25-1", document_number="RFI-5")
    h = _nf("h", "w/H.md", project="25-1", document_number="RFI-5")
    assert ng.is_candidate(g, h, mode="primary_secondary")[0] is True


def test_same_sha_alone_is_not_a_durable_candidate():
    a = _nf("a", "w/A.md", attachment_extension="pdf", attachment_sha256s=frozenset({"deadbeef"}))
    b = _nf("b", "w/B.md", attachment_extension="pdf", attachment_sha256s=frozenset({"deadbeef"}))
    ok, signals = ng.is_candidate(a, b, mode="primary_secondary")
    assert ok is False and ng.is_duplicate_pair(signals) is True


def test_duplicate_pair_with_primaries_is_still_vetoed():
    # The exact 10G bug: two duplicate email cards that ALSO share thread+subject+participant+project.
    # Duplicate evidence (same source SHA / same message-id) must veto durable eligibility anyway.
    common = {"project": "23-435-01", "thread_topic": "tt", "subject_norm": "subj",
              "participant_hashes": frozenset({"ph1"})}
    a = _nf("a", "w/A.md", source_sha256="samehash", message_id_hash="mid1", **common)
    b = _nf("b", "w/B.md", source_sha256="samehash", message_id_hash="mid1", **common)
    ok, signals = ng.is_candidate(a, b, mode="primary_secondary")
    assert ok is False  # vetoed despite same_thread_topic + same_subject_normalized primaries
    assert ng.is_duplicate_pair(signals) is True
    assert "same_source_sha256" in signals and "same_message_id_hash" in signals


def test_same_message_id_hash_pair_is_duplicate_even_without_source_sha():
    a = _nf("a", "w/A.md", thread_topic="tt", subject_norm="s", message_id_hash="mid9", project="25-1")
    b = _nf("b", "w/B.md", thread_topic="tt", subject_norm="s", message_id_hash="mid9", project="25-1")
    ok, signals = ng.is_candidate(a, b, mode="primary_secondary")
    assert ok is False and "same_message_id_hash" in signals


def test_review_only_types_are_not_apply_types():
    for t in ("same_project", "same_source_duplicate", "same_email_duplicate", "potential_duplicate"):
        assert t not in ng.APPLY_TYPES
        assert t in ng.REVIEW_ONLY_TYPES or t in ng._NON_APPLY
    # sanity: a normal semantic relationship is still applyable
    assert "same_company" in ng.APPLY_TYPES


# ---------------------------------------------------------- entry-level removal helpers (10G fix)

_BLOCK = ("# Card\n\n## Related Project\n- Detected project number: 25-1; no project record linked yet.\n\n"
          "<!-- gc-graph-links:start -->\n"
          "- [[Source Notes/Work/B__bbbbbbbb2222|B]] — same_company · qwen-vetted · confidence 0.90\n"
          "- [[Source Notes/Work/C__cccccccc3333|C]] — supports_or_explains · qwen-vetted · confidence 0.85\n"
          "<!-- gc-graph-links:end -->\n")


def test_remove_related_link_removes_only_the_targeted_entry():
    out, reason = ng.remove_related_link(_BLOCK, target_rel="Source Notes/Work/B__bbbbbbbb2222.md")
    assert reason == "removed"
    assert "B__bbbbbbbb2222" not in out and "C__cccccccc3333" in out  # only B dropped
    assert out.count(ng.REL_BLOCK_BEGIN) == 1 and out.count(ng.REL_BLOCK_END) == 1


def test_remove_related_link_removes_block_when_last_entry_gone():
    one, _ = ng.remove_related_link(_BLOCK, target_rel="Source Notes/Work/C__cccccccc3333.md")
    out, reason = ng.remove_related_link(one, target_rel="Source Notes/Work/B__bbbbbbbb2222.md")
    assert reason == "emptied_removed"
    assert ng.REL_BLOCK_BEGIN not in out and ng.REL_BLOCK_END not in out
    assert "## Related Project" in out  # section + placeholder preserved
    assert "no project record linked yet" in out


def test_remove_related_link_target_not_found_and_absent_and_ambiguous():
    assert ng.remove_related_link(_BLOCK, target_rel="Source Notes/Work/Z__zzzzzzzz9999.md")[1] == \
        "target_not_found"
    assert ng.remove_related_link("# no block\n", target_rel="x.md")[1] == "absent"
    dupd = _BLOCK + "\n" + ng.REL_BLOCK_BEGIN + "\n" + ng.REL_BLOCK_END + "\n"
    assert ng.remove_related_link(dupd, target_rel="x.md") == (None, "ambiguous_existing_block")


def test_remove_frontmatter_tags_removes_only_named_tags():
    text = ("---\nnote_type: source_card\ntags:\n  - source/type/correspondence\n"
            "  - related/company\n  - review/qwen-vetted\n  - project/23-435-01\n---\n# x\n")
    out, reason = ng.remove_frontmatter_tags(text, sorted(ng.RELATED_TAGS | {"review/qwen-vetted"}))
    assert reason == "removed"
    assert "- related/company" not in out and "- review/qwen-vetted" not in out
    assert "- source/type/correspondence" in out and "- project/23-435-01" in out  # kept


# --------------------------------------------------------------------- bounded selection (run)

def test_bounded_selection_excludes_other_project(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    # assign a shared project to the two subcontracts and a different one to the misc note
    facts = {}
    for p in (env["vault"] / "Source Notes" / "Work").glob("*.md"):
        r = "Source Notes/Work/" + p.name
        proj = "23-435-01" if "Subcontract" in p.name else "99-000-00"
        facts[r] = _nf(p.stem, r, project=proj, vendor="acme")
    monkeypatch.setattr(ng, "note_fact_from", lambda repo, row, text: facts[row["note_rel_path"]])

    def _boom(model, timeout):
        raise AssertionError("no Ollama in a no-vet dry run")

    rc, out = _run(_args(env, project_number="23-435-01"), capsys, client_factory=_boom)
    assert rc == 0
    assert out["eligibility_mode"] == "primary_secondary"
    assert out["notes_selected"] == 2  # the two same-project subcontracts
    assert out["excluded_outside_project"] == 1  # the other-project misc note
    # same_vendor + same_project are BOTH secondary → no primary → no durable candidate.
    assert out["candidate_pairs"] == 0


def test_lineage_pair_excluded(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    cards = sorted((env["vault"] / "Source Notes" / "Work").glob("*Subcontract*.md"))
    card_a, card_b = cards[0], cards[1]
    rel_a = "Source Notes/Work/" + card_a.name
    rel_b = "Source Notes/Work/" + card_b.name
    # make A an attachment whose parent-email card is B (direct lineage) — written into A's card text.
    card_a.write_text(card_a.read_text()
                      + f"\n- Parent email card: [[{rel_b[:-3]}|B]]\n", encoding="utf-8")

    facts = {
        rel_a: _nf("A", rel_a, project="25-244", vendor="acme", document_number="RFI-1",
                   attachment_extension="pdf", parent_email_hash="H"),
        rel_b: _nf("B", rel_b, project="25-244", vendor="acme", document_number="RFI-1",
                   thread_topic="tt"),
    }
    for p in (env["vault"] / "Source Notes" / "Work").glob("*.md"):
        r = "Source Notes/Work/" + p.name
        facts.setdefault(r, _nf(p.stem, r, project="25-999"))

    monkeypatch.setattr(ng, "note_fact_from", lambda repo, row, text: facts[row["note_rel_path"]])
    rc, out = _run(_args(env, project_number="25-244"), capsys,
                   client_factory=lambda m, t: _FakeClient())
    assert rc == 0
    assert out["notes_selected"] == 2  # 25-999 misc excluded by the project filter
    assert out["excluded_outside_project"] == 1
    assert out["lineage_pairs_excluded"] == 1  # A<->its own parent B removed
    assert out["candidate_pairs"] == 0  # the only eligible pair was the excluded lineage pair


def test_duplicate_sha_review_only_counted(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    work = sorted((env["vault"] / "Source Notes" / "Work").glob("*Subcontract*.md"))
    rels = ["Source Notes/Work/" + p.name for p in work]
    facts = {
        rels[0]: _nf("A", rels[0], project="25-244", attachment_extension="pdf",
                     attachment_sha256s=frozenset({"dup"})),
        rels[1]: _nf("B", rels[1], project="25-244", attachment_extension="pdf",
                     attachment_sha256s=frozenset({"dup"})),
    }
    for p in (env["vault"] / "Source Notes" / "Work").glob("*.md"):
        r = "Source Notes/Work/" + p.name
        facts.setdefault(r, _nf(p.stem, r, project="25-999"))

    monkeypatch.setattr(ng, "note_fact_from", lambda repo, row, text: facts[row["note_rel_path"]])
    rc, out = _run(_args(env, project_number="25-244"), capsys, client_factory=lambda m, t: None)
    assert rc == 0
    assert out["duplicate_review_candidates"] == 1  # same-content pair, no durable basis
    assert out["candidate_pairs"] == 0  # never a durable candidate on sha alone


# ------------------------------------------------------------------- checkpoints / gates (apply)

def test_checkpoint_mismatch_refuses(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)  # default mode → 1 approved via _FakeClient
    rc, _ = _run(_args(env, apply=True, approved_count=2), capsys,
                 client_factory=lambda m, t: _FakeClient())
    assert rc == 3


def test_checkpoint_missing_when_approved_refuses(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, _ = _run(_args(env, apply=True, approved_count=None), capsys,
                 client_factory=lambda m, t: _FakeClient())
    assert rc == 3


def test_max_apply_relationships_cap_refuses(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, _ = _run(_args(env, apply=True, approved_count=1, max_apply_relationships=0), capsys,
                 client_factory=lambda m, t: _FakeClient())
    assert rc == 3


def test_project_confirm_gate_mismatch_refuses(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, _ = _run(_args(env, apply=True, approved_count=1, project_number="25-244",
                       confirm_project_number="99-999"), capsys,
                 client_factory=lambda m, t: _FakeClient())
    assert rc == 3


def test_backlink_integrity_passes_on_apply(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, apply=True, approved_count=1), capsys,
                   client_factory=lambda m, t: _FakeClient())
    assert rc == 0
    assert out["backlink_integrity_passed"] is True
    assert out["backlinks_verified"] == out["relationships_applied"] == 1
    assert out["ollama_calls"] == out["vetted_pairs"] >= 1
    assert out["applied_relationship_types"]  # non-empty distribution, separate from basis counts
