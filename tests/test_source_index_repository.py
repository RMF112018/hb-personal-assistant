"""SourceIndexRepository: explicit FTS sync, idempotency, durable queue, domain links."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> SourceIndexRepository:
    db = str(tmp_path / "idx.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return SourceIndexRepository(db)


def _file(rel: str, *, sha: str, mtime: int, excerpt: str, project: str | None = None) -> dict:
    return {
        "source_kind": "external_file", "source_root_key": "proj", "rel_path": rel,
        "content_sha256": sha, "mtime_ns": mtime, "file_ext": rel.rsplit(".", 1)[-1],
        "project_key": project, "extraction_status": "ok",
        "text_excerpt": excerpt, "excerpt_char_count": len(excerpt),
    }


def test_upsert_and_search(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/Conduit RFI.pdf", sha="s1", mtime=1,
                                  excerpt="Underground conduit for electrical", project="tropical"))
    hits = repo.search_sources("conduit", limit=5)
    assert len(hits) == 1 and hits[0]["path"] == "a/Conduit RFI.pdf"
    assert hits[0]["result_type"] == "source"
    assert repo.search_sources("conduit", project_key="tropical")
    assert repo.search_sources("conduit", project_key="other") == []


def test_idempotency_lookup_carries_hash(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="abc", mtime=99, excerpt="hello"))
    look = repo.lookup_by_path("external_file", "a/x.md")
    assert look["content_sha256"] == "abc" and look["mtime_ns"] == 99
    assert look["fts_rowid"] is not None


def test_reindex_keeps_single_fts_row(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="s1", mtime=1, excerpt="alpha conduit"))
    repo.upsert_source_file(_file("a/x.md", sha="s2", mtime=2, excerpt="beta tunnel"))
    con = sqlite3.connect(repo.db_path)
    assert con.execute("SELECT COUNT(*) FROM source_intelligence_fts").fetchone()[0] == 1
    assert repo.search_sources("tunnel")  # new content searchable
    assert repo.search_sources("alpha") == []  # old content gone


def test_delete_removes_fts_and_marks_deleted(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="s1", mtime=1, excerpt="conduit"))
    repo.mark_deleted("external_file", "a/x.md")
    con = sqlite3.connect(repo.db_path)
    assert con.execute("SELECT COUNT(*) FROM source_intelligence_fts").fetchone()[0] == 0
    assert repo.search_sources("conduit") == []
    assert con.execute(
        "SELECT deleted FROM source_intelligence_sources WHERE rel_path='a/x.md'"
    ).fetchone()[0] == 1


def test_queue_debounce_claim_complete(repo: SourceIndexRepository) -> None:
    e1 = repo.enqueue_event(event_type="modified", rel_path="p/q.md", source_root_key="proj")
    e2 = repo.enqueue_event(event_type="modified", rel_path="p/q.md", source_root_key="proj")
    assert e1 == e2  # coalesced while queued
    claimed = repo.claim_queued(10)
    assert len(claimed) == 1 and claimed[0]["rel_path"] == "p/q.md"
    assert repo.claim_queued(10) == []  # nothing left queued
    repo.complete_event(claimed[0]["event_id"], "done")
    assert repo.index_status()["queued_count"] == 0


def test_requeue_stuck_processing(repo: SourceIndexRepository) -> None:
    repo.enqueue_event(event_type="modified", rel_path="p/q.md")
    repo.claim_queued(10)  # → processing
    con = sqlite3.connect(repo.db_path)
    # force updated_at into the past so the TTL trips
    con.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00'")
    con.commit()
    assert repo.requeue_stuck(ttl_seconds=60) == 1
    assert repo.index_status()["queued_count"] == 1


def test_domain_link_has_no_text(repo: SourceIndexRepository) -> None:
    sid = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                  domain_ref_id="msg-1", project_number="22-101-00")
    con = sqlite3.connect(repo.db_path)
    assert con.execute(
        "SELECT domain_ref_id FROM source_intelligence_sources WHERE source_id=?", (sid,)
    ).fetchone()[0] == "msg-1"
    # no text row for a link source
    assert con.execute(
        "SELECT COUNT(*) FROM source_intelligence_text WHERE source_id=?", (sid,)
    ).fetchone()[0] == 0


def test_register_roots_deactivates_removed(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="s1", mtime=1, excerpt="x"))
    repo.register_source_roots([{"source_root_key": "other", "enabled": True}])  # 'proj' removed
    con = sqlite3.connect(repo.db_path)
    assert con.execute(
        "SELECT active FROM source_intelligence_sources WHERE source_root_key='proj'"
    ).fetchone()[0] == 0
