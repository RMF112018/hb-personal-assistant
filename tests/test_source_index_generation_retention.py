"""Generation retention/cleanup (deployment-readiness gate 5).

Bounded, FAIL-CLOSED pruning of source_index_scan_generations: keep the N most-recent rows per root, but
NEVER prune the active generation or the latest COMPLETED generation (health/watcher trust them).

Scratch DBs only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "g.db")
    SQLiteMigrator(db_path=db).apply()
    return db


def _mk(db: str, root: str, gid: str, status: str, seq: int) -> None:
    """Insert a generation row with a controlled started_at (seq → recency)."""
    ts = f"2026-07-11T00:{seq:02d}:00+00:00"
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO source_index_scan_generations "
        "(generation_id, root_key, status, traversal_version, root_path_hash, policy_fingerprint, "
        " started_at, updated_at) VALUES (?,?,?,1,'rph','fp',?,?)",
        (gid, root, status, ts, ts),
    )
    c.commit()
    c.close()


def _ids(db: str, root: str) -> list[str]:
    c = sqlite3.connect(db)
    rows = [
        r[0]
        for r in c.execute(
            "SELECT generation_id FROM source_index_scan_generations WHERE root_key=? "
            "ORDER BY started_at DESC, rowid DESC",
            (root,),
        ).fetchall()
    ]
    c.close()
    return rows


def test_prune_keeps_n_most_recent(tmp_path):
    db = _db(tmp_path)
    for i in range(10):
        _mk(db, "k", f"g{i:02d}", "completed", i)  # g09 newest
    repo = SourceIndexScanGenerationsRepository(db)
    res = repo.prune_generations("k", keep=3)
    assert res["total_pruned"] == 7
    assert _ids(db, "k") == ["g09", "g08", "g07"]  # 3 most recent survive


def test_prune_always_keeps_latest_completed_outside_window(tmp_path):
    db = _db(tmp_path)
    _mk(db, "k", "done-old", "completed", 0)  # OLDEST, only completed
    for i in range(1, 11):
        _mk(db, "k", f"fail{i:02d}", "failed", i)  # 10 newer failures
    repo = SourceIndexScanGenerationsRepository(db)
    res = repo.prune_generations("k", keep=3)
    surviving = set(_ids(db, "k"))
    assert "done-old" in surviving  # authoritative completed retained despite being oldest
    assert surviving == {"done-old", "fail10", "fail09", "fail08"}  # 3 recent + the completed
    assert res["total_pruned"] == 7


def test_prune_always_keeps_active_generation(tmp_path):
    db = _db(tmp_path)
    _mk(db, "k", "live", "running", 0)  # OLDEST, the one active generation
    for i in range(1, 11):
        _mk(db, "k", f"done{i:02d}", "completed", i)
    repo = SourceIndexScanGenerationsRepository(db)
    repo.prune_generations("k", keep=2)
    surviving = set(_ids(db, "k"))
    assert "live" in surviving  # active generation never pruned
    assert surviving == {"live", "done10", "done09"}  # active + 2 most recent completed


def test_keep_floors_at_one(tmp_path):
    db = _db(tmp_path)
    for i in range(5):
        _mk(db, "k", f"g{i}", "completed", i)
    repo = SourceIndexScanGenerationsRepository(db)
    res = repo.prune_generations("k", keep=0)
    assert res["keep"] == 1
    assert _ids(db, "k") == ["g4"]  # only the most recent (also latest completed)


def test_dry_run_reports_without_deleting(tmp_path):
    db = _db(tmp_path)
    for i in range(10):
        _mk(db, "k", f"g{i:02d}", "completed", i)
    repo = SourceIndexScanGenerationsRepository(db)
    res = repo.prune_generations("k", keep=2, dry_run=True)
    assert res["dry_run"] is True
    assert res["total_pruned"] == 8
    assert len(_ids(db, "k")) == 10  # nothing actually deleted


def test_prune_all_roots(tmp_path):
    db = _db(tmp_path)
    for root in ("a", "b"):
        for i in range(5):
            _mk(db, root, f"{root}{i}", "completed", i)
    repo = SourceIndexScanGenerationsRepository(db)
    res = repo.prune_generations(None, keep=2)
    assert res["pruned_by_root"] == {"a": 3, "b": 3}
    assert len(_ids(db, "a")) == 2 and len(_ids(db, "b")) == 2


def test_prune_noop_when_within_window(tmp_path):
    db = _db(tmp_path)
    for i in range(3):
        _mk(db, "k", f"g{i}", "completed", i)
    repo = SourceIndexScanGenerationsRepository(db)
    res = repo.prune_generations("k", keep=20)
    assert res["total_pruned"] == 0
    assert len(_ids(db, "k")) == 3


def test_cli_prune_generations_smoke(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from hb_assistant.cli import source_watch as sw
    from hb_assistant.cli.main import app
    from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig

    db = _db(tmp_path)
    for i in range(6):
        _mk(db, "k", f"g{i}", "completed", i)
    monkeypatch.setattr(sw, "_db_path", lambda _db: db)
    monkeypatch.setattr(sw, "_obsidian_config", lambda: ObsidianMcpConfig())
    res = CliRunner().invoke(
        app, ["source-watch", "prune-generations", "--root-key", "k", "--keep", "2", "--db", db]
    )
    assert res.exit_code == 0
    assert '"total_pruned": 4' in res.stdout
    assert len(_ids(db, "k")) == 2
