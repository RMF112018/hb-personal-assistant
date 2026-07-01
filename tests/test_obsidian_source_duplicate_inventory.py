"""Phase 10H — duplicate-review inventory (count-only, creates nothing).

Exercises `_duplicate_inventory`: unique pair count, per-signal contribution (a multi-signal pair counts
once overall but in each signal), connected-component clusters, and that it modifies no cards (detail
rows only). Pure over synthetic NoteFacts.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tests.test_obsidian_source_graph_apply import _nf

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_note_correct_graph.py"
_spec = importlib.util.spec_from_file_location("correct_note_graph_10h_dup", _SCRIPT)
assert _spec and _spec.loader
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


def _facts():
    return {
        # A,B share BOTH source SHA and message-id → one pair, two signals
        "A": _nf("A", "w/A.md", source_sha256="s1", message_id_hash="m1"),
        "B": _nf("B", "w/B.md", source_sha256="s1", message_id_hash="m1"),
        # E shares source SHA with A,B → extends the cluster {A,B,E}
        "E": _nf("E", "w/E.md", source_sha256="s1"),
        # C,D share an attachment SHA → separate cluster {C,D}
        "C": _nf("C", "w/C.md", attachment_sha256s=frozenset({"att1"})),
        "D": _nf("D", "w/D.md", attachment_sha256s=frozenset({"att1"})),
        # F is unique — never in a pair
        "F": _nf("F", "w/F.md", source_sha256="unique"),
    }


def test_inventory_counts_unique_pairs_and_per_signal_and_clusters():
    detail: list = []
    stats = cg._duplicate_inventory(_facts(), detail)
    # unique pairs: (A,B),(A,E),(B,E),(C,D) = 4
    assert stats["duplicate_review_pairs"] == 4
    # per-signal (a pair contributes to each of its signals)
    assert stats["same_source_sha256_pairs"] == 3  # (A,B),(A,E),(B,E)
    assert stats["same_email_message_id_pairs"] == 1  # (A,B) only
    assert stats["same_attachment_sha_pairs"] == 1  # (C,D)
    # clusters
    assert stats["duplicate_clusters"] == 2  # {A,B,E} and {C,D}
    assert stats["largest_cluster_size"] == 3  # {A,B,E}


def test_multi_signal_pair_counts_once_in_total():
    # A,B share two signals; the total unique-pair count must not double-count them.
    facts = {"A": _nf("A", "w/A.md", source_sha256="s", message_id_hash="m"),
             "B": _nf("B", "w/B.md", source_sha256="s", message_id_hash="m")}
    stats = cg._duplicate_inventory(facts, [])
    assert stats["duplicate_review_pairs"] == 1
    assert stats["same_source_sha256_pairs"] == 1 and stats["same_email_message_id_pairs"] == 1


def test_inventory_creates_nothing_and_only_writes_detail_rows():
    detail: list = []
    facts = _facts()
    snapshot = dict(facts)
    cg._duplicate_inventory(facts, detail)
    assert facts == snapshot  # facts unchanged (no links/tags/deletes/merges)
    assert len(detail) == 1 and set(detail[0]) == {"duplicate_pairs", "clusters"}


def test_no_duplicates_is_zeroed():
    facts = {"A": _nf("A", "w/A.md", source_sha256="a"),
             "B": _nf("B", "w/B.md", source_sha256="b")}
    stats = cg._duplicate_inventory(facts, [])
    assert stats["duplicate_review_pairs"] == 0 and stats["duplicate_clusters"] == 0
    assert stats["largest_cluster_size"] == 0
