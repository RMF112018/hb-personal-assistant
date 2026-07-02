"""Phase 10L: bounded subroot traversal safety (source_subroot)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_subroot as ss


def test_validate_rejects_absolute_dotdot_and_escape(tmp_path: Path) -> None:
    root = tmp_path / "23-435-01 - Tropical"
    root.mkdir()
    with pytest.raises(ss.SubrootError):
        ss.validate_subroot(root, "/etc/passwd")
    with pytest.raises(ss.SubrootError):
        ss.validate_subroot(root, "../sibling")
    with pytest.raises(ss.SubrootError):
        ss.validate_subroot(root, "20_Construction/../../escape")
    with pytest.raises(ss.SubrootError):
        ss.validate_subroot(root, "")


def test_validate_accepts_nested_relative(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "20_Construction" / "Permits").mkdir(parents=True)
    got = ss.validate_subroot(root, "20_Construction/Permits")
    assert ss.is_contained(root, got)
    assert got == root / "20_Construction" / "Permits"


def test_scandir_listable_true_false(tmp_path: Path) -> None:
    d = tmp_path / "d"
    d.mkdir()
    assert ss.scandir_listable(d) is True
    assert ss.scandir_listable(tmp_path / "missing") is False


def test_walk_files_contained_and_bounded(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    base = root / "20_Construction" / "Permits"
    base.mkdir(parents=True)
    (base / "a.pdf").write_text("a", encoding="utf-8")
    (base / "sub").mkdir()
    (base / "sub" / "b.docx").write_text("b", encoding="utf-8")
    files, stats = ss.walk_files(base, root, max_files=100)
    names = {p.name for p in files}
    assert names == {"a.pdf", "b.docx"}
    assert stats["listable"] == 1 and stats["containment_rejected"] == 0


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics differ on Windows")
def test_walk_files_does_not_recurse_symlink_dirs(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    base = root / "Permits"
    outside = tmp_path / "outside"
    (outside).mkdir()
    (outside / "secret.pdf").write_text("x", encoding="utf-8")
    base.mkdir(parents=True)
    (base / "real.pdf").write_text("r", encoding="utf-8")
    os.symlink(outside, base / "link_to_outside")  # symlink dir → must not be followed
    files, stats = ss.walk_files(base, root, max_files=100)
    names = {p.name for p in files}
    assert "real.pdf" in names
    assert "secret.pdf" not in names            # symlink dir not followed → outside file never reached
    assert stats["symlink_dirs_skipped"] >= 1
