"""Phase 10L: read-only source-root availability probe.

Proves the resilient scandir walk counts supported/unsupported/temp files, survives an EINTR on one
subdir (counting it and continuing over siblings), reports root-not-listable distinctly, and — critically
— NEVER opens a file classified as a placeholder/online-only (so nothing is ever hydrated), even when
byte-read probing is explicitly enabled.
"""

from __future__ import annotations

import errno
import importlib.util
import os
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "obsidian_source_root_availability_probe",
        _REPO / "scripts" / "obsidian_source_root_availability_probe.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "sub").mkdir(parents=True)
    (root / "a.pdf").write_text("pdf", encoding="utf-8")
    (root / "b.eml").write_text("eml", encoding="utf-8")
    (root / "c.zip").write_text("zip", encoding="utf-8")   # unsupported ext
    (root / "~$tmp.docx").write_text("temp", encoding="utf-8")  # temp
    (root / "sub" / "d.docx").write_text("docx", encoding="utf-8")
    return root


def test_counts_supported_unsupported_temp_and_root_listable(tmp_path: Path) -> None:
    mod = _load()
    out = mod.probe(str(_tree(tmp_path)), max_files=500, max_dirs=1000, read_probe_limit=0,
                    allow_read_probe=False)
    s = out["safe"]
    assert s["root_exists"] and s["root_is_dir"] and s["root_listable"]
    assert s["read_probe_mode"] == "stat_only"
    assert s["candidate_doc_ext_count"] == 2   # a.pdf + sub/d.docx
    assert s["candidate_eml_count"] == 1       # b.eml
    assert s["unsupported_ext_count"] == 1     # c.zip
    assert s["temp_skipped_count"] == 1        # ~$tmp.docx
    assert s["files_read_probe_ok"] == 0 and s["files_read_probe_failed"] == 0


def test_eintr_on_subdir_is_counted_and_walk_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    root = _tree(tmp_path)
    real_scandir = os.scandir

    def _boom(path):
        if str(path).endswith("/sub"):
            raise OSError(errno.EINTR, "Interrupted system call")
        return real_scandir(path)

    monkeypatch.setattr(mod.os, "scandir", _boom)
    out = mod.probe(str(root), max_files=500, max_dirs=1000, read_probe_limit=0, allow_read_probe=False)
    s = out["safe"]
    assert s["root_listable"] is True
    assert s["interrupted_system_call_count"] >= 1      # the sub dir EINTR was counted
    assert s["candidate_doc_ext_count"] >= 1            # root-level a.pdf still seen (walk continued)


def test_root_not_listable_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    root = _tree(tmp_path)
    monkeypatch.setattr(mod, "_scandir", lambda p: (None, OSError(errno.EINTR, "x")))
    out = mod.probe(str(root), max_files=500, max_dirs=1000, read_probe_limit=0, allow_read_probe=False)
    s = out["safe"]
    assert s["root_listable"] is False
    assert s["files_seen"] == 0
    assert s["interrupted_system_call_count"] == 1


def test_placeholder_is_never_opened_even_with_read_probe(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    root = _tree(tmp_path)
    # Classify a.pdf as a placeholder; everything else readable.
    real = mod.classify_readability

    def _fake(path: str) -> str:
        return "placeholder" if path.endswith("a.pdf") else real(path)

    monkeypatch.setattr(mod, "classify_readability", _fake)
    # Guard: fail loudly if the placeholder is ever opened.
    real_open = open

    def _guard_open(file, *a, **k):
        assert not str(file).endswith("a.pdf"), "placeholder must never be opened (would hydrate)"
        return real_open(file, *a, **k)

    monkeypatch.setattr("builtins.open", _guard_open)
    out = mod.probe(str(root), max_files=500, max_dirs=1000, read_probe_limit=25, allow_read_probe=True)
    s = out["safe"]
    assert s["cloud_placeholder_or_unavailable_count"] == 1   # a.pdf classified placeholder
    assert s["read_probe_mode"] == "byte_read"
    # Read-probe ran on real-local supported files (d.docx), never the placeholder.
    assert s["files_read_probe_ok"] >= 1


def test_read_probe_requires_confirm_flag(tmp_path: Path) -> None:
    mod = _load()
    root = _tree(tmp_path)
    rc = mod.main(["--source-root", str(root), "--read-probe-limit", "5"])  # no confirm flag
    assert rc == 3
