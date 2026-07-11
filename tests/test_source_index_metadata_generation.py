"""PR 2 — metadata-first discovery, durable scan generations, path search, and weighted ranking.

Scratch DBs + temp roots only; no live/production DB, NAS, or watcher is touched.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)

_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        path = os.path.join(tempfile.mkdtemp(prefix="v120tmpl_"), "template.db")
        SQLiteMigrator(db_path=path).apply()
        _TEMPLATE_DB = path
    return _TEMPLATE_DB


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "g.db")
    shutil.copy(_template_db(), db)
    return db


def _cfg(root_dir: Path, **overrides) -> ObsidianMcpConfig:
    base = ObsidianMcpConfig(
        vault_root=str(root_dir),
        external_sources=[
            ExternalSourceRoot(source_root_key="work", path=str(root_dir), enabled=True)
        ],
        external_source_index_enabled=True,
    )
    return base.model_copy(update=overrides) if overrides else base


# ----- V122 migration: additive, idempotent, no full FTS rebuild --------------------------------
def test_v120_migration_idempotent_and_additive(tmp_path):
    db = str(tmp_path / "m.db")
    v1 = SQLiteMigrator(db_path=db).apply()
    v2 = SQLiteMigrator(db_path=db).apply()  # re-run
    assert v1 == v2 == 122
    conn = sqlite3.connect(db)
    gcols = {r[1] for r in conn.execute("PRAGMA table_info(source_index_scan_generations)")}
    scols = {r[1] for r in conn.execute("PRAGMA table_info(source_intelligence_sources)")}
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(source_intelligence_metadata)")}
    idx = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_source_index_scan_generations%'"
        )
    }
    conn.close()
    assert {
        "active_run_id",
        "owner_heartbeat_at",
        "reconcile_cursor_json",
        "policy_fingerprint",
    } <= gcols
    assert {"last_seen_generation", "last_seen_at"} <= scols
    assert {"extraction_disposition", "content_indexed_at"} <= mcols
    assert "idx_source_index_scan_generations_active" in idx


# ----- metadata-only files are discoverable by filename / folder / project ----------------------
def test_metadata_only_file_is_searchable_by_filename(tmp_path):
    root_dir = tmp_path / "root"
    (root_dir / "24-118-00 Riverside").mkdir(parents=True)
    # A PDF is metadata-only by default (parser opt-in off): no content extracted, but it must be
    # findable by filename, folder, and project number.
    pdf = root_dir / "24-118-00 Riverside" / "ProjectCharter.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.scan_source_root(r, repo, _cfg(root_dir))

    # extracted no content, but a path FTS row exists (empty excerpt).
    conn = sqlite3.connect(db)
    disp = conn.execute(
        "SELECT extraction_disposition FROM source_intelligence_metadata"
    ).fetchone()[0]
    txt = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    fts_excerpt = conn.execute("SELECT text_excerpt FROM source_intelligence_fts").fetchone()[0]
    conn.close()
    assert disp == "metadata_only"
    assert txt == 0  # no content extracted
    assert (fts_excerpt or "") == ""  # path row, empty content

    by_name = repo.search_sources("ProjectCharter")
    by_folder = repo.search_sources("Riverside")
    by_project = repo.search_sources("24-118-00")
    assert any("ProjectCharter.pdf" in hit["path"] for hit in by_name), by_name
    assert any("Riverside" in hit["path"] for hit in by_folder), by_folder
    assert any("24-118-00" in hit["path"] for hit in by_project), by_project

    # A metadata-only path row must NOT count as content-searchable.
    counts = repo.content_status_counts("work")
    assert counts["metadata_searchable"] == 1
    assert counts["content_searchable"] == 0
    assert counts["intentional_metadata_only"] == 1


# ----- weighted BM25: a filename match outranks a deep body-frequency match ----------------------
def test_weighted_rank_prefers_path_over_body(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    # File A: the term "budget" only in the FILENAME. File B: "budget" several times in the BODY but
    # not the name. Filler files (no "budget") give the term real IDF. Weighted BM25 (rel_path:8 >
    # text_excerpt:1) must rank the filename match first so path/filename hits are not buried under
    # body-frequency. These weights are locked by this test.
    (root_dir / "budget.txt").write_text("quarterly figures for the site")
    (root_dir / "notes.txt").write_text("budget " * 8 + "meeting notes")
    for i in range(8):
        (root_dir / f"filler{i}.txt").write_text(f"content number {i} about concrete and steel")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.scan_source_root(r, repo, _cfg(root_dir))

    hits = repo.search_sources("budget", limit=10)
    assert hits, hits
    assert hits[0]["path"] == "budget.txt", [h["path"] for h in hits]


# ----- metadata-first: root scan is path-searchable only; body search needs targeted extraction -----
def test_root_scan_path_only_then_targeted_body_searchable(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "meeting-minutes.txt"
    f.write_text("the concrete pour is scheduled for friday")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.scan_source_root(r, repo, _cfg(root_dir))

    # After a metadata-first scan: findable by PATH/filename, but NOT by body, and no content extracted.
    assert any("meeting-minutes.txt" in h["path"] for h in repo.search_sources("minutes"))
    assert not any("meeting-minutes.txt" in h["path"] for h in repo.search_sources("concrete"))
    counts = repo.content_status_counts("work")
    assert counts["content_searchable"] == 0 and counts["content_extracted"] == 0
    assert counts["content_pending"] == 1  # eligible, awaiting targeted extraction

    # Targeted extraction makes the body searchable.
    si.index_source_file(f, r, repo, _cfg(root_dir))
    assert any("meeting-minutes.txt" in h["path"] for h in repo.search_sources("concrete"))
    counts2 = repo.content_status_counts("work")
    assert counts2["content_searchable"] == 1 and counts2["content_extracted"] == 1


# ----- generation lifecycle authority: stale-lease release preserves the cursor -----------------
def test_stale_lease_release_preserves_cursor_not_abandon(tmp_path):
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    fp, rph = "fp", "rph"
    g = gr.begin_generation_pass("work", "runA", policy_fingerprint=fp, root_path_hash=rph)
    gid = g["generation_id"]
    gr.mark_partial(gid, "runA", cursor_json='{"v":1,"frames":[{"directory":"","after_name":"X"}]}')
    # Re-claim, then simulate the owner being killed (stale heartbeat) mid-pass.
    g2 = gr.begin_generation_pass("work", "runB", policy_fingerprint=fp, root_path_hash=rph)
    assert g2["resumed"] and g2["cursor_json"]
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_index_scan_generations SET owner_heartbeat_at='2000-01-01T00:00:00+00:00' "
        "WHERE generation_id=?",
        (gid,),
    )
    conn.commit()
    conn.close()
    g3 = gr.begin_generation_pass("work", "runC", policy_fingerprint=fp, root_path_hash=rph)
    assert g3 is not None
    assert g3["generation_id"] == gid  # same generation, NOT abandoned
    assert g3["status"] == "running" and g3["cursor_json"]  # cursor preserved
    # And exactly one active generation exists for the root.
    n = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_index_scan_generations WHERE root_key='work' "
            "AND status IN ('running','partial','reconcile_pending')"
        )
        .fetchone()[0]
    )
    assert n == 1


def test_live_owner_conflict_is_none(tmp_path):
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    g = gr.begin_generation_pass("work", "run1", policy_fingerprint="fp", root_path_hash="rph")
    assert g is not None
    # A second start while the first still holds a fresh lease is a retryable conflict (None).
    assert (
        gr.begin_generation_pass("work", "run2", policy_fingerprint="fp", root_path_hash="rph")
        is None
    )


# ----- bounded passes resume the SAME generation to completion -----------------------------------
def test_bounded_passes_resume_one_generation(tmp_path):
    root_dir = tmp_path / "root"
    (root_dir / "sub").mkdir(parents=True)
    for i in range(6):
        (root_dir / f"f{i}.txt").write_text(f"x{i}")
    (root_dir / "sub" / "deep.txt").write_text("deep")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    # Observe only 2 files per pass -> several partial passes, one generation, then completion.
    cfg = _cfg(root_dir, source_index_scan_observed_files_per_pass=2)
    passes = 0
    while True:
        rep = si.scan_source_root(r, repo, cfg)
        passes += 1
        if rep.generation_status == "completed":
            break
        assert rep.generation_status == "partial"
        assert passes < 20  # forward progress guaranteed
    gens = SourceIndexScanGenerationsRepository(db).list_generations("work")
    assert len(gens) == 1 and gens[0]["status"] == "completed"
    # All 7 files were metadata-indexed exactly once (searchable by filename).
    n = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE source_root_key='work' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n == 7
    assert passes >= 3  # genuinely spanned multiple bounded passes


# ----- a partial (incomplete) generation reconciles NOTHING; a complete one deletes --------------
def test_partial_generation_deletes_nothing_complete_deletes(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(4):
        (root_dir / f"f{i}.txt").write_text(f"x{i}")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.scan_source_root(r, repo, _cfg(root_dir))  # full index, generation completed

    # Remove one file, then run a BOUNDED pass that cannot complete the walk.
    (root_dir / "f0.txt").unlink()
    rep = si.scan_source_root(r, repo, _cfg(root_dir, source_index_scan_observed_files_per_pass=1))
    assert rep.generation_status == "partial"
    # Reconciliation must NOT have run on the incomplete generation — the removed file survives.
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='f0.txt'")
        .fetchone()[0]
    )
    assert d == 0, "partial generation must not delete a removed file"

    # Finish the generation → the complete walk reconciles the deletion.
    while (
        si.scan_source_root(
            r, repo, _cfg(root_dir, source_index_scan_observed_files_per_pass=1)
        ).generation_status
        != "completed"
    ):
        pass
    d2 = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='f0.txt'")
        .fetchone()[0]
    )
    assert d2 == 1, "complete generation reconciles the deletion"


# ----- high-fanout FAILS the generation (no reconciliation, no false delete) ---------------------
def test_high_fanout_fails_generation_no_delete(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(4):
        (root_dir / f"pre{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.scan_source_root(r, repo, _cfg(root_dir))  # baseline complete

    # Now blow past the fanout cap in the root directory and remove a prior file.
    for i in range(30):
        (root_dir / f"big{i}.txt").write_text("y")
    (root_dir / "pre0.txt").unlink()
    rep = si.scan_source_root(r, repo, _cfg(root_dir, source_index_directory_fanout_limit=10))
    assert rep.generation_status == "failed"
    assert rep.error_code == "directory_fanout_limit"
    g = SourceIndexScanGenerationsRepository(db).list_generations("work")[0]
    assert g["status"] == "failed"
    # No reconciliation ran on the failed generation → the removed file is NOT deleted.
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='pre0.txt'")
        .fetchone()[0]
    )
    assert d == 0


# ----- no absolute host path leaks into generation state or the cursor --------------------------
def test_no_absolute_path_in_generation_state(tmp_path):
    root_dir = tmp_path / "root"
    (root_dir / "a").mkdir(parents=True)
    (root_dir / "a" / "x.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.scan_source_root(r, repo, _cfg(root_dir, source_index_scan_observed_files_per_pass=1))
    row = (
        sqlite3.connect(db)
        .execute(
            "SELECT cursor_json, reconcile_cursor_json, policy_fingerprint, root_path_hash "
            "FROM source_index_scan_generations WHERE root_key='work'"
        )
        .fetchone()
    )
    blob = " ".join(str(x) for x in row if x is not None)
    assert str(root_dir) not in blob  # never an absolute host path
    assert str(tmp_path) not in blob
