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


# ===== F-11: a genuine V119→V120 upgrade repairs legacy rows on the first generation ================
def test_v119_to_v120_first_generation_repairs_legacy_rows(tmp_path):
    """Representative legacy rows (NULL disposition; a metadata-only file with NO path-FTS row; a content
    file with extracted text) — exactly what the V120 ADD COLUMN yields for pre-existing V119 rows — are
    repaired on the first V120 generation: the metadata-only file becomes path-searchable and the content
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

    # First V120 generation after the "upgrade": repairs the pdf's path FTS, preserves the txt's content.
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
