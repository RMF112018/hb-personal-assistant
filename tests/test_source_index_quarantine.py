"""Checkpoint A4 — poison-file quarantine + bounded forward progress.

A single persistently-failing ("poison") file must not pin a source root forever. On repeated per-file
failure the scan holds the cursor and retries up to a bounded threshold; at the threshold the file is
QUARANTINED (a durable, root-level blocker), the cursor advances past it, and later files still index.
A walk that exhausts holding an unresolved quarantine is NON-authoritative (``failed`` +
``quarantine_unresolved``) and is NOT auto-restarted; the A2 trust decision reports the blocker; and only
an operator-driven, bounded, confirmed retry (never a bare "not found") can resolve it.

Scratch SQLite + temp roots only. No live/production DB, NAS, watcher, or remote MCP surface is touched.
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
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)
from hb_assistant.store.source_index_scan_quarantine_repository import (
    SourceIndexScanQuarantineRepository,
)
from hb_assistant.store.source_index_scan_quarantine_tables import (
    RESOLUTION_CONFIRMED_ABSENT,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED,
    STATUS_QUARANTINED,
)

_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        path = os.path.join(tempfile.mkdtemp(prefix="a4q_"), "template.db")
        SQLiteMigrator(db_path=path).apply()
        _TEMPLATE_DB = path
    return _TEMPLATE_DB


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "q.db")
    shutil.copy(_template_db(), db)
    return db


def _cfg(root_dir: Path, *, threshold: int = 2, **overrides) -> ObsidianMcpConfig:
    base = ObsidianMcpConfig(
        vault_root=str(root_dir),
        external_sources=[
            ExternalSourceRoot(source_root_key="work", path=str(root_dir), enabled=True)
        ],
        external_source_index_enabled=True,
        source_index_quarantine_retry_threshold=threshold,
    )
    return base.model_copy(update=overrides) if overrides else base


def _mkfiles(root_dir: Path, n: int = 4) -> None:
    root_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (root_dir / f"f{i}.txt").write_text("x")


def _poison(name: str = "f2.txt"):
    """A monkeypatch for ``_index_source_metadata`` that ALWAYS fails for ``name`` (a permanent poison
    file) and delegates every other path to the real implementation."""
    orig = si._index_source_metadata

    def _flaky(abs_path, *a, **k):
        if abs_path.name == name:
            raise RuntimeError("permanent upsert error")
        return orig(abs_path, *a, **k)

    return _flaky


def _active_count(db: str, root_key: str = "work") -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM source_intelligence_sources "
            "WHERE source_root_key=? AND deleted=0",
            (root_key,),
        ).fetchone()[0]
    finally:
        conn.close()


# ===================================================================================================
# Migration — V125 additive, fresh-safe, upgrade-safe, idempotent
# ===================================================================================================
def test_migration_fresh_creates_quarantine_table(tmp_path):
    db = str(tmp_path / "fresh.db")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION == 125
    conn = sqlite3.connect(db)
    try:
        got = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            ("source_index_scan_quarantine",),
        ).fetchone()
        assert got is not None
        # The active-unresolved uniqueness index is present (deterministic upsert target).
        idx = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='source_index_scan_quarantine'"
            ).fetchall()
        }
        assert "idx_source_index_scan_quarantine_active" in idx
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_migration_is_idempotent(tmp_path):
    db = str(tmp_path / "idem.db")
    assert SQLiteMigrator(db_path=db).apply() == 125
    # A second unconditional apply is a no-op (parity-guarded), not an error.
    assert SQLiteMigrator(db_path=db).apply() == 125
    conn = sqlite3.connect(db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name='source_index_scan_quarantine'"
        ).fetchone()[0]
        assert n == 1
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_migration_upgrade_recreates_quarantine_table(tmp_path):
    """Simulate a pre-V125 DB (drop the V125 marker + table) and prove ``apply()`` re-adds it on upgrade."""
    db = str(tmp_path / "up.db")
    SQLiteMigrator(db_path=db).apply()
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE source_index_scan_quarantine")
    conn.execute("DELETE FROM schema_migrations WHERE version=125")
    conn.commit()
    got = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='source_index_scan_quarantine'"
    ).fetchone()
    conn.close()
    assert got is None  # pre-upgrade shape has no quarantine table
    assert SQLiteMigrator(db_path=db).apply() == 125
    conn = sqlite3.connect(db)
    try:
        got = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='source_index_scan_quarantine'"
        ).fetchone()
        assert got is not None
    finally:
        conn.close()


# ===================================================================================================
# Repository — bounded attempt accounting, single active record, sanitized storage
# ===================================================================================================
def test_record_failure_holds_below_threshold_then_quarantines(tmp_path):
    db = _db(tmp_path)
    repo = SourceIndexScanQuarantineRepository(db)
    r1 = repo.record_failure(
        root_key="work",
        rel_path="a/f.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=3,
    )
    assert r1["action"] == "hold" and r1["attempt_count"] == 1
    r2 = repo.record_failure(
        root_key="work",
        rel_path="a/f.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=3,
    )
    assert r2["action"] == "hold" and r2["attempt_count"] == 2
    r3 = repo.record_failure(
        root_key="work",
        rel_path="a/f.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=3,
    )
    assert r3["action"] == "quarantine" and r3["attempt_count"] == 3
    assert repo.blocking_count("work") == 1


def test_record_failure_keeps_single_active_row_no_duplicates(tmp_path):
    db = _db(tmp_path)
    repo = SourceIndexScanQuarantineRepository(db)
    for _ in range(5):
        repo.record_failure(
            root_key="work",
            rel_path="f.txt",
            source_id=None,
            generation_id="g1",
            failure_stage="metadata_stat",
            error_code="stat_failed",
            threshold=2,
        )
    conn = sqlite3.connect(db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM source_index_scan_quarantine "
            "WHERE source_root_key='work' AND rel_path='f.txt' AND resolution_state=?",
            (RESOLUTION_UNRESOLVED,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 1  # partial UNIQUE index enforces one active unresolved record per (root, path)
    assert repo.blocking_count("work") == 1


def test_record_failure_normalizes_unknown_error_code(tmp_path):
    db = _db(tmp_path)
    repo = SourceIndexScanQuarantineRepository(db)
    repo.record_failure(
        root_key="work",
        rel_path="f.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="RuntimeError: /Users/secret/path boom",
        threshold=1,
    )
    rec = repo.list_quarantine("work")[0]
    # A raw exception string (with a host path) is never stored — it is mapped to a structured code.
    assert rec["error_code"] == "metadata_upsert_failed"
    assert "/Users/" not in rec["error_code"]


def test_resolve_observed_clears_below_threshold_retry(tmp_path):
    db = _db(tmp_path)
    repo = SourceIndexScanQuarantineRepository(db)
    repo.record_failure(
        root_key="work",
        rel_path="f.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=5,
    )
    assert repo.troubled_paths("work") == {"f.txt"}
    assert repo.resolve_observed(root_key="work", rel_path="f.txt") is True
    assert repo.troubled_paths("work") == set()
    assert repo.blocking_count("work") == 0


# ===================================================================================================
# Scan loop — threshold retry, cursor advance, forward progress, non-authoritative completion
# ===================================================================================================
def test_threshold_retry_creates_one_quarantine_and_indexes_later_files(tmp_path, monkeypatch):
    """f2 fails on every pass. Pass 1 holds (below threshold); pass 2 reaches the threshold → f2 is
    quarantined once, the cursor advances past it, and f0/f1/f3 all index. The generation is NON-authoritative
    (failed + quarantine_unresolved), never ``completed`` with a hole."""
    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=2)
    monkeypatch.setattr(si, "_index_source_metadata", _poison("f2.txt"))

    rep1 = si.scan_source_root(r, repo, cfg)
    assert rep1.generation_status == "partial"  # held below threshold (F-03 behavior preserved)

    rep2 = si.scan_source_root(r, repo, cfg)
    assert rep2.generation_status == "failed"
    assert rep2.error_code == "quarantine_unresolved"

    qrepo = SourceIndexScanQuarantineRepository(db)
    items = qrepo.list_quarantine("work")
    assert len(items) == 1
    assert items[0]["rel_path"] == "f2.txt"
    assert items[0]["status"] == STATUS_QUARANTINED
    # Later files indexed despite the poison file (forward progress); f2 itself is not indexed.
    assert _active_count(db) == 3
    conn = sqlite3.connect(db)
    try:
        f2 = conn.execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE rel_path='f2.txt' AND deleted=0"
        ).fetchone()[0]
    finally:
        conn.close()
    assert f2 == 0


def test_no_duplicate_quarantine_rows_across_repeated_passes(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=2)
    monkeypatch.setattr(si, "_index_source_metadata", _poison("f2.txt"))
    for _ in range(4):
        si.scan_source_root(r, repo, cfg)
    conn = sqlite3.connect(db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM source_index_scan_quarantine WHERE rel_path='f2.txt'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_unresolved_quarantine_suspends_auto_retry(tmp_path, monkeypatch):
    """Once quarantined, a fresh automatic pass does NOT walk/reconcile — it returns the blocked sentinel
    (no new infinite loop). Recovery needs operator retry, a policy change, or an explicit restart."""
    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=2)
    monkeypatch.setattr(si, "_index_source_metadata", _poison("f2.txt"))
    si.scan_source_root(r, repo, cfg)  # partial
    si.scan_source_root(r, repo, cfg)  # failed + quarantine_unresolved

    files_before = _active_count(db)
    rep = si.scan_source_root(r, repo, cfg)  # blocked — must not walk
    assert rep.generation_status == "failed"
    assert rep.error_code == "quarantine_unresolved"
    assert "restart_required" in rep.error_codes
    assert _active_count(db) == files_before  # no walk occurred


def test_transient_failure_below_threshold_never_quarantines(tmp_path, monkeypatch):
    """A single failure that clears before the threshold is transient — it resolves on the next clean
    observation and NEVER accumulates into a quarantine (the F-03 hold-and-retry guarantee is preserved)."""
    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=3)

    orig = si._index_source_metadata
    state = {"failed": False}

    def _flaky_once(abs_path, *a, **k):
        if abs_path.name == "f2.txt" and not state["failed"]:
            state["failed"] = True
            raise RuntimeError("transient")
        return orig(abs_path, *a, **k)

    monkeypatch.setattr(si, "_index_source_metadata", _flaky_once)
    rep1 = si.scan_source_root(r, repo, cfg)
    assert rep1.generation_status == "partial"

    # Fault cleared: the next pass resolves the retry record and completes with all 4 files.
    for _ in range(6):
        rep = si.scan_source_root(r, repo, cfg)
        if rep.generation_status == "completed":
            break
    assert rep.generation_status == "completed"
    assert _active_count(db) == 4
    qrepo = SourceIndexScanQuarantineRepository(db)
    assert qrepo.blocking_count("work") == 0
    assert qrepo.troubled_paths("work") == set()  # the transient retry record was resolved


def test_quarantine_state_durable_across_repo_reopen(tmp_path, monkeypatch):
    """The quarantine is durable: a fresh repository instance (crash/restart) still sees the blocker."""
    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=2)
    monkeypatch.setattr(si, "_index_source_metadata", _poison("f2.txt"))
    si.scan_source_root(r, repo, cfg)
    si.scan_source_root(r, repo, cfg)
    # A brand-new repository object over the same DB file (simulating a process restart).
    assert SourceIndexScanQuarantineRepository(db).has_blocking("work") is True


def test_stored_rel_path_is_root_relative_no_absolute_host_path(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    (root_dir / "sub").mkdir(parents=True)
    (root_dir / "sub" / "poison.txt").write_text("x")
    (root_dir / "ok.txt").write_text("x")
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=1)
    monkeypatch.setattr(si, "_index_source_metadata", _poison("poison.txt"))
    si.scan_source_root(r, repo, cfg)
    rec = SourceIndexScanQuarantineRepository(db).list_quarantine("work")[0]
    assert rec["rel_path"] == "sub/poison.txt"
    assert str(tmp_path) not in rec["rel_path"]
    assert not os.path.isabs(rec["rel_path"])


# ===================================================================================================
# Trust — an unresolved quarantine blocks the root (A2 RootTrustDecision)
# ===================================================================================================
def test_unresolved_quarantine_blocks_root_trust(tmp_path):
    from hb_assistant.obsidian_mcp.source_root_trust import (
        RC_QUARANTINE_UNRESOLVED,
        TRUST_SAFE,
        evaluate_root_trust,
        gather_root_inputs,
    )

    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 2)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    cfg = _cfg(root_dir, threshold=1)
    # Record a blocking quarantine directly (independent of a scan).
    SourceIndexScanQuarantineRepository(db).record_failure(
        root_key="work",
        rel_path="f0.txt",
        source_id=None,
        generation_id="g1",
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=1,
    )
    inp = gather_root_inputs(repo, cfg, cfg, "work")
    assert inp.unresolved_quarantine_count >= 1
    decision = evaluate_root_trust(inp)
    assert decision.trust_state != TRUST_SAFE
    assert RC_QUARANTINE_UNRESOLVED in decision.reason_codes
    assert decision.unresolved_quarantine_count >= 1


# ===================================================================================================
# Retention — an unresolved quarantine survives generation pruning (root-level blocker)
# ===================================================================================================
def test_generation_retention_preserves_unresolved_quarantine(tmp_path):
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    qrepo = SourceIndexScanQuarantineRepository(db)
    # Create several failed(quarantine_unresolved) generations, the latest holding the live blocker.
    last_gid = None
    for i in range(5):
        g = gr.begin_generation_pass(
            "work", f"run{i}", policy_fingerprint="fp", root_path_hash="rph"
        )
        gid = g["generation_id"]
        gr.fail_generation(gid, f"run{i}", last_error_code="quarantine_unresolved")
        last_gid = gid
    qrepo.record_failure(
        root_key="work",
        rel_path="f.txt",
        source_id=None,
        generation_id=last_gid,
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=1,
    )
    assert qrepo.has_blocking("work") is True
    gr.prune_generations("work", keep=1)
    # Pruning kept the root blocked: the quarantine survives, and the blocking generation was retained.
    assert qrepo.has_blocking("work") is True


def test_pruned_origin_generation_does_not_clear_root_blocker(tmp_path):
    """Pruning a quarantine's ORIGIN generation nulls its generation_id but retains origin_generation_id and
    the unresolved record — the root stays blocked (no cascade delete)."""
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    qrepo = SourceIndexScanQuarantineRepository(db)
    # An OLD generation is the quarantine's origin; a NEWER blocking generation keeps the root failed.
    g_old = gr.begin_generation_pass("work", "old", policy_fingerprint="fp", root_path_hash="rph")
    old_gid = g_old["generation_id"]
    gr.fail_generation(old_gid, "old", last_error_code="metadata_walk_error")
    qrepo.record_failure(
        root_key="work",
        rel_path="f.txt",
        source_id=None,
        generation_id=old_gid,
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=1,
    )
    for i in range(3):
        g = gr.begin_generation_pass("work", f"n{i}", policy_fingerprint="fp", root_path_hash="rph")
        gr.fail_generation(g["generation_id"], f"n{i}", last_error_code="quarantine_unresolved")

    gr.prune_generations("work", keep=1)  # prunes the old origin generation
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rec = conn.execute(
            "SELECT generation_id, origin_generation_id, resolution_state "
            "FROM source_index_scan_quarantine WHERE rel_path='f.txt'"
        ).fetchone()
        gen_present = conn.execute(
            "SELECT COUNT(*) FROM source_index_scan_generations WHERE generation_id=?",
            (old_gid,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert gen_present == 0  # the origin generation really was pruned
    assert rec["generation_id"] is None  # its FK-less reference was nulled
    assert rec["origin_generation_id"] == old_gid  # audit lineage retained
    assert rec["resolution_state"] == RESOLUTION_UNRESOLVED  # still a blocker
    assert qrepo.has_blocking("work") is True


def test_resolved_quarantine_retention_is_bounded_but_keeps_blockers(tmp_path):
    """A RESOLVED record may be retained as history and can be pruned by generation retention, but resolving
    it (or pruning it) must never erase a still-UNRESOLVED blocker for the same root."""
    db = _db(tmp_path)
    gr = SourceIndexScanGenerationsRepository(db)
    qrepo = SourceIndexScanQuarantineRepository(db)
    g = gr.begin_generation_pass("work", "r0", policy_fingerprint="fp", root_path_hash="rph")
    gid = g["generation_id"]
    gr.fail_generation(gid, "r0", last_error_code="quarantine_unresolved")
    # One resolved (history) + one unresolved (live blocker) for the same root.
    res = qrepo.record_failure(
        root_key="work",
        rel_path="resolved.txt",
        source_id=None,
        generation_id=gid,
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=1,
    )
    qrepo.resolve(quarantine_id=res["quarantine_id"], resolution_state=RESOLUTION_RESOLVED)
    qrepo.record_failure(
        root_key="work",
        rel_path="blocker.txt",
        source_id=None,
        generation_id=gid,
        failure_stage="metadata_stat",
        error_code="stat_failed",
        threshold=1,
    )
    gr.prune_generations("work", keep=1)
    assert qrepo.has_blocking("work") is True
    assert {
        r["rel_path"] for r in qrepo.list_quarantine("work", resolution_state=RESOLUTION_UNRESOLVED)
    } == {"blocker.txt"}


# ===================================================================================================
# Operator retry — bounded, confirmed, trustworthy-observation-only resolution
# ===================================================================================================
def _quarantine_one(db: str, root_dir: Path, name: str, monkeypatch) -> str:
    """Drive a scan until ``name`` is quarantined; return its quarantine_id."""
    repo = SourceIndexRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, threshold=1)
    monkeypatch.setattr(si, "_index_source_metadata", _poison(name))
    si.scan_source_root(r, repo, cfg)
    monkeypatch.undo()
    return SourceIndexScanQuarantineRepository(db).list_quarantine("work")[0]["quarantine_id"]


def test_operator_retry_resolves_now_readable_path(tmp_path, monkeypatch):
    from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine

    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 3)
    db = _db(tmp_path)
    qid = _quarantine_one(db, root_dir, "f2.txt", monkeypatch)
    cfg = _cfg(root_dir, threshold=1)
    out = retry_quarantine(db, cfg, root_key="work", quarantine_id=qid, max_items=1)
    assert out["ok"] and out["resolved"] == 1
    assert SourceIndexScanQuarantineRepository(db).has_blocking("work") is False


def test_operator_retry_confirmed_absent_only_when_trustworthy(tmp_path, monkeypatch):
    from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine

    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 3)
    db = _db(tmp_path)
    qid = _quarantine_one(db, root_dir, "f2.txt", monkeypatch)
    # The file is genuinely gone AND the root/parent are available → trustworthy confirmed-absence.
    (root_dir / "f2.txt").unlink()
    cfg = _cfg(root_dir, threshold=1)
    out = retry_quarantine(db, cfg, root_key="work", quarantine_id=qid, max_items=1)
    assert out["confirmed_absent"] == 1
    rec = SourceIndexScanQuarantineRepository(db).get(qid)
    assert rec["resolution_state"] == RESOLUTION_CONFIRMED_ABSENT


def test_operator_retry_retains_when_root_unavailable(tmp_path, monkeypatch):
    """A retry that cannot find the path is NOT success when the root itself is unavailable — the
    unresolved quarantine is RETAINED (never silently resolved by a bare 'not found')."""
    from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine

    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 3)
    db = _db(tmp_path)
    qid = _quarantine_one(db, root_dir, "f2.txt", monkeypatch)
    shutil.rmtree(
        root_dir
    )  # the entire root is gone (mount loss) — indeterminate, not confirmed-absent
    cfg = _cfg(root_dir, threshold=1)
    out = retry_quarantine(db, cfg, root_key="work", quarantine_id=qid, max_items=1)
    assert out["retained"] == 1
    assert out["outcomes"][0]["retain_reason"] == "root_unavailable"
    assert SourceIndexScanQuarantineRepository(db).has_blocking("work") is True


def test_operator_retry_is_bounded_by_max_items(tmp_path, monkeypatch):
    from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine

    db = _db(tmp_path)
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    qrepo = SourceIndexScanQuarantineRepository(db)
    for i in range(5):
        qrepo.record_failure(
            root_key="work",
            rel_path=f"f{i}.txt",
            source_id=None,
            generation_id="g1",
            failure_stage="metadata_stat",
            error_code="stat_failed",
            threshold=1,
        )
    cfg = _cfg(root_dir, threshold=1)
    out = retry_quarantine(db, cfg, root_key="work", max_items=2)
    assert out["attempted"] == 2  # bounded — never a blanket "resolve everything"


def test_operator_retry_is_idempotent_on_resolved_record(tmp_path, monkeypatch):
    from hb_assistant.obsidian_mcp.source_quarantine_ops import retry_quarantine

    root_dir = tmp_path / "root"
    _mkfiles(root_dir, 3)
    db = _db(tmp_path)
    qid = _quarantine_one(db, root_dir, "f2.txt", monkeypatch)
    cfg = _cfg(root_dir, threshold=1)
    first = retry_quarantine(db, cfg, root_key="work", quarantine_id=qid, max_items=1)
    assert first["resolved"] == 1
    # Retrying an already-resolved record is a no-op (no target remains) — never double-mutates.
    second = retry_quarantine(db, cfg, root_key="work", quarantine_id=qid, max_items=1)
    assert second["resolved"] == 0
    assert SourceIndexScanQuarantineRepository(db).has_blocking("work") is False


# ===================================================================================================
# Config validation + policy fingerprint
# ===================================================================================================
def test_config_threshold_must_be_at_least_one():
    with pytest.raises(ValueError):
        ObsidianMcpConfig(
            vault_root="/tmp/x",
            external_sources=[ExternalSourceRoot(source_root_key="work", path="/tmp/x")],
            source_index_quarantine_retry_threshold=0,
        )


def test_quarantine_threshold_participates_in_policy_fingerprint(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    fp2 = si._root_fingerprint(r, _cfg(root_dir, threshold=2))
    fp5 = si._root_fingerprint(r, _cfg(root_dir, threshold=5))
    assert fp2 != fp5  # a correctness-affecting policy change invalidates prior generations


# ===================================================================================================
# No remote MCP write surface for quarantine (operator-only, local CLI)
# ===================================================================================================
def test_no_remote_quarantine_write_tool_exposed():
    from hb_assistant.nas_mcp.artifact_tools import ALL_PA_TOOLS
    from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS

    all_names = set(ALL_ASSISTANT_TOOLS) | set(ALL_PA_TOOLS)
    assert [n for n in all_names if "quarantine" in n.lower()] == []


def test_quarantine_cli_commands_registered_locally():
    from hb_assistant.cli.source_watch import app

    names = {getattr(c, "name", None) for c in app.registered_commands}
    assert {"quarantine-list", "quarantine-inspect", "quarantine-retry"} <= names
