"""P2: resumable/bounded apply + mtime+size fast-skip for very large source roots.

Exercises scan_source_root against a temp DB: change detection without re-hashing, per-pass bounds,
resume-to-completion, and complete-pass-only delete reconciliation. No NAS, no production data.
"""

from __future__ import annotations

import os
from pathlib import Path

from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import scan_source_root
from hb_assistant.store.migrator import SQLiteMigrator


def _env(tmp_path: Path, n_files: int = 6):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(n_files):
        (root_dir / f"doc{i}.txt").write_text(f"content {i}")
    repo = SourceIndexRepository(db)
    config = ObsidianMcpConfig()
    root = ExternalSourceRoot(source_root_key="r", path=str(root_dir))
    return repo, config, root, root_dir


def test_first_pass_indexes_all_and_completes(tmp_path: Path) -> None:
    repo, config, root, _ = _env(tmp_path, 6)
    rep = scan_source_root(root, repo, config)
    assert rep.indexed == 6
    assert rep.skipped == 0
    assert rep.completed is True
    assert rep.bounded_out is False


def test_rescan_fast_skips_unchanged(tmp_path: Path) -> None:
    repo, config, root, _ = _env(tmp_path, 6)
    scan_source_root(root, repo, config)
    rep2 = scan_source_root(root, repo, config)
    assert rep2.indexed == 0       # nothing re-indexed
    assert rep2.skipped == 6       # all mtime+size fast-skipped
    assert rep2.completed is True


def test_active_index_state_has_mtime_and_size(tmp_path: Path) -> None:
    repo, config, root, root_dir = _env(tmp_path, 3)
    scan_source_root(root, repo, config)
    state = repo.active_index_state("r")
    assert set(state) == {"doc0.txt", "doc1.txt", "doc2.txt"}
    for rel, (mtime_ns, size) in state.items():
        st = (root_dir / rel).stat()
        assert mtime_ns == st.st_mtime_ns
        assert size == st.st_size


def test_changed_file_is_reindexed(tmp_path: Path) -> None:
    repo, config, root, root_dir = _env(tmp_path, 4)
    scan_source_root(root, repo, config)
    target = root_dir / "doc1.txt"
    target.write_text("materially changed content, different size")
    os.utime(target, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))  # bump mtime
    rep = scan_source_root(root, repo, config)
    assert rep.indexed == 1        # only the changed file
    assert rep.skipped == 3


def test_bounded_pass_stops_early_without_delete_reconcile(tmp_path: Path) -> None:
    repo, config, root, root_dir = _env(tmp_path, 6)
    rep = scan_source_root(root, repo, config, max_files_per_pass=2)
    assert rep.indexed == 2
    assert rep.bounded_out is True
    assert rep.completed is False
    assert rep.deleted == 0        # incomplete pass must NOT reconcile deletions


def test_resume_converges_to_complete(tmp_path: Path) -> None:
    repo, config, root, _ = _env(tmp_path, 7)
    passes = 0
    while True:
        rep = scan_source_root(root, repo, config, max_files_per_pass=2)
        passes += 1
        if rep.completed:
            break
        assert rep.bounded_out is True
        assert passes < 20  # guard against a non-converging loop
    # every file ended up indexed exactly once (later passes fast-skip the earlier ones)
    assert len(repo.active_index_state("r")) == 7


def test_delete_reconcile_only_on_complete_pass(tmp_path: Path) -> None:
    repo, config, root, root_dir = _env(tmp_path, 4)
    scan_source_root(root, repo, config)              # index all 4 (doc0..doc3)
    (root_dir / "doc3.txt").unlink()                  # remove one on disk
    # Make the remaining files "changed" so a bounded pass hits its indexing budget and stops
    # BEFORE finishing the walk (bounded_out) — the missing file must NOT be reconciled yet.
    for i in range(3):
        p = root_dir / f"doc{i}.txt"
        p.write_text(f"changed {i} with a different length body")
        os.utime(p, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))
    bounded = scan_source_root(root, repo, config, max_files_per_pass=1)
    assert bounded.bounded_out is True
    assert bounded.completed is False
    assert bounded.deleted == 0
    assert "doc3.txt" in repo.active_index_state("r")  # still active — no reconcile on partial pass
    # a full pass finishes the remaining files and reconciles the deletion
    full = scan_source_root(root, repo, config)
    assert full.completed is True
    assert full.deleted == 1
    assert "doc3.txt" not in repo.active_index_state("r")
