"""N8C-7 memory repository: deterministic upsert, idempotency, supersede, provenance, stale."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import memory_models as mm
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> MemoryRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return MemoryRepository(db)


def _header(name: str = "Tropical Waters", node_type: str = "project", digest: str = "d1") -> dict:
    return {"node_id": mm.compute_node_id(node_type, mm.normalize_memory_name(name), None),
            "node_type": node_type, "canonical_name": name,
            "normalized_name": mm.normalize_memory_name(name), "domain": None,
            "aliases": ["TWN"], "review_tier": "trusted_source_backed", "confidence": 0.9,
            "input_digest": digest, "created_by": "cli"}


def _mention(node_id: str, claim_id: str = "c1") -> dict:
    return mm.MemoryMention(mention_type="claim_subject", claim_id=claim_id, source_id="s1",
                            evidence_excerpt="ev", confidence=0.8,
                            review_tier="trusted_source_backed").to_row(node_id)


def test_node_id_determinism() -> None:
    a = mm.compute_node_id("project", mm.normalize_memory_name("  Tropical  Waters! "), None)
    b = mm.compute_node_id("project", mm.normalize_memory_name("tropical waters"), None)
    assert a == b  # normalized identity is stable


def test_upsert_node_idempotent(repo) -> None:
    h = _header()
    assert repo.upsert_node(h)["created"] is True
    assert repo.upsert_node(h)["created"] is False  # same node_id -> update, no duplicate
    assert repo.count_nodes() == 1


def test_upsert_mention_idempotent(repo) -> None:
    h = _header()
    repo.upsert_node(h)
    m = _mention(h["node_id"])
    assert repo.upsert_mention(m)["created"] is True
    assert repo.upsert_mention(m)["created"] is False  # deterministic mention_id, no duplicate
    repo.refresh_node_counts(h["node_id"])
    n = repo.get_node(h["node_id"])
    assert n["mention_count"] == 1 and n["source_count"] == 1 and n["claim_count"] == 1


def test_persist_compilation_supersede_on_new_input(repo) -> None:
    h = _header()
    repo.upsert_node(h)
    c1 = {"compilation_id": mm.compute_compilation_id(h["node_id"], "node_summary", "d1"),
          "node_id": h["node_id"], "compile_type": "node_summary", "summary": "s1",
          "input_digest": "d1", "review_tier": "trusted_source_backed", "mention_count": 1}
    assert repo.persist_compilation(c1)["created"] is True
    # Same input -> same id -> reused, not duplicated.
    assert repo.persist_compilation(c1)["reused"] is True
    # Changed input -> new compilation, prior superseded.
    c2 = {**c1, "compilation_id": mm.compute_compilation_id(h["node_id"], "node_summary", "d2"),
          "input_digest": "d2"}
    assert repo.persist_compilation(c2)["created"] is True
    comps = repo.list_compilations(h["node_id"])
    statuses = sorted(c["status"] for c in comps)
    assert statuses == ["built", "superseded"]


def test_mention_requires_provenance() -> None:
    with pytest.raises(mm.MemoryValidationError, match="provenance"):
        mm.MemoryMention(mention_type="claim_subject").to_row("nid")


def test_mark_node_stale_explicit(repo) -> None:
    h = _header()
    repo.upsert_node(h)
    assert repo.mark_node_stale(h["node_id"], detail="drift") is True
    assert repo.get_node(h["node_id"])["status"] == "stale"
    assert "marked_stale" in [e["event_type"] for e in repo.list_events(h["node_id"])]
    assert repo.mark_node_stale("nope") is False


def test_search_nodes(repo) -> None:
    repo.upsert_node(_header())
    assert len(repo.search_nodes("tropical")) == 1
    assert repo.search_nodes("nonexistent") == []
