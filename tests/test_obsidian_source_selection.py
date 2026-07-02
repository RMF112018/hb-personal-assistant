"""Phase 10L: direct-file / manifest source selection helpers (source_subroot).

Covers the exact-file selectors added on top of bounded subroot traversal: lexical validation shared
with include-subroot, ``lstat``-only classification (never scandir/open → no hydration), and manifest
loading/classification.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from hb_assistant.obsidian_mcp import source_subroot as ss


def test_validate_include_file_rejects_absolute_dotdot_escape_and_empty(tmp_path: Path) -> None:
    root = tmp_path / "23-435-01 - Tropical"
    root.mkdir()
    for bad in ("/etc/passwd", "../sibling.pdf", "00_Admin/../../escape.pdf", ""):
        with pytest.raises(ss.SubrootError):
            ss.validate_include_file(root, bad)


def test_validate_include_file_rejects_root_itself(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(ss.SubrootError):
        ss.validate_include_file(root, ".")


def test_validate_include_file_accepts_nested_relative_unresolved(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    got = ss.validate_include_file(root, "00_Admin/Permits/Doc.pdf")
    # lexical only: the joined path is returned even though nothing exists on disk yet.
    assert got == root / "00_Admin" / "Permits" / "Doc.pdf"
    assert ss.is_contained(root, got)


def test_classify_include_file_readable_missing_and_dir(tmp_path: Path) -> None:
    f = tmp_path / "a.pdf"
    f.write_text("data", encoding="utf-8")
    assert ss.classify_include_file(f) == "readable"
    assert ss.classify_include_file(tmp_path / "nope.pdf") == "missing"
    assert ss.classify_include_file(tmp_path) == "not_file"  # a directory is not a file


def test_classify_include_file_placeholder_via_lstat_only(tmp_path: Path, monkeypatch) -> None:
    # A dataless on-demand file: st_size>0 but st_blocks==0. Prove classify uses lstat (never open).
    f = tmp_path / "dormant.pdf"
    f.write_text("x", encoding="utf-8")

    def _fake_lstat(path, *a, **k):
        return SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_size=4096, st_blocks=0)

    def _guard_open(*a, **k):  # classification must never open the file (would hydrate)
        raise AssertionError("classify_include_file must not open the file")

    monkeypatch.setattr(ss.os, "lstat", _fake_lstat)
    monkeypatch.setattr("builtins.open", _guard_open)
    assert ss.classify_include_file(f) == "placeholder"


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics differ on Windows")
def test_classify_include_file_symlink_is_not_file(tmp_path: Path) -> None:
    target = tmp_path / "real.pdf"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.pdf"
    os.symlink(target, link)
    assert ss.classify_include_file(link) == "not_file"  # symlinks are never followed


def test_load_source_manifest_ignores_blank_and_comments(tmp_path: Path) -> None:
    m = tmp_path / "m.txt"
    m.write_text("# header comment\n\n00_Admin/Permits/Doc.pdf\n  20_Construction/  \n# tail\n",
                 encoding="utf-8")
    assert ss.load_source_manifest(m) == ["00_Admin/Permits/Doc.pdf", "20_Construction/"]


def test_classify_manifest_entry_subroot_vs_file() -> None:
    assert ss.classify_manifest_entry("20_Construction/") == "subroot"
    assert ss.classify_manifest_entry("00_Admin/Permits/Doc.pdf") == "file"


def test_manifest_entries_pass_same_safety_checks(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    # a manifest entry that escapes must still be rejected by the same validators the CLI uses.
    with pytest.raises(ss.SubrootError):
        ss.validate_include_file(root, "../../escape.pdf")
    with pytest.raises(ss.SubrootError):
        ss.validate_subroot(root, "/etc")
