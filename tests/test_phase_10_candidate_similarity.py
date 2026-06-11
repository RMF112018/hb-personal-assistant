"""Phase 10 V51 — advisory similarity / duplicate layer tests.

Verifies the layer emits review-only edges (never auto-merges or suppresses), clusters exact
deterministic duplicates, computes optional semantic edges from a hermetic embedder, and records
model-advised duplicates as advisory evidence only.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.construction.second_brain.local_ai.candidate_similarity import (
    build_similarity_edges,
)
from hb_assistant.retrieval.embedder import DeterministicEmbedder


def _item(cid: str, *, title: str = "", group: Optional[str] = None) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "title_redacted": title,
        "reason_redacted": "",
        "duplicate_group_key": group,
    }


def test_deterministic_group_cluster_edges() -> None:
    items = [_item("a", group="g1"), _item("b", group="g1"), _item("c", group="g2")]
    res = build_similarity_edges(items, brief_date="2026-06-11")
    methods = {e["similarity_method"] for e in res["edges"]}
    assert "deterministic_group_key" in methods
    edge = next(e for e in res["edges"] if e["similarity_method"] == "deterministic_group_key")
    assert edge["similarity_score"] == 1.0
    assert edge["review_recommendation"] == "review_duplicate_candidate"


def test_edges_are_review_only_never_merge() -> None:
    items = [_item("a", group="g1"), _item("b", group="g1")]
    res = build_similarity_edges(items, brief_date="2026-06-11")
    assert res["edges"]
    for e in res["edges"]:
        assert e["review_recommendation"] == "review_duplicate_candidate"
        # No edge carries any merge/suppress directive — only review evidence.
        assert "merge" not in e and "suppress" not in e


def test_normalized_text_match_clusters() -> None:
    items = [_item("a", title="Submit the RFI"), _item("b", title="submit the rfi")]
    res = build_similarity_edges(items, brief_date="2026-06-11")
    methods = {e["similarity_method"] for e in res["edges"]}
    assert "normalized_text" in methods


def test_semantic_pass_with_deterministic_embedder() -> None:
    items = [_item("a", title="Concrete pour schedule"), _item("b", title="Concrete pour schedule")]
    res = build_similarity_edges(items, brief_date="2026-06-11", embedder=DeterministicEmbedder())
    assert res["semantic_ran"] is True
    # Identical redacted text → an edge exists (deterministic group/text or semantic).
    assert res["edge_count"] >= 1


def test_model_duplicates_are_advisory_only() -> None:
    items = [_item("a", title="x"), _item("b", title="y")]
    model_dups = [{"candidate_a_id": "a", "candidate_b_id": "b", "similarity_label": "maybe dup"}]
    res = build_similarity_edges(items, brief_date="2026-06-11", model_duplicates=model_dups)
    model_edges = [e for e in res["edges"] if e["similarity_method"] == "model_advisory"]
    assert len(model_edges) == 1
    assert model_edges[0]["review_recommendation"] == "review_duplicate_candidate"


def test_no_duplicate_pairs_when_all_distinct() -> None:
    items = [_item("a", title="alpha"), _item("b", title="beta"), _item("c", title="gamma")]
    res = build_similarity_edges(items, brief_date="2026-06-11")
    # No shared group key and distinct text → no deterministic duplicate edges.
    assert all(e["similarity_method"] != "deterministic_group_key" for e in res["edges"])
