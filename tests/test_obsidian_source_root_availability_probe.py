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


def test_include_subroot_traversed_when_root_not_listable(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    root = tmp_path / "proj"
    sub = root / "20_Construction" / "Permits"
    sub.mkdir(parents=True)
    (sub / "a.pdf").write_text("a", encoding="utf-8")
    real = mod._scandir

    def _fake(path):  # root won't enumerate, but the subroot still does
        if os.path.abspath(os.fspath(path)) == os.path.abspath(str(root)):
            return None, OSError(errno.EINTR, "Interrupted system call")
        return real(path)

    monkeypatch.setattr(mod, "_scandir", _fake)
    base = mod.validate_subroot(Path(str(root)), "20_Construction/Permits")
    out = mod.probe(str(root), max_files=100, max_dirs=1000, read_probe_limit=0,
                    allow_read_probe=False, include_subroots=[base])
    s = out["safe"]
    assert s["source_root_listable"] is False
    assert s["include_subroots_requested"] == 1 and s["include_subroots_listable"] == 1
    assert s["candidate_doc_ext_count_under_include_subroots"] >= 1
    assert s["files_seen_under_include_subroots"] >= 1


def test_include_subroot_absolute_or_dotdot_refused(tmp_path: Path) -> None:
    mod = _load()
    root = tmp_path / "proj"
    root.mkdir()
    assert mod.main(["--source-root", str(root), "--include-subroot", "/etc"]) == 3
    assert mod.main(["--source-root", str(root), "--include-subroot", "../escape"]) == 3


def test_include_file_selected_even_when_all_scandir_fails(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    # The crux: an exact file is confirmed by lstat while EVERY os.scandir raises EINTR (parent
    # directory unenumerable). Selection must NOT depend on any directory listing.
    mod = _load()
    root = tmp_path / "proj"
    sub = root / "00_Admin" / "Permits"
    sub.mkdir(parents=True)
    (sub / "Doc.pdf").write_text("pdf", encoding="utf-8")

    def _boom(*a, **k):
        raise OSError(errno.EINTR, "Interrupted system call")

    monkeypatch.setattr(mod.os, "scandir", _boom)
    vf = mod.validate_include_file(root, "00_Admin/Permits/Doc.pdf")
    out = mod.probe(str(root), max_files=100, max_dirs=100, read_probe_limit=0,
                    allow_read_probe=False, include_files=[vf], include_files_requested_raw=1)
    s = out["safe"]
    assert s["source_root_listable"] is False           # parent won't enumerate
    assert s["include_files_requested_raw"] == 1 and s["include_files_validated"] == 1
    assert s["include_files_lstat_ok"] == 1 and s["include_files_selected_readable"] == 1
    assert s["include_files_missing"] == 0 and s["include_files_unavailable_or_placeholder"] == 0


def test_include_file_missing_and_dir_counted(tmp_path: Path) -> None:
    mod = _load()
    root = tmp_path / "proj"
    (root / "sub").mkdir(parents=True)
    vmissing = mod.validate_include_file(root, "sub/nope.pdf")
    vdir = mod.validate_include_file(root, "sub")
    out = mod.probe(str(root), max_files=100, max_dirs=100, read_probe_limit=0,
                    allow_read_probe=False, include_files=[vmissing, vdir],
                    include_files_requested_raw=2)
    s = out["safe"]
    assert s["include_files_missing"] == 1 and s["include_files_not_files"] == 1
    assert s["include_files_selected_readable"] == 0


def test_include_file_absolute_or_dotdot_refused(tmp_path: Path) -> None:
    mod = _load()
    root = tmp_path / "proj"
    root.mkdir()
    assert mod.main(["--source-root", str(root), "--include-file", "/etc/passwd"]) == 3
    assert mod.main(["--source-root", str(root), "--include-file", "../escape.pdf"]) == 3


def test_source_manifest_file_entry_selected_and_bad_entry_counted(tmp_path: Path,
                                                                   capsys) -> None:
    mod = _load()
    root = tmp_path / "proj"
    sub = root / "00_Admin"
    sub.mkdir(parents=True)
    (sub / "Doc.pdf").write_text("pdf", encoding="utf-8")
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("# operator manifest\n00_Admin/Doc.pdf\n../escape.pdf\n", encoding="utf-8")
    rc = mod.main(["--source-root", str(root), "--source-manifest", str(manifest)])
    assert rc == 0
    import json
    s = json.loads(capsys.readouterr().out)
    assert s["include_files_requested_raw"] == 2       # both file entries counted raw
    assert s["include_files_validated"] == 1           # only one passed safety checks
    assert s["include_files_containment_rejected"] == 1
    assert s["include_files_selected_readable"] == 1
