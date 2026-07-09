"""P1: streaming source-tree walk + per-root file cap (large-root scale fix).

These cover the replacement of ``sorted(root_path.rglob("*"))`` with a lazy, dir-pruning
``walk_source_tree`` and the new per-root ``max_files`` override, without needing a NAS or a DB.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_bootstrap import _file_plan_counts
from hb_assistant.obsidian_mcp.source_indexer import (
    effective_max_files,
    walk_source_tree,
)


def _srcroot(tmp_path: Path) -> Path:
    # Dedicated subdir: the suite's conftest may seed app-support/vault into tmp_path itself.
    root = tmp_path / "srcroot"
    root.mkdir()
    return root


def _build_tree(root: Path) -> None:
    (root / "a.txt").write_text("a")
    (root / "b.md").write_text("b")
    (root / ".secret.txt").write_text("s")  # hidden file -> skipped
    git = root / ".git"  # hidden dir -> pruned (never descended)
    git.mkdir()
    (git / "config").write_text("x")
    nm = root / "node_modules"  # excluded segment -> pruned
    nm.mkdir()
    (nm / "dep.js").write_text("x")
    (nm / "deep").mkdir()
    (nm / "deep" / "buried.js").write_text("x")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("c")
    nested = sub / "nested"
    nested.mkdir()
    (nested / "d.txt").write_text("d")


def _files(root: Path, config: ObsidianMcpConfig) -> list[str]:
    return sorted(
        rel for kind, _abs, rel in walk_source_tree(root, config) if kind == "file"
    )


def test_walk_is_lazy_generator(tmp_path: Path) -> None:
    root = _srcroot(tmp_path)
    _build_tree(root)
    gen = walk_source_tree(root, ObsidianMcpConfig())
    assert isinstance(gen, Iterator)
    assert hasattr(gen, "__next__")  # not a pre-built list


def test_walk_prunes_hidden_and_excluded_dirs(tmp_path: Path) -> None:
    root = _srcroot(tmp_path)
    _build_tree(root)
    files = _files(root, ObsidianMcpConfig())
    # only the four real document files; nothing under .git/ or node_modules/, no hidden file
    assert files == ["a.txt", "b.md", "sub/c.txt", "sub/nested/d.txt"]
    assert not any(".git" in f for f in files)
    assert not any("node_modules" in f for f in files)
    assert ".secret.txt" not in files


def test_walk_want_dirs_yields_dirs_but_not_pruned_ones(tmp_path: Path) -> None:
    root = _srcroot(tmp_path)
    _build_tree(root)
    dirs = sorted(
        rel for kind, _abs, rel in walk_source_tree(root, ObsidianMcpConfig(), want_dirs=True)
        if kind == "dir"
    )
    assert dirs == ["sub", "sub/nested"]  # .git and node_modules pruned


def test_pruned_dir_children_never_visited(tmp_path: Path) -> None:
    # A pruned subtree must not be descended even if it is huge — assert a buried file is absent.
    root = _srcroot(tmp_path)
    _build_tree(root)
    files = _files(root, ObsidianMcpConfig())
    assert "node_modules/deep/buried.js" not in files


def test_effective_max_files_per_root_override() -> None:
    config = ObsidianMcpConfig(external_source_scan_max_files=5000)
    default_root = ExternalSourceRoot(source_root_key="vault", path="/tmp")
    capped_root = ExternalSourceRoot(source_root_key="work", path="/tmp", max_files=100000)
    assert effective_max_files(default_root, config) == 5000
    assert effective_max_files(capped_root, config) == 100000


def test_max_files_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ExternalSourceRoot(source_root_key="x", path="/tmp", max_files=0)
    with pytest.raises(ValueError):
        ExternalSourceRoot(source_root_key="x", path="/tmp", max_files=-5)


def test_file_plan_counts_honors_per_root_cap(tmp_path: Path) -> None:
    root_dir = _srcroot(tmp_path)
    for i in range(10):
        (root_dir / f"f{i}.txt").write_text("x")
    config = ObsidianMcpConfig()
    # global default is high enough -> all 10 counted, not truncated
    root_all = ExternalSourceRoot(source_root_key="r", path=str(root_dir))
    plan = _file_plan_counts(root_all, config)
    assert plan == {"root_found": True, "files_seen": 10, "would_index": 10, "truncated": False}
    # per-root cap of 3 -> truncated at 3
    root_capped = ExternalSourceRoot(source_root_key="r", path=str(root_dir), max_files=3)
    plan_capped = _file_plan_counts(root_capped, config)
    assert plan_capped["files_seen"] == 3
    assert plan_capped["truncated"] is True


def test_file_plan_counts_missing_root(tmp_path: Path) -> None:
    root = ExternalSourceRoot(source_root_key="r", path=str(tmp_path / "does-not-exist"))
    assert _file_plan_counts(root, ObsidianMcpConfig()) == {
        "root_found": False,
        "files_seen": 0,
        "would_index": 0,
    }
