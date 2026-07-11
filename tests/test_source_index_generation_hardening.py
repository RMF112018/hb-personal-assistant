"""PR 2 review-fix regression coverage — atomic batch commit, lease-loss abort, legacy fast-skip repair,
disposition/sensitivity transitions, cursor validation, three-outcome reconciliation, content
preservation vs invalidation, generation-derived health, and additive search result fields.

Scratch DBs + temp roots only; no live/production DB, NAS, or watcher is touched.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_health_service import source_index_health
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)

_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        path = os.path.join(tempfile.mkdtemp(prefix="v120hz_"), "template.db")
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


def _run_to_completion(r, repo, cfg, *, cap: int = 50):
    rep = None
    for _ in range(cap):
        rep = si.scan_source_root(r, repo, cfg)
        if rep.generation_status == "completed":
            return rep
    raise AssertionError(f"did not complete; last={rep.generation_status if rep else None}")


# ===== Finding 1: atomic batch commit + lease-guard rowcount =====================================
def test_advance_cursor_returns_zero_when_lease_lost(tmp_path):
    """A cursor advance under a run that no longer owns the generation affects 0 rows (silent-loss guard)."""
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    g = gr.begin_generation_pass("work", "run1", policy_fingerprint="fp", root_path_hash="rph")
    gid = g["generation_id"]
    # A takeover: a different run becomes the owner.
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_index_scan_generations SET active_run_id='run2' WHERE generation_id=?",
        (gid,),
    )
    conn.commit()
    conn.close()
    assert gr.advance_cursor(gid, "run1", cursor_json='{"v":1}') == 0
    # The rightful owner still advances.
    assert gr.advance_cursor(gid, "run2", cursor_json='{"v":1}') == 1


def test_scan_aborts_as_conflict_when_lease_lost_midbatch(tmp_path):
    """If the cursor advance reports 0 (lease taken over) the pass aborts as a retryable conflict and
    does NOT keep writing under a lease it no longer holds."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(3):
        (root_dir / f"f{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))

    class _LeaseLossGen(SourceIndexScanGenerationsRepository):
        def advance_cursor(self, *a, **k):  # noqa: ANN002
            return 0  # simulate a stale-lease takeover

    rep = si.scan_source_root(r, repo, _cfg(root_dir), genrepo=_LeaseLossGen(db))
    assert rep.conflict is True
    assert rep.generation_status == "conflict"
    assert rep.error_code == "lease_lost"


def test_batch_metadata_and_cursor_commit_atomically(tmp_path):
    """A failure at the cursor checkpoint rolls the WHOLE batch back — no metadata is persisted without
    its cursor advance (the cursor can never point past uncommitted metadata)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(3):
        (root_dir / f"f{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))

    class _RaiseAdvance(SourceIndexScanGenerationsRepository):
        def advance_cursor(self, *a, **k):  # noqa: ANN002
            raise RuntimeError("boom-at-checkpoint")

    with pytest.raises(RuntimeError):
        si.scan_source_root(r, repo, _cfg(root_dir), genrepo=_RaiseAdvance(db))
    # The batch rolled back: NO source rows and NO advanced cursor persisted.
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM source_intelligence_sources").fetchone()[0]
    cursor_json = conn.execute(
        "SELECT cursor_json FROM source_index_scan_generations WHERE root_key='work'"
    ).fetchone()[0]
    conn.close()
    assert n == 0, "metadata must not persist when the cursor checkpoint failed"
    assert cursor_json is None


# ===== Finding 2: legacy NULL disposition + missing path-FTS repaired on an unchanged scan ========
def test_unchanged_scan_repairs_missing_path_fts_and_disposition(tmp_path):
    """A legacy row (no path-FTS row, NULL disposition) whose file is unchanged is NOT fast-skipped —
    it is repaired so it becomes path-searchable and its disposition backfills."""
    root_dir = tmp_path / "root"
    (root_dir / "24-118-00").mkdir(parents=True)
    pdf = root_dir / "24-118-00" / "Charter.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))

    # Degrade the row to a PR-1-style metadata-only row: drop its FTS row + NULL fts_rowid + disposition.
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM source_intelligence_fts")
    conn.execute(
        "UPDATE source_intelligence_metadata SET fts_rowid=NULL, extraction_disposition=NULL"
    )
    conn.commit()
    conn.close()
    assert repo.search_sources("Charter") == []  # not searchable while un-repaired

    # A rescan (file unchanged) must REPAIR it rather than fast-skip it.
    _run_to_completion(r, repo, _cfg(root_dir))
    conn = sqlite3.connect(db)
    disp, fts_rowid = conn.execute(
        "SELECT extraction_disposition, fts_rowid FROM source_intelligence_metadata"
    ).fetchone()
    conn.close()
    assert disp == "metadata_only"
    assert fts_rowid is not None
    assert any("Charter.pdf" in h["path"] for h in repo.search_sources("Charter"))


# ===== Finding 4 + 5: disposition transition clears content; unchanged repair preserves it ========
def test_disposition_transition_invalidates_content_keeps_path(tmp_path):
    """A policy change that flips a file's disposition content→too_large clears stale extracted content
    but keeps the path/filename FTS row (discoverability invariant)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "spec.txt"
    f.write_text("the tunnel lining detail")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    si.index_source_file(f, r, repo, _cfg(root_dir))  # targeted extract → content present
    assert any("spec.txt" in h["path"] for h in repo.search_sources("tunnel"))

    # Now a policy change (max_file_mb=0) reclassifies the file as too_large without editing it.
    _run_to_completion(r, repo, _cfg(root_dir, max_file_mb=0))
    conn = sqlite3.connect(db)
    n_text = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    disp = conn.execute(
        "SELECT extraction_disposition FROM source_intelligence_metadata"
    ).fetchone()[0]
    conn.close()
    assert n_text == 0, "stale content cleared on a content->too_large transition"
    assert disp == "too_large"
    # Path search still works (content search does not).
    assert any("spec.txt" in h["path"] for h in repo.search_sources("spec"))
    assert not any("spec.txt" in h["path"] for h in repo.search_sources("tunnel"))


def test_preserve_content_repair_keeps_extracted_text(tmp_path):
    """A metadata REPAIR of a physically unchanged file preserves valid extracted text/chunks — a
    re-observation can never destroy content (finding 5)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "log.txt"
    f.write_text("crane erection sequence")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    gen = SourceIndexScanGenerationsRepository(db).begin_generation_pass(
        "work", "runx", policy_fingerprint="fp", root_path_hash="rph"
    )
    gid = gen["generation_id"]
    si.index_source_file(f, r, repo, _cfg(root_dir))  # content extracted
    assert any("log.txt" in h["path"] for h in repo.search_sources("crane"))

    # A preserve repair must keep the text row intact.
    si._index_source_metadata(f, r, repo, _cfg(root_dir), generation_id=gid, preserve_content=True)
    conn = sqlite3.connect(db)
    n_preserved = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    conn.close()
    assert n_preserved == 1, "preserve repair must not clear extracted content"
    assert any("log.txt" in h["path"] for h in repo.search_sources("crane"))

    # A NON-preserve metadata write (a genuine change) DOES invalidate the stale content.
    si._index_source_metadata(f, r, repo, _cfg(root_dir), generation_id=gid, preserve_content=False)
    conn = sqlite3.connect(db)
    n_cleared = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    conn.close()
    assert n_cleared == 0


def test_sensitivity_flip_changes_fingerprint_and_abandons_active_generation(tmp_path):
    """A root's sensitivity is folded into the policy fingerprint, so flipping it invalidates an ACTIVE
    (resumable) generation — it is abandoned and a fresh one is created (content must be re-secured)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(3):
        (root_dir / f"f{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    root_hash = si.hashlib.sha256(str(root_dir).encode()).hexdigest()[:32]
    r_plain = ExternalSourceRoot(source_root_key="work", path=str(root_dir), sensitive=False)
    r_sensitive = ExternalSourceRoot(source_root_key="work", path=str(root_dir), sensitive=True)
    # The fingerprint itself must differ on the sensitivity bit.
    assert si._policy_fingerprint(r_plain, _cfg(root_dir), root_hash) != si._policy_fingerprint(
        r_sensitive, _cfg(root_dir), root_hash
    )

    # Leave an ACTIVE partial generation (bounded), then flip sensitivity: the active generation is
    # abandoned (fingerprint mismatch), never silently resumed under the new policy.
    cfg_bounded = _cfg(root_dir, source_index_scan_observed_files_per_pass=1)
    rep = si.scan_source_root(r_plain, repo, cfg_bounded)
    assert rep.generation_status == "partial"
    first = rep.generation_id
    si.scan_source_root(r_sensitive, repo, cfg_bounded)
    gens = {
        g["generation_id"]: g
        for g in SourceIndexScanGenerationsRepository(db).list_generations("work")
    }
    assert gens[first]["status"] == "abandoned"
    assert any(gid != first for gid in gens)  # a fresh generation replaced it


# ===== Finding 3: invalid/escaping/missing cursor frames → abandon, no reconciliation =============
@pytest.mark.parametrize(
    "bad_cursor",
    [
        '{"version":1,"frames":[{"d":"../escape","after":null}]}',  # containment escape
        '{"version":1,"frames":[{"d":"gone-dir","after":null}]}',  # missing directory
        '{"version":1,"frames":["not-a-dict"]}',  # malformed frame
        '{"version":99,"frames":[]}',  # wrong traversal version
    ],
)
def test_invalid_cursor_abandons_generation_without_reconciliation(tmp_path, bad_cursor):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "keep.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))  # keep.txt indexed, generation completed

    # Seed an ACTIVE partial generation carrying an invalid cursor + a stale deletion candidate.
    gr = SourceIndexScanGenerationsRepository(db)
    g = gr.begin_generation_pass(
        "work", "runbad", policy_fingerprint="willreset", root_path_hash="rph"
    )
    gr.mark_partial(g["generation_id"], "runbad", cursor_json=bad_cursor)

    # Align the seeded generation's fingerprint to what scan_source_root will compute, so the fingerprint
    # check PASSES and cursor VALIDATION is what rejects it (isolating the finding-3 path).
    root_path_hash = si.hashlib.sha256(str(root_dir).encode()).hexdigest()[:32]
    fp = si._policy_fingerprint(r, _cfg(root_dir), root_path_hash)
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_index_scan_generations SET policy_fingerprint=?, root_path_hash=?, "
        "traversal_version=1 WHERE generation_id=?",
        (fp, root_path_hash, g["generation_id"]),
    )
    conn.commit()
    conn.close()

    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "abandoned"
    assert rep.error_code == "invalid_cursor"
    # No deletion ran: keep.txt still present.
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='keep.txt'")
        .fetchone()[0]
    )
    assert d == 0


# ===== Finding 4: reconciliation never deletes on an indeterminate (permission/IO) probe ==========
def test_indeterminate_candidate_leaves_reconcile_pending_no_delete(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    (root_dir / "b.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))

    # Remove b.txt (genuinely gone) but make the reconcile probe report INDETERMINATE for it (e.g. a
    # permission/transient-IO error) — it must NOT be deleted; the generation stays reconcile_pending.
    (root_dir / "b.txt").unlink()
    orig = si._probe_candidate

    def _fake_probe(abs_c, root_path):
        if abs_c.name == "b.txt":
            return "indeterminate"
        return orig(abs_c, root_path)

    monkeypatch.setattr(si, "_probe_candidate", _fake_probe)
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "reconcile_pending"
    assert rep.error_code == "reconcile_indeterminate"
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='b.txt'")
        .fetchone()[0]
    )
    assert d == 0, "an indeterminate probe must never delete"

    # Once the condition clears (real ENOENT), a resumed reconcile completes and deletes it.
    monkeypatch.undo()
    rep2 = _run_to_completion(r, repo, _cfg(root_dir))
    assert rep2.generation_status == "completed"
    d2 = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='b.txt'")
        .fetchone()[0]
    )
    assert d2 == 1


def test_probe_candidate_classifies_three_outcomes(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    present = root_dir / "here.txt"
    present.write_text("x")
    assert si._probe_candidate(present, root_dir) == "present"
    assert si._probe_candidate(root_dir / "missing.txt", root_dir) == "absent"

    def _boom(path):
        raise PermissionError("denied")

    monkeypatch.setattr(si.os, "stat", _boom)
    assert si._probe_candidate(present, root_dir) == "indeterminate"


# ===== Finding 6: health completeness derives from generation truth, not legacy bootstrap status ===
def test_health_metadata_completeness_from_generation_truth(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(4):
        (root_dir / f"pre{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    cfg = _cfg(root_dir)
    h = source_index_health(repo, cfg)
    work = next(x for x in h["roots"] if x["root_key"] == "work")
    assert work["metadata_completeness_state"] == "complete"

    # Now drive the latest generation to FAILED (high fanout). Rows still exist, but completeness must
    # NOT read as complete off the stale bootstrap status.
    for i in range(30):
        (root_dir / f"big{i}.txt").write_text("y")
    rep = si.scan_source_root(r, repo, _cfg(root_dir, source_index_directory_fanout_limit=10))
    assert rep.generation_status == "failed"
    h2 = source_index_health(repo, cfg)
    work2 = next(x for x in h2["roots"] if x["root_key"] == "work")
    assert work2["metadata_completeness_state"] == "partial", work2["metadata_completeness_state"]


# ===== Finding 7: additive search result fields + path-only snippet ==============================
def test_search_result_fields_path_only_then_content(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "RFI-response.txt"
    f.write_text("the reinforcement bar spacing")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))

    # Metadata-first: a filename match is a PATH match with no indexed text, and its snippet highlights
    # the rel_path (never an empty content snippet).
    hits = repo.search_source_files("RFI-response")
    assert hits, hits
    hit = hits[0]
    assert hit["match_basis"] == "path"
    assert hit["indexed_text_available"] is False
    assert (
        hit["extraction_disposition"] == "content"
    )  # a .txt is content-eligible (awaiting extraction)
    assert hit["extraction_status"] == "pending"
    assert "[" in (hit["snippet"] or "")  # highlighted path snippet

    also = repo.search_sources("RFI-response")[0]
    assert also["match_basis"] == "path" and also["indexed_text_available"] is False

    # After targeted extraction a body match is a CONTENT match with indexed text available.
    si.index_source_file(f, r, repo, _cfg(root_dir))
    body = repo.search_source_files("reinforcement")
    assert body, body
    assert "content" in body[0]["match_basis"]
    assert body[0]["indexed_text_available"] is True


# ===== F-01 (2nd round): an INDETERMINATE directory read suspends the scan, never mass-deletes ======
def test_scandir_read_error_classification():
    """_scandir_sorted distinguishes a confirmed-gone directory (ENOENT/ENOTDIR → empty) from an
    indeterminate read error (permission/IO → DirectoryReadError, fail closed)."""
    import tempfile as _tf

    tmp = Path(_tf.mkdtemp(prefix="scandir_"))
    missing = tmp / "nope"
    cfg = _cfg(tmp)
    # Confirmed-gone directory → treated as empty (no raise).
    assert si._scandir_sorted(missing, tmp, cfg, 20000) == []
    # A file path used as a directory (ENOTDIR) → empty, not an error.
    afile = tmp / "f.txt"
    afile.write_text("x")
    assert si._scandir_sorted(afile, tmp, cfg, 20000) == []


def test_directory_read_error_suspends_without_deletion(tmp_path, monkeypatch):
    """A permission/transient-IO failure enumerating a subtree during the walk suspends the generation
    (partial, directory_read_error) with NO reconciliation — an unreadable subtree can never be published
    as a complete scan that then deletes its indexed files (F-01)."""
    root_dir = tmp_path / "root"
    (root_dir / "sub").mkdir(parents=True)
    (root_dir / "top.txt").write_text("x")
    (root_dir / "sub" / "deep.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    (root_dir / "sub" / "deep.txt").unlink()  # would be a stale candidate if the walk "completed"

    orig = si._scandir_sorted

    def _fake_scandir(abs_dir, root_path, config, fanout):
        if abs_dir.name == "sub":
            raise si.DirectoryReadError("sub")
        return orig(abs_dir, root_path, config, fanout)

    monkeypatch.setattr(si, "_scandir_sorted", _fake_scandir)
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "partial"
    assert rep.error_code == "directory_read_error"
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='sub/deep.txt'")
        .fetchone()[0]
    )
    assert d == 0, "an unreadable subtree must not drive a deletion"


def test_empty_root_guard_blocks_mass_delete(tmp_path):
    """A root that suddenly reads as empty while the index still holds MORE THAN the threshold of active
    rows (lost mount / empty mountpoint) fails closed instead of mass-deleting; a small emptying still
    reconciles (F-01 blast-radius sentinel)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(3):
        (root_dir / f"f{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, source_index_empty_root_delete_threshold=2)
    _run_to_completion(r, repo, cfg)
    for i in range(3):
        (root_dir / f"f{i}.txt").unlink()  # root now reads empty; 3 active rows > threshold 2
    rep = si.scan_source_root(r, repo, cfg)
    assert rep.generation_status == "failed"
    assert rep.error_code == "empty_root_guard"
    n_active = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources "
            "WHERE source_root_key='work' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n_active == 3, "the empty-root guard must not delete any row"


# ===== F-03 (2nd round): a per-file error holds the cursor and is retried, never skipped =============
def test_per_file_error_holds_cursor_then_retries(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(4):
        (root_dir / f"f{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))

    orig = si._index_source_metadata
    state = {"failed": False}

    def _flaky(abs_path, *a, **k):
        if abs_path.name == "f2.txt" and not state["failed"]:
            state["failed"] = True
            raise RuntimeError("transient upsert error")
        return orig(abs_path, *a, **k)

    monkeypatch.setattr(si, "_index_source_metadata", _flaky)
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    # The pass suspended (partial) at the unresolved file — NOT completed with a hole.
    assert rep.generation_status == "partial"
    assert rep.error_code == "metadata_walk_error"
    # f2 was NOT indexed (cursor held before it); it is not silently skipped.
    conn = sqlite3.connect(db)
    f2_rows = conn.execute(
        "SELECT COUNT(*) FROM source_intelligence_sources WHERE rel_path='f2.txt' AND deleted=0"
    ).fetchone()[0]
    conn.close()
    assert f2_rows == 0

    # The next pass (error cleared) resumes from the held cursor and indexes f2 → completes with all 4.
    monkeypatch.undo()
    rep2 = _run_to_completion(r, repo, _cfg(root_dir))
    assert rep2.generation_status == "completed"
    n = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources "
            "WHERE source_root_key='work' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n == 4
    assert any("f2.txt" in h["path"] for h in repo.search_sources("f2"))


# ===== F-11: a genuine V119→V122 upgrade repairs legacy rows on the first generation ================
def test_v119_to_v120_first_generation_repairs_legacy_rows(tmp_path):
    """Representative legacy rows (NULL disposition; a metadata-only file with NO path-FTS row; a content
    file with extracted text) — exactly what the V122 ADD COLUMN yields for pre-existing V119 rows — are
    repaired on the first V122 generation: the metadata-only file becomes path-searchable and the content
    file keeps its extracted content."""
    from hb_assistant.obsidian_mcp.source_index_repository import source_id_for

    root_dir = tmp_path / "root"
    (root_dir / "a").mkdir(parents=True)
    pdf = root_dir / "a" / "Legacy.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    txt = root_dir / "a" / "Report.txt"
    txt.write_text("the concrete pour schedule")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    si.index_source_file(txt, r, repo, _cfg(root_dir))  # give the txt real extracted content

    # Degrade both rows to legacy V119 shape: NULL disposition everywhere, and DROP the pdf's path-FTS row
    # (PR-1 metadata-only rows had none). The txt keeps its content + FTS row.
    pdf_sid = source_id_for("external_file", source_root_key="work", rel_path="a/Legacy.pdf")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE source_intelligence_metadata SET extraction_disposition=NULL")
    conn.execute(
        "DELETE FROM source_intelligence_fts WHERE rowid=("
        "SELECT fts_rowid FROM source_intelligence_metadata WHERE source_id=?)",
        (pdf_sid,),
    )
    conn.execute(
        "UPDATE source_intelligence_metadata SET fts_rowid=NULL WHERE source_id=?", (pdf_sid,)
    )
    conn.commit()
    conn.close()
    assert repo.search_sources("Legacy") == []  # pdf not path-searchable pre-upgrade

    # First V122 generation after the "upgrade": repairs the pdf's path FTS, preserves the txt's content.
    _run_to_completion(r, repo, _cfg(root_dir))
    assert any("Legacy.pdf" in h["path"] for h in repo.search_sources("Legacy"))
    assert any(
        "Report.txt" in h["path"] for h in repo.search_sources("concrete")
    )  # content preserved
    conn = sqlite3.connect(db)
    disp = conn.execute(
        "SELECT extraction_disposition FROM source_intelligence_metadata WHERE source_id=?",
        (pdf_sid,),
    ).fetchone()[0]
    conn.close()
    assert disp == "metadata_only"  # disposition backfilled during the repair


# ===== F-06: a file inserted behind the cursor is never LOST — the next generation catches it ========
def test_file_inserted_behind_cursor_no_loss_next_generation_catches(tmp_path):
    """A file created BEHIND the traversal cursor between bounded passes may be missed by the in-flight
    generation (a documented point-in-time-snapshot property), but it is NEVER permanently lost and NEVER
    causes a false deletion: the next generation (fresh from root) indexes it. This bounds F-06 to eventual
    consistency — full mutation-safe cursoring is a follow-up."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for n in ("m1.txt", "m2.txt", "m3.txt"):
        (root_dir / n).write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, source_index_scan_observed_files_per_pass=1)

    rep1 = si.scan_source_root(r, repo, cfg)  # observes m1, cursor parks after m1
    assert rep1.generation_status == "partial"
    (root_dir / "a0.txt").write_text("x")  # sorts BEFORE the cursor → may be missed this generation

    _run_to_completion(r, repo, cfg)  # finish the in-flight generation
    # No false deletion: the m-files (which exist) are never deleted.
    n_deleted = (
        sqlite3.connect(db)
        .execute("SELECT COUNT(*) FROM source_intelligence_sources WHERE deleted=1")
        .fetchone()[0]
    )
    assert n_deleted == 0

    # The NEXT generation walks fresh from root and indexes the behind-cursor file (eventual catch-up).
    _run_to_completion(r, repo, cfg)
    assert any("a0.txt" in h["path"] for h in repo.search_sources("a0"))
    n_active = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources "
            "WHERE source_root_key='work' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n_active == 4  # a0 + m1 + m2 + m3, none lost


# ===== Round 3 =====================================================================================
# The following cover the six round-3 review findings: sensitivity re-secure on a COMPLETED root,
# project reclassification of an unchanged file, content_indexed_at clearing, strict cursor validation,
# generation-truth health (reconcile_pending/legacy fallback), and lease-fenced terminal transitions.


# ----- Round-3 finding 1: a completed-root sensitivity flip re-secures unchanged plaintext ----------
def test_sensitivity_flip_on_completed_root_resecures_unchanged_content(tmp_path):
    """A root that becomes sensitive AFTER a generation completed must re-secure its already-indexed
    files: even though each file is physically unchanged (stat + disposition match), the fast-skip is
    defeated by the owed sensitivity re-secure, so the next generation clears the plaintext content while
    keeping path discoverability."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "payroll.txt"
    f.write_text("employee salary ledger")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r_plain = ExternalSourceRoot(source_root_key="work", path=str(root_dir), sensitive=False)
    _run_to_completion(r_plain, repo, _cfg(root_dir))
    si.index_source_file(f, r_plain, repo, _cfg(root_dir))  # plaintext content indexed + searchable
    assert any("payroll.txt" in h["path"] for h in repo.search_sources("salary"))
    assert repo.content_status_counts("work")["content_searchable"] >= 1

    # Flip the root to sensitive; the file is UNCHANGED. The next (fresh) generation re-secures it.
    r_sensitive = ExternalSourceRoot(source_root_key="work", path=str(root_dir), sensitive=True)
    _run_to_completion(r_sensitive, repo, _cfg(root_dir))
    conn = sqlite3.connect(db)
    n_text = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    conn.close()
    assert n_text == 0, "plaintext content must be cleared when a completed root becomes sensitive"
    assert repo.content_status_counts("work")["content_searchable"] == 0
    assert not any("payroll.txt" in h["path"] for h in repo.search_sources("salary"))
    # Path discoverability is preserved (path FTS invariant).
    assert any("payroll.txt" in h["path"] for h in repo.search_sources("payroll"))


# ----- Round-3 finding 2: a project-matcher change re-routes an unchanged file ----------------------
def test_project_reclassification_replaces_stale_project_on_unchanged_file(tmp_path, monkeypatch):
    """A project-matcher policy change re-routes a file to a different project even when its bytes are
    unchanged. The stale project_key + belongs_to_project edge must be REPLACED (not fast-skipped, not
    appended)."""
    root_dir = tmp_path / "root"
    (root_dir / "10-001-00 Tower").mkdir(parents=True)
    f = root_dir / "10-001-00 Tower" / "plan.txt"
    f.write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    conn = sqlite3.connect(db)
    pk0 = conn.execute(
        "SELECT project_key FROM source_intelligence_sources WHERE rel_path LIKE '%plan.txt'"
    ).fetchone()[0]
    conn.close()
    assert pk0 == "10-001-00"

    orig = si.match_path_to_project

    def _rerouted(rel_path):
        if "plan.txt" in rel_path:
            return ("20-002-00", "20-002-00", "high")
        return orig(rel_path)

    monkeypatch.setattr(si, "match_path_to_project", _rerouted)
    _run_to_completion(r, repo, _cfg(root_dir))
    conn = sqlite3.connect(db)
    pk1 = conn.execute(
        "SELECT project_key FROM source_intelligence_sources WHERE rel_path LIKE '%plan.txt'"
    ).fetchone()[0]
    rels = [
        row[0]
        for row in conn.execute(
            "SELECT dst_ref FROM source_intelligence_relationships WHERE relation='belongs_to_project'"
        ).fetchall()
    ]
    conn.close()
    assert pk1 == "20-002-00", "an unchanged file must be re-routed to the new project"
    assert rels == ["20-002-00"], "the stale project edge must be replaced, not appended"


# ----- Round-3 finding 3: content_indexed_at is NULLed when valid content no longer exists ----------
def test_content_indexed_at_cleared_when_content_removed(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "notes.txt"
    f.write_text("beam camber survey")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    si.index_source_file(f, r, repo, _cfg(root_dir))  # extraction stamps content_indexed_at

    def _stamp():
        conn = sqlite3.connect(db)
        v = conn.execute("SELECT content_indexed_at FROM source_intelligence_metadata").fetchone()[
            0
        ]
        conn.close()
        return v

    assert _stamp() is not None
    gid = SourceIndexScanGenerationsRepository(db).begin_generation_pass(
        "work", "runc", policy_fingerprint="fp", root_path_hash="rph"
    )["generation_id"]
    # A preserve REPAIR keeps valid content → keeps the stamp.
    si._index_source_metadata(f, r, repo, _cfg(root_dir), generation_id=gid, preserve_content=True)
    assert _stamp() is not None, "a preserve repair must not clear content_indexed_at"
    # A replace write with no content (metadata-first) clears content → the stamp must become NULL.
    si._index_source_metadata(f, r, repo, _cfg(root_dir), generation_id=gid, preserve_content=False)
    assert _stamp() is None, "content_indexed_at must be NULL once valid content no longer exists"


# ----- Round-3 finding 4: strict, exception-safe cursor validation ---------------------------------
def test_validate_cursor_strict_rules(tmp_path):
    root = tmp_path / "root"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir()
    (root / "a" / "f.txt").write_text("x")
    cfg = _cfg(root)

    def V(cur):
        return si._validate_cursor(cur, root, cfg, 20000)

    assert V({"frames": []}) is False  # version REQUIRED
    assert V({"version": "abc", "frames": []}) is False  # non-integer version → no crash, reject
    assert V({"version": 1, "frames": []}) is True  # valid empty
    # Parent→child must be EXACT (child.d == parent.d / parent.after).
    assert (
        V({"version": 1, "frames": [{"d": "", "after": "a"}, {"d": "a", "after": "f.txt"}]}) is True
    )
    assert (
        V({"version": 1, "frames": [{"d": "", "after": "a"}, {"d": "b", "after": None}]}) is False
    )
    # A deeper frame under a parent whose ``after`` is None is inconsistent.
    assert (
        V({"version": 1, "frames": [{"d": "", "after": None}, {"d": "a", "after": None}]}) is False
    )
    # An in-root symlink frame is rejected (its target may have changed since the cursor was persisted).
    (root / "link").symlink_to(root / "a", target_is_directory=True)
    assert V({"version": 1, "frames": [{"d": "link", "after": None}]}) is False


def test_malformed_json_cursor_abandons_without_reconciliation(tmp_path):
    """A cursor_json payload that is not decodable JSON is itself an invalid cursor: the pass ABANDONS
    (no reconciliation, no crash) — it never falls through to a walk-from-root that then reconciles."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "keep.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))

    gr = SourceIndexScanGenerationsRepository(db)
    g = gr.begin_generation_pass(
        "work", "runbad", policy_fingerprint="willreset", root_path_hash="rph"
    )
    gr.mark_partial(g["generation_id"], "runbad", cursor_json="not-json{{")
    root_path_hash = si.hashlib.sha256(str(root_dir).encode()).hexdigest()[:32]
    fp = si._policy_fingerprint(r, _cfg(root_dir), root_path_hash)
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_index_scan_generations SET policy_fingerprint=?, root_path_hash=?, "
        "traversal_version=1 WHERE generation_id=?",
        (fp, root_path_hash, g["generation_id"]),
    )
    conn.commit()
    conn.close()

    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "abandoned"
    assert rep.error_code == "invalid_cursor"
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='keep.txt'")
        .fetchone()[0]
    )
    assert d == 0


# ----- Round-3 finding 5: health/readiness from generation truth, not legacy/partial state ----------
def test_health_reconcile_pending_is_not_complete_and_watcher_not_ready(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    (root_dir / "b.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))

    (root_dir / "b.txt").unlink()
    orig = si._probe_candidate
    monkeypatch.setattr(
        si,
        "_probe_candidate",
        lambda abs_c, rp: "indeterminate" if abs_c.name == "b.txt" else orig(abs_c, rp),
    )
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "reconcile_pending"

    h = source_index_health(repo, _cfg(root_dir))
    work = next(x for x in h["roots"] if x["root_key"] == "work")
    # reconcile_pending means unresolved candidates → NOT certifiably complete, watcher NOT ready.
    assert work["metadata_completeness_state"] == "partial"
    assert work["bootstrap"]["watcher_ready"] is False
    assert work["run_state"] != "running"


def test_health_legacy_fallback_requires_explicit_success(tmp_path):
    """For a root with NO V122 generation, completeness falls back to the legacy bootstrap status — but
    only the explicit success sentinel ('bootstrapped') certifies complete; 'conflict'/'partial'/'failed'
    must NOT (the prior ``!= 'partial'`` wrongly certified conflict/failed)."""
    from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository

    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "doc.txt"
    f.write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    si.index_source_file(f, r, repo, _cfg(root_dir))  # targeted → rows exist, NO generation
    bstate = SourceIndexBootstrapRepository(db)

    def _completeness(status: str) -> str:
        bstate.upsert_bootstrap_state("work", file_index_status=status)
        h = source_index_health(repo, _cfg(root_dir))
        return next(x for x in h["roots"] if x["root_key"] == "work")["metadata_completeness_state"]

    assert _completeness("conflict") == "partial"
    assert _completeness("failed") == "partial"
    assert _completeness("bootstrapped") == "complete"


# ----- Round-3 finding 6: metadata-walk completion and finish are lease-fenced ----------------------
def test_walk_complete_and_finish_are_lease_fenced(tmp_path):
    """A run that no longer owns the generation cannot mark the walk complete or complete the generation
    (rowcount 0), so it can never certify progress under a lost lease."""
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    gid = gr.begin_generation_pass("work", "A", policy_fingerprint="fp", root_path_hash="rph")[
        "generation_id"
    ]
    assert gr.mark_metadata_walk_complete(gid, "B") == 0  # non-owner cannot mark walk complete
    assert gr.mark_metadata_walk_complete(gid, "A") == 1
    # Takeover before completion: ownership moves to B (status stays running).
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_index_scan_generations SET active_run_id='B' WHERE generation_id=?", (gid,)
    )
    conn.commit()
    conn.close()
    assert gr.finish_completed(gid, "A") == 0  # A lost the lease → cannot complete
    assert gr.finish_completed(gid, "B") == 1  # rightful owner completes
    status = (
        sqlite3.connect(db)
        .execute("SELECT status FROM source_index_scan_generations WHERE generation_id=?", (gid,))
        .fetchone()[0]
    )
    assert status == "completed"


def test_scan_reports_conflict_when_finish_loses_lease(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))

    class _LostAtFinish(SourceIndexScanGenerationsRepository):
        def finish_completed(self, *a, **k):  # noqa: ANN002
            return 0  # lease lost right before completion

    rep = si.scan_source_root(r, repo, _cfg(root_dir), genrepo=_LostAtFinish(db))
    assert rep.completed is False
    assert rep.generation_status == "conflict"
    assert rep.error_code == "lease_lost"


def test_scan_reports_conflict_when_walk_complete_loses_lease(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))

    class _LostAtWalkComplete(SourceIndexScanGenerationsRepository):
        def mark_metadata_walk_complete(self, *a, **k):  # noqa: ANN002
            return 0  # lease lost right after the final batch

    rep = si.scan_source_root(r, repo, _cfg(root_dir), genrepo=_LostAtWalkComplete(db))
    assert rep.completed is False
    assert rep.generation_status == "conflict"
    assert rep.error_code == "lease_lost"


# ===== Round 4 =====================================================================================
# V121→V122 renumber + migration, second-stat race (walk & reconcile), committed-prefix counters,
# stricter cursor validation (non-root frame / malformed after), sensitive→plain, project_number
# signature, and exclusion changes against a completed root.


def test_v122_fresh_and_incremental_migration(tmp_path):
    """Fresh V122 reaches head 122 with the generations table + new fingerprint column; an incremental
    apply onto a DB that already has 120/121 lands ONLY v122 (idempotent, parity-guarded)."""
    from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

    db = str(tmp_path / "fresh.db")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION == 122
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(source_intelligence_sources)")}
    assert {"last_seen_generation", "last_seen_at", "last_indexed_fingerprint"} <= cols
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='source_index_scan_generations'"
    ).fetchone()
    conn.close()
    assert SQLiteMigrator(db_path=db).apply() == 122  # idempotent re-run

    # GENUINE incremental V121→V122: reduce a migrated DB to a real V121 shape — DROP the v122 marker, the
    # generations table, the reconciliation index, AND every v122-added column (sqlite 3.35+ DROP COLUMN) —
    # then re-apply and prove v122 actually recreates the table, index, all six columns, and the marker
    # while the prior manifest data (120/121) survives.
    v122_columns = [
        ("source_intelligence_sources", "last_seen_generation"),
        ("source_intelligence_sources", "last_seen_at"),
        ("source_intelligence_sources", "last_indexed_fingerprint"),
        ("source_intelligence_metadata", "extraction_disposition"),
        ("source_intelligence_metadata", "content_indexed_at"),
        ("source_index_bootstrap_runs", "generation_id"),
    ]
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM schema_migrations WHERE version=122")
    conn.execute("DROP TABLE source_index_scan_generations")
    conn.execute("DROP INDEX IF EXISTS idx_si_sources_last_seen_gen")
    for table, col in v122_columns:
        conn.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
    conn.commit()
    for table, col in v122_columns:  # sanity: genuinely V121-shaped now
        assert col not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    conn.close()

    assert SQLiteMigrator(db_path=db).apply() == 122
    conn = sqlite3.connect(db)
    for table, col in v122_columns:  # every column recreated
        assert col in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}, (table, col)
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='source_index_scan_generations'"
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_si_sources_last_seen_gen'"
    ).fetchone()
    assert {
        r[0]
        for r in conn.execute(
            "SELECT version FROM schema_migrations WHERE version IN (120,121,122)"
        )
    } == {120, 121, 122}  # prior manifest data survives + v122 marker rewritten
    conn.close()


def test_walk_none_outcome_suspends_without_advancing(tmp_path, monkeypatch):
    """A metadata observation that yields NO source id (second-stat race) must SUSPEND the walk with the
    cursor held — never advance past the file as if processed (finding: second-stat race, walk side)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for n in ("f0.txt", "f1.txt", "f2.txt"):
        (root_dir / n).write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    orig = si._index_source_metadata
    state = {"done": False}

    def _none_once(abs_path, *a, **k):
        if abs_path.name == "f1.txt" and not state["done"]:
            state["done"] = True
            return si.IndexOutcome(None, "content", False, False, False, "pending")
        return orig(abs_path, *a, **k)

    monkeypatch.setattr(si, "_index_source_metadata", _none_once)
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "partial"
    assert "metadata_no_source_id" in rep.error_codes
    n_f1 = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE rel_path='f1.txt' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n_f1 == 0, "the None-outcome file must not be certified as processed"

    monkeypatch.undo()
    rep2 = _run_to_completion(r, repo, _cfg(root_dir))
    assert rep2.generation_status == "completed"
    n = (
        sqlite3.connect(db)
        .execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE source_root_key='work' AND deleted=0"
        )
        .fetchone()[0]
    )
    assert n == 3


def test_reconcile_survivor_none_leaves_reconcile_pending(tmp_path, monkeypatch):
    """A survivor refresh during reconciliation that yields NO source id must leave the generation
    reconcile_pending and delete NOTHING — never a false completion (finding: second-stat race, reconcile
    side)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    (root_dir / "b.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))  # G1 stamps a, b

    # Seed an idle reconcile_pending generation G2 whose walk is "complete" but never stamped a/b (so both
    # are stale-but-present survivors at reconcile). Fingerprint/root-hash match current policy so the scan
    # resumes G2 rather than creating a fresh one.
    from pathlib import Path as _P

    gr = SourceIndexScanGenerationsRepository(db)
    rph = si.hashlib.sha256(str(_P(str(root_dir))).encode("utf-8")).hexdigest()[:32]
    fp = si._policy_fingerprint(r, _cfg(root_dir), rph)
    g2 = gr.begin_generation_pass("work", "seed", policy_fingerprint=fp, root_path_hash=rph)
    gr.mark_metadata_walk_complete(g2["generation_id"], "seed")
    gr.release_owner(g2["generation_id"], "seed")  # → reconcile_pending, idle (resumable)

    orig = si._index_source_metadata

    def _none_for_b(abs_path, *a, **k):
        if abs_path.name == "b.txt":
            return si.IndexOutcome(None, "content", False, False, False, "pending")
        return orig(abs_path, *a, **k)

    monkeypatch.setattr(si, "_index_source_metadata", _none_for_b)
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "reconcile_pending"
    n_deleted = (
        sqlite3.connect(db)
        .execute("SELECT COUNT(*) FROM source_intelligence_sources WHERE deleted=1")
        .fetchone()[0]
    )
    assert n_deleted == 0, "an unresolved survivor must never drive a deletion or a completion"


def test_committed_prefix_counter_no_double_count(tmp_path, monkeypatch):
    """The persisted files_observed counts only the COMMITTED prefix, so a batch whose suffix is retried
    next pass is never double-counted toward the generation ceiling (finding: committed-prefix counters)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(5):
        (root_dir / f"f{i}.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    orig = si._index_source_metadata
    state = {"failed": False}

    def _flaky(abs_path, *a, **k):
        if abs_path.name == "f2.txt" and not state["failed"]:
            state["failed"] = True
            raise RuntimeError("transient")
        return orig(abs_path, *a, **k)

    monkeypatch.setattr(si, "_index_source_metadata", _flaky)
    rep1 = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep1.generation_status == "partial"
    gr = SourceIndexScanGenerationsRepository(db)
    g = gr.get_active_generation("work")
    assert g["files_observed"] == 2, g[
        "files_observed"
    ]  # only f0, f1 committed — NOT the whole batch

    monkeypatch.undo()
    rep2 = _run_to_completion(r, repo, _cfg(root_dir))
    assert rep2.generation_status == "completed"
    g2 = next(x for x in gr.list_generations("work") if x["generation_id"] == g["generation_id"])
    assert g2["files_observed"] == 5, g2["files_observed"]  # retried suffix not double-counted


def test_validate_cursor_round4_rules(tmp_path):
    root = tmp_path / "root"
    (root / "a").mkdir(parents=True)
    (root / "a" / "f.txt").write_text("x")
    cfg = _cfg(root)

    def V(cur):
        return si._validate_cursor(cur, root, cfg, 20000)

    # The FIRST frame must be the ROOT (d == "" or "."). A subtree-only cursor is rejected.
    assert V({"version": 1, "frames": [{"d": "a", "after": "f.txt"}]}) is False
    assert (
        V({"version": 1, "frames": [{"d": "", "after": "a"}, {"d": "a", "after": "f.txt"}]}) is True
    )
    # ``after`` must be a single valid basename — no separators / NUL / '.' / '..'.
    assert V({"version": 1, "frames": [{"d": "", "after": "a/b"}]}) is False
    assert V({"version": 1, "frames": [{"d": "", "after": ".."}]}) is False
    assert V({"version": 1, "frames": [{"d": "", "after": "a\x00b"}]}) is False
    assert V({"version": 1, "frames": [{"d": "", "after": None}]}) is False
    # An anchor naming a non-existent / non-matching entry is rejected (would skip real entries).
    assert (
        V({"version": 1, "frames": [{"d": "", "after": "zzzz"}]}) is False
    )  # not an entry of root
    # An in-root symlinked directory is excluded from traversal, so an anchor naming it is not a real
    # (non-symlink) entry and the cursor is rejected (a retargeted symlink must not drive resume).
    (root / "link").symlink_to(root / "a", target_is_directory=True)
    assert V({"version": 1, "frames": [{"d": "", "after": "link"}]}) is False
    # A deepest anchor that names a DIRECTORY (not a yielded file) would skip its whole subtree → rejected.
    assert V({"version": 1, "frames": [{"d": "", "after": "a"}]}) is False


def test_sensitive_to_plain_transition_clears_vault_content(tmp_path):
    """A completed SENSITIVE→PLAIN transition must re-evaluate an encrypted-to-vault row: it is not left
    fast-skipped/preserved — the stale vault content is cleared (path discoverability preserved)."""
    from hb_assistant.obsidian_mcp.source_index_repository import source_id_for

    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "secret.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r_sens = ExternalSourceRoot(source_root_key="work", path=str(root_dir), sensitive=True)
    _run_to_completion(r_sens, repo, _cfg(root_dir))
    # Simulate an extracted-to-vault content row (sensitive: text_vault_ref set, no plaintext excerpt).
    sid = source_id_for("external_file", source_root_key="work", rel_path="secret.txt")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO source_intelligence_text (source_id, text_excerpt, text_vault_ref, updated_at) "
        "VALUES (?,?,?,?)",
        (sid, None, "vault-ref-blob", "2020-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()
    assert (
        repo.load_metadata_state_batch("work", ["secret.txt"])["secret.txt"]["content_mode"]
        == "vault"
    )

    r_plain = ExternalSourceRoot(source_root_key="work", path=str(root_dir), sensitive=False)
    _run_to_completion(r_plain, repo, _cfg(root_dir))
    n_text = (
        sqlite3.connect(db).execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    )
    assert n_text == 0, "vault content must be cleared on a sensitive->plain transition"
    assert any("secret.txt" in h["path"] for h in repo.search_sources("secret"))


def test_project_number_change_reprocesses_unchanged_file(tmp_path, monkeypatch):
    """Project compatibility compares BOTH key and number: a matcher change that alters only the number of
    an unchanged file still forces a replace of the stale routing (finding: project signature)."""
    root_dir = tmp_path / "root"
    (root_dir / "10-001-00 T").mkdir(parents=True)
    (root_dir / "10-001-00 T" / "p.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    orig = si.match_path_to_project

    def _num_change(rel_path):
        if "p.txt" in rel_path:
            return ("10-001-00", "99-999-99", "high")  # key unchanged, NUMBER changed
        return orig(rel_path)

    monkeypatch.setattr(si, "match_path_to_project", _num_change)
    _run_to_completion(r, repo, _cfg(root_dir))
    num = (
        sqlite3.connect(db)
        .execute(
            "SELECT project_number FROM source_intelligence_sources WHERE rel_path LIKE '%p.txt'"
        )
        .fetchone()[0]
    )
    assert num == "99-999-99", "a project_number change must reprocess the unchanged file"


def test_new_exclusion_removes_indexed_rows_on_completed_root(tmp_path):
    """Adding an exclusion to a previously-indexed directory must REMOVE its records: the walk prunes the
    subtree and reconciliation treats the present-but-now-excluded files as policy removals (finding:
    exclusion changes) — the source files themselves are never touched."""
    root_dir = tmp_path / "root"
    (root_dir / "ARCHIVE").mkdir(parents=True)
    (root_dir / "active.txt").write_text("x")
    (root_dir / "ARCHIVE" / "old.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    assert any("old.txt" in h["path"] for h in repo.search_sources("old"))

    cfg2 = _cfg(root_dir, source_index_excluded_path_parts=["ARCHIVE"])
    _run_to_completion(r, repo, cfg2)
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path LIKE '%old.txt'")
        .fetchone()[0]
    )
    assert d == 1, "a newly-excluded file must be removed from the index"
    assert not any("old.txt" in h["path"] for h in repo.search_sources("old"))
    assert any("active.txt" in h["path"] for h in repo.search_sources("active"))
    # The source file on disk is untouched.
    assert (root_dir / "ARCHIVE" / "old.txt").exists()


# ===== Round 5 =====================================================================================
# reconcile-cursor self-limiting restart, authoritative preserve (FTS/relationship/abs_path_hash),
# policy-current health, and ownership-fenced abandon.


def test_reconcile_ignores_persisted_cursor_and_restarts(tmp_path):
    """Reconciliation restarts its keyset sweep from the beginning and never trusts a persisted
    reconcile checkpoint: a forged-high (valid-format) `after` that would skip every stale row must NOT
    let an absent file survive, and a malformed payload must not crash the pass (blocker 1)."""
    from pathlib import Path as _P

    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    (root_dir / "b.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    (root_dir / "b.txt").unlink()  # b is genuinely gone → must be reconciled away

    gr = SourceIndexScanGenerationsRepository(db)
    rph = si.hashlib.sha256(str(_P(str(root_dir))).encode("utf-8")).hexdigest()[:32]
    fp = si._policy_fingerprint(r, _cfg(root_dir), rph)
    g = gr.begin_generation_pass("work", "seed", policy_fingerprint=fp, root_path_hash=rph)
    gr.mark_metadata_walk_complete(g["generation_id"], "seed")
    # A forged checkpoint at the maximum source_id: if trusted, `source_id > after` returns nothing.
    gr.mark_reconcile_pending(
        g["generation_id"], "seed", reconcile_cursor_json='{"after":"' + "f" * 32 + '"}'
    )
    rep = si.scan_source_root(r, repo, _cfg(root_dir))
    assert rep.generation_status == "completed"
    d = (
        sqlite3.connect(db)
        .execute("SELECT deleted FROM source_intelligence_sources WHERE rel_path='b.txt'")
        .fetchone()[0]
    )
    assert d == 1, "a forged reconcile checkpoint must not let an absent row survive reconciliation"


def test_preserve_rebuilds_fts_from_retained_text(tmp_path):
    """Preserve rebuilds the FTS row FROM the retained extracted text — not an empty path-only row — so a
    content row with a missing FTS row stays body-searchable and health keeps counting it content-searchable
    (blocker 3: the concrete plaintext-content-with-missing-FTS failure)."""
    from hb_assistant.obsidian_mcp.source_index_repository import source_id_for

    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "report.txt"
    f.write_text("the concrete pour schedule")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    si.index_source_file(f, r, repo, _cfg(root_dir))  # extract content
    assert any("report.txt" in h["rel_path"] for h in repo.search_source_files("concrete"))

    # Drop the FTS row (retain the extracted text) and NULL the fingerprint so the next scan PRESERVES.
    sid = source_id_for("external_file", source_root_key="work", rel_path="report.txt")
    conn = sqlite3.connect(db)
    conn.execute(
        "DELETE FROM source_intelligence_fts WHERE rowid=("
        "SELECT fts_rowid FROM source_intelligence_metadata WHERE source_id=?)",
        (sid,),
    )
    conn.execute("UPDATE source_intelligence_metadata SET fts_rowid=NULL WHERE source_id=?", (sid,))
    conn.execute(
        "UPDATE source_intelligence_sources SET last_indexed_fingerprint=NULL WHERE source_id=?",
        (sid,),
    )
    conn.commit()
    conn.close()
    assert repo.search_source_files("concrete") == []  # body search broken pre-repair

    _run_to_completion(r, repo, _cfg(root_dir))
    assert any("report.txt" in h["rel_path"] for h in repo.search_source_files("concrete")), (
        "preserve must rebuild the FTS from retained text (not an empty path-only row)"
    )
    assert repo.content_status_counts("work")["content_searchable"] >= 1


def test_preserve_refreshes_abs_path_hash_and_project_relationship(tmp_path):
    """Preserve authoritatively refreshes derived identity — abs_path_hash and the belongs_to_project edge —
    on a fingerprint mismatch, so a root-path or matcher-version change never leaves them stale (blocker 3)."""
    from hb_assistant.obsidian_mcp.source_index_repository import source_id_for

    root_dir = tmp_path / "root"
    (root_dir / "24-118-00").mkdir(parents=True)
    f = root_dir / "24-118-00" / "plan.txt"
    f.write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))
    sid = source_id_for("external_file", source_root_key="work", rel_path="24-118-00/plan.txt")
    correct_hash = si.hashlib.sha256(str(f).encode()).hexdigest()[:32]

    # Corrupt abs_path_hash + the relationship confidence, NULL the fingerprint (→ preserve on rescan).
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_intelligence_sources SET abs_path_hash='STALEHASH', "
        "last_indexed_fingerprint=NULL WHERE source_id=?",
        (sid,),
    )
    conn.execute(
        "UPDATE source_intelligence_relationships SET confidence='WRONG' "
        "WHERE src_source_id=? AND relation='belongs_to_project'",
        (sid,),
    )
    conn.commit()
    conn.close()

    _run_to_completion(r, repo, _cfg(root_dir))
    conn = sqlite3.connect(db)
    got_hash = conn.execute(
        "SELECT abs_path_hash FROM source_intelligence_sources WHERE source_id=?", (sid,)
    ).fetchone()[0]
    conf = conn.execute(
        "SELECT confidence FROM source_intelligence_relationships "
        "WHERE src_source_id=? AND relation='belongs_to_project'",
        (sid,),
    ).fetchone()[0]
    conn.close()
    assert got_hash == correct_hash, "preserve must refresh abs_path_hash"
    assert conf == "high", "preserve must rebuild the project relationship under current policy"


def test_health_stale_when_generation_fingerprint_mismatches_policy(tmp_path):
    """Health must not certify a completed generation as complete/watcher-ready once its stored fingerprint
    no longer matches the currently-configured root (a sensitivity/exclusion/root-path/matcher change) —
    it reads partial and watcher-not-ready until the corrective generation runs (blocker 4)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir)
    _run_to_completion(r, repo, cfg)
    work = next(x for x in source_index_health(repo, cfg)["roots"] if x["root_key"] == "work")
    assert work["metadata_completeness_state"] == "complete"  # matches current policy

    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_index_scan_generations SET policy_fingerprint='STALEFP' WHERE status='completed'"
    )
    conn.commit()
    conn.close()
    work2 = next(x for x in source_index_health(repo, cfg)["roots"] if x["root_key"] == "work")
    assert work2["metadata_completeness_state"] == "partial", (
        "stale completion must not read complete"
    )
    assert work2["bootstrap"]["watcher_ready"] is False


def test_abandon_is_ownership_fenced(tmp_path):
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    gid = gr.begin_generation_pass("work", "A", policy_fingerprint="fp", root_path_hash="rph")[
        "generation_id"
    ]
    assert gr.abandon_generation(gid, "B") == 0  # a non-owner cannot abandon
    st = (
        sqlite3.connect(db)
        .execute("SELECT status FROM source_index_scan_generations WHERE generation_id=?", (gid,))
        .fetchone()[0]
    )
    assert st == "running", "a lost-lease worker must not abandon the new owner's generation"
    assert gr.abandon_generation(gid, "A") == 1  # the rightful owner can
    st2 = (
        sqlite3.connect(db)
        .execute("SELECT status FROM source_index_scan_generations WHERE generation_id=?", (gid,))
        .fetchone()[0]
    )
    assert st2 == "abandoned"


def test_scan_reports_conflict_when_abandon_loses_lease(tmp_path):
    """An invalid cursor whose abandon affects 0 rows (lease taken over during filesystem validation) is a
    retryable conflict, not an abandonment of the new owner's generation (blocker 5)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "keep.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    _run_to_completion(r, repo, _cfg(root_dir))

    gr = SourceIndexScanGenerationsRepository(db)
    rph = si.hashlib.sha256(str(root_dir).encode()).hexdigest()[:32]
    fp = si._policy_fingerprint(r, _cfg(root_dir), rph)
    g = gr.begin_generation_pass("work", "runbad", policy_fingerprint=fp, root_path_hash=rph)
    # An invalid cursor (first frame is not the root) so validation rejects it and the pass tries to abandon.
    gr.mark_partial(
        g["generation_id"],
        "runbad",
        cursor_json='{"version":1,"frames":[{"d":"gone","after":"x"}]}',
    )

    class _LostAbandon(SourceIndexScanGenerationsRepository):
        def abandon_generation(self, *a, **k):  # noqa: ANN002
            return 0  # lease lost during validation

    rep = si.scan_source_root(r, repo, _cfg(root_dir), genrepo=_LostAbandon(db))
    assert rep.generation_status == "conflict"
    assert rep.error_code == "lease_lost"
