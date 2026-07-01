"""Phase 10I — read-only graph review surfaces (counts + sanitized report; executes nothing).

Covers the analyzers in scripts/obsidian_source_graph_review.py: duplicate-cluster inventory, existing
gc-graph-links integrity (hardened for malformed lines / unknown types / duplicate entries / missing
reciprocals / ambiguous blocks / invalid tags), deterministic relationship candidates (zero Ollama),
identity scorecard, isolated high-value counts, and the count-only/sanitized report renderer. Pure
functions over synthetic facts + card text, plus a couple of main()/run() integration checks proving
no vault/DB/queue/runtime-JSON change.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from hb_assistant.obsidian_mcp import source_note_graph as ng
from tests.test_obsidian_source_graph_apply import _nf
from tests.test_obsidian_source_note_graph import _env

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_graph_review.py"
_spec = importlib.util.spec_from_file_location("graph_review_10i", _SCRIPT)
assert _spec and _spec.loader
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)

_B, _E = ng.REL_BLOCK_BEGIN, ng.REL_BLOCK_END


def _links_card(*lines: str) -> str:
    body = "\n".join(lines)
    return f"# Card\n\n{_B}\n{body}\n{_E}\n"


def _link(target_no_md: str, rtype: str, disp: str = "T") -> str:
    return f"- [[{target_no_md}|{disp}]] — {rtype} · qwen-vetted · confidence 0.90"


# --------------------------------------------------------------------------- duplicate clusters

def test_duplicate_clusters_counts_pairs_signals_buckets_and_stable_ids():
    facts = {
        "A": _nf("A", "w/A.md", source_sha256="s1", message_id_hash="m1"),
        "B": _nf("B", "w/B.md", source_sha256="s1", message_id_hash="m1"),
        "E": _nf("E", "w/E.md", source_sha256="s1"),
        "C": _nf("C", "w/C.md", attachment_sha256s=frozenset({"att1"})),
        "D": _nf("D", "w/D.md", attachment_sha256s=frozenset({"att1"})),
        "F": _nf("F", "w/F.md", source_sha256="uniq"),
    }
    detail: list = []
    stats = gr._duplicate_clusters(facts, detail)
    assert stats["duplicate_review_pairs"] == 4  # (A,B),(A,E),(B,E),(C,D)
    assert stats["same_source_sha256_pairs"] == 3 and stats["same_email_message_id_pairs"] == 1
    assert stats["same_attachment_sha_pairs"] == 1
    assert stats["duplicate_clusters"] == 2 and stats["largest_cluster_size"] == 3
    assert stats["clusters_size_2"] == 1 and stats["clusters_size_3_to_5"] == 1
    assert stats["clusters_size_6_plus"] == 0
    # deterministic cluster ids (12-char hashes) — recompute identically, no card change
    ids1 = detail[-1]["cluster_ids"]
    detail2: list = []
    gr._duplicate_clusters(dict(facts), detail2)
    assert detail2[-1]["cluster_ids"] == ids1 and len(ids1) == 2


# --------------------------------------------------------------------------- existing-link integrity (hardened)

def test_existing_links_reciprocal_pair_passes():
    facts = {"A": _nf("A", "w/A.md"), "B": _nf("B", "w/B.md")}
    text = {"A": _links_card(_link("w/B", "same_company")),
            "B": _links_card(_link("w/A", "same_company"))}
    st = gr._existing_links(facts, text, [])
    assert st["graph_blocks"] == 2 and st["relationships"] == 2
    assert st["reciprocal_pass"] is True and st["one_way_links"] == 0
    assert st["invalid_relationship_types"] == 0


def test_existing_links_detects_missing_reciprocal():
    facts = {"A": _nf("A", "w/A.md"), "B": _nf("B", "w/B.md")}
    text = {"A": _links_card(_link("w/B", "same_company")), "B": "# B (no block)\n"}
    st = gr._existing_links(facts, text, [])
    assert st["one_way_links"] == 1 and st["reciprocal_pass"] is False


def test_existing_links_detects_unknown_type_duplicate_entry_and_malformed_line():
    facts = {"A": _nf("A", "w/A.md"), "B": _nf("B", "w/B.md")}
    text = {
        "A": _links_card(
            _link("w/B", "bogus_type"),          # unknown relationship type
            _link("w/B", "bogus_type"),          # exact duplicate entry
            "- a malformed line with no wiki target and no rel type",  # malformed → no target/type
        ),
        "B": _links_card(_link("w/A", "same_company")),
    }
    st = gr._existing_links(facts, text, [])
    assert st["duplicate_entries"] == 1
    # bogus_type ×2 + the malformed line (rtype None) all count as invalid types
    assert st["invalid_relationship_types"] == 3


def test_existing_links_detects_durable_same_project_and_duplicate_types():
    facts = {"A": _nf("A", "w/A.md"), "B": _nf("B", "w/B.md")}
    text = {"A": _links_card(_link("w/B", "same_project"), _link("w/B", "same_source_duplicate")),
            "B": _links_card(_link("w/A", "same_company"))}
    st = gr._existing_links(facts, text, [])
    assert st["durable_same_project_links"] == 1 and st["durable_duplicate_links"] == 1


def test_existing_links_detects_ambiguous_block_and_invalid_tags():
    facts = {"A": _nf("A", "w/A.md")}
    ambiguous = f"# A\n\n{_B}\n{_link('w/x', 'same_company')}\n{_B}\n{_E}\n"  # two start markers
    text = {"A": ambiguous}
    st = gr._existing_links(facts, text, [])
    assert st["ambiguous_graph_blocks"] == 1 and st["graph_blocks"] == 0  # ambiguous → not a valid block
    fm = ("---\ntags:\n  - related/company\n  - related/bogus\n  - review/qwen-vetted\n"
          "  - review/not-a-real-review-tag\n---\n# A\n")
    st2 = gr._existing_links({"A": _nf("A", "w/A.md")}, {"A": fm}, [])
    assert st2["invalid_tags"] == 2  # related/bogus + review/not-a-real-review-tag (valid ones ignored)


# --------------------------------------------------------------------------- relationship candidates (no model)

def test_relationship_candidates_are_deterministic_zero_ollama():
    facts = {
        # primary + secondary → eligible in both modes
        "A": _nf("A", "w/A.md", thread_topic="tt", procore_project_id="P"),
        "B": _nf("B", "w/B.md", thread_topic="tt", procore_project_id="P"),
        # duplicate pair → review-only, vetoed from candidacy
        "C": _nf("C", "w/C.md", source_sha256="dup"),
        "D": _nf("D", "w/D.md", source_sha256="dup"),
        # project-only strong signal (secondary only, no primary) → not default-eligible
        "E": _nf("E", "w/E.md", procore_project_id="Q"),
        "G": _nf("G", "w/G.md", procore_project_id="Q"),
    }
    st = gr._relationship_candidates(facts)
    assert st["ollama_calls"] == 0
    assert st["primary_secondary_eligible"] == 1  # (A,B)
    assert st["duplicate_review_pairs"] == 1       # (C,D)
    assert st["project_only_rejected"] >= 1        # (E,G)
    assert st["would_require_human_review"] == st["candidate_pairs"]


# --------------------------------------------------------------------------- identity scorecard

def _idblock(num="23-435-01", key="tropical", procore="2525840",
             name="Tropical World Nursery Senior Living Facility") -> str:
    return (f'<!-- hb-project-identity:start project_number="{num}" project_key="{key}" '
            f'procore_project_id="{procore}" -->\n'
            f"- Resolved project: {num} · {key} · {name}\n<!-- hb-project-identity:end -->\n")


def _idcard(*, fm_key="tropical", placeholder=False, blocks=1, resolve_key="tropical",
            resolve_num="23-435-01", procore="2525840") -> str:
    related = ("- Detected project number: 23-435-01; no project record linked yet.\n" if placeholder
               else "- Project: 23-435-01 — Tropical World Nursery Senior Living Facility · tropical\n")
    ids = "".join(_idblock(resolve_num, resolve_key, procore) for _ in range(blocks))
    return (f'---\nnote_type: source_card\nproject_key: "{fm_key}"\nproject_number: "23-435-01"\n'
            f"tags:\n  - project/23-435-01\n---\n# Card\n\n## Related Project\n{related}\n{ids}")


def test_identity_scorecard_counts_consistent_stale_ambiguous_missing():
    cards = {
        "A": _idcard(fm_key="tropical", placeholder=False),          # consistent
        "B": _idcard(fm_key="23-435-01", placeholder=True),          # stale fm + visible → inconsistent
        "C": _idcard(fm_key="tropical", placeholder=True),           # stale visible only → inconsistent
        "D": _idcard(blocks=2),                                      # ambiguous (2 blocks)
        "E": "---\nproject_key: x\n---\n# E\n## Related Project\n- x\n",  # missing block
        "F": _idcard(fm_key="99-000-00", resolve_key="other",
                     resolve_num="99-000-00", procore="999"),        # other project
    }
    facts = {nid: _nf(nid, f"w/{nid}.md") for nid in cards}
    st = gr._identity_quality(facts, dict(cards))
    assert st["cards_checked"] == 6
    assert st["identity_inconsistent"] == 2      # B, C
    assert st["ambiguous_identity_blocks"] == 1  # D
    assert st["missing_identity_blocks"] == 1    # E
    assert st["non_tropical_in_selection"] == 1  # F
    assert st["identity_consistent"] == 1        # A


# --------------------------------------------------------------------------- isolated high-value

def test_isolated_high_value_counts():
    facts = {
        "A": _nf("A", "w/A.md", disposition="auto_card_high", document_type="submittal"),
        "B": _nf("B", "w/B.md", disposition="auto_card_high", thread_topic="t", document_type="email"),
        "C": _nf("C", "w/C.md", disposition="metadata_only", document_type="rfi"),
        "L": _nf("L", "w/L.md", disposition="auto_card_high", document_type="rfi"),  # linked → not isolated
    }
    text = {"A": "# A\n", "B": "# B\n", "C": "# C\n",
            "L": _links_card(_link("w/A", "same_company"))}
    st = gr._isolated_high_value(facts, text)
    assert st["isolated_cards"] == 3               # A,B,C (L has a link)
    assert st["isolated_high_value_cards"] == 2    # A,B (auto_card_high); C is metadata_only
    assert st["isolated_email_cards"] == 1         # B
    assert st["isolated_submittal_or_rfi_cards"] == 2  # A(submittal), C(rfi)


# --------------------------------------------------------------------------- report renderer sanitization

def test_report_is_count_only_and_leaks_nothing():
    safe = {"mode": "review", "cards_checked": 103, "identity_consistent": 103,
            "duplicate_review_pairs": 28, "duplicate_clusters": 4, "candidate_pairs": 0,
            "ollama_calls": 0, "cards_modified": 0, "db_mutations": 0, "queue_delta": 0,
            "runtime_json_mutated": False,
            "candidate_basis_counts": {"same_procore_id": 12}}
    # sensitive-looking strings stuffed into UNKNOWN keys must never appear in the report
    safe["_leak"] = "john@example.com [[Secret Title]] /Users/bobby/vault/x.md message-id:<abc@d>"
    md = gr._render_phase10i_report(safe)
    assert "cards_checked: 103" in md and "duplicate_review_pairs: 28" in md
    assert "same_procore_id: 12" in md  # known distribution rendered
    assert "future_actions" in md and "accept_relationship" in md  # design listed
    for leak in ("john@example.com", "[[", "Secret Title", "/Users/", ".md", "message-id"):
        assert leak not in md


# --------------------------------------------------------------------------- integration (read-only, no mutation)

def _argv(env, *modes, extra=None):
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--project-number", "25-244"]
    a += list(modes)
    if extra:
        a += extra
    return a


def test_dry_run_writes_nothing_and_proves_no_mutation(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    ev = tmp_path / "ev10i"
    rc = gr.main(_argv(env, "--all", "--json-output", extra=["--evidence-dir", str(ev)]))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["mode"] == "review"
    assert out["cards_modified"] == 0 and out["db_mutations"] == 0
    assert out["queue_delta"] == 0 and out["runtime_json_mutated"] is False
    assert out["ollama_calls"] == 0
    assert not ev.exists()  # dry-run (no --write-review-report) writes nothing


def test_write_review_report_writes_only_evidence(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    ev = tmp_path / "ev10i"
    rc = gr.main(_argv(env, "--all", "--write-review-report", extra=["--evidence-dir", str(ev)]))
    capsys.readouterr()
    assert rc == 0
    assert (ev / "phase10i-review-summary-safe.json").is_file()
    assert (ev / "phase10i-review-report-safe.md").is_file()
    assert (ev / "local-sensitive" / "phase10i-review-detail-local-sensitive.json").is_file()
    # summary is count-only; re-running proves idempotence + no mutation
    safe = json.loads((ev / "phase10i-review-summary-safe.json").read_text())
    assert safe["cards_modified"] == 0 and safe["db_mutations"] == 0


def test_vet_without_confirms_refuses(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc = gr.main(_argv(env, "--all", "--vet"))
    err = capsys.readouterr().err
    assert rc == 3 and "vet requires" in err and "10J" in err


def test_no_mode_refuses(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc = gr.main(_argv(env))
    assert rc == 3 and "at least one mode" in capsys.readouterr().err
