"""Vault quarantine reset script: dry-run safety, full manifest, apply-gate, deletion guards.

All tests use TEMP vault paths (never the production vault) with --allow-nonstandard-vault-path.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_vault_quarantine_reset.py"
_spec = importlib.util.spec_from_file_location("obsidian_vault_quarantine_reset", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "Obsidian Vault"
    (vault / "Work").mkdir(parents=True)
    (vault / "Work" / "note.md").write_text("# work note", encoding="utf-8")
    (vault / "corpus").mkdir()
    (vault / "corpus" / "big.pdf").write_bytes(b"%PDF-1.4 fake")
    (vault / ".git").mkdir()
    (vault / ".git" / "config").write_text("[core]", encoding="utf-8")
    return vault


def test_dry_run_changes_nothing_and_writes_summary(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    ev = tmp_path / "evidence"
    result = mod.do_dry_run(vault, ev, "sess1", full_manifest=False)
    # Nothing renamed/created.
    assert vault.is_dir()
    assert (vault / "Work" / "note.md").is_file()
    assert not list(tmp_path.glob("*QUARANTINED*"))
    summary = Path(result["summary_manifest"])
    assert summary.is_file()
    payload = json.loads(summary.read_text())
    assert payload["manifest_type"] == "summary"
    top = {e["rel_path"] for e in payload["entries"]}
    assert {"Work", "corpus", ".git"} <= top
    assert result["full_manifest"] is None
    assert result["external_roots_touched"] is False


def test_full_manifest_records_every_file(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    ev = tmp_path / "evidence"
    result = mod.do_dry_run(vault, ev, "sess2", full_manifest=True)
    full = Path(result["full_manifest"])
    assert full.is_file()
    lines = full.read_text().splitlines()
    meta = json.loads(lines[0])
    assert meta["kind"] == "manifest_meta" and meta["vault_path"] == str(vault)
    records = [json.loads(line) for line in lines[1:]]
    assert result["full_manifest_file_count"] == len(records) == 3  # note.md, big.pdf, .git/config
    classifications = {r["rel_path"]: r["classification"] for r in records}
    assert classifications["Work/note.md"] == "markdown"
    assert classifications["corpus/big.pdf"] == "corpus"
    assert classifications[".git/config"] == "system_artifact"
    for r in records:
        assert {"rel_path", "kind", "ext", "size_bytes", "mtime_ns", "top_folder",
                "classification", "planned_disposition"} <= set(r)


def test_full_manifest_records_symlinks_without_following(tmp_path: Path) -> None:
    """Symlinks are tagged as symlinks and NEVER followed; external targets are never traversed."""
    vault = _make_vault(tmp_path)
    # External target OUTSIDE the vault whose contents must never appear in the manifest.
    external = tmp_path / "external_target"
    (external / "secret_dir").mkdir(parents=True)
    (external / "secret_dir" / "secret.md").write_text("external secret", encoding="utf-8")
    external_file = tmp_path / "external_file.txt"
    external_file.write_text("external file", encoding="utf-8")
    # Symlinks inside the vault pointing outside it.
    (vault / "link_to_dir").symlink_to(external / "secret_dir")
    (vault / "link_to_file.md").symlink_to(external_file)

    ev = tmp_path / "ev"
    result = mod.do_dry_run(vault, ev, "syms", full_manifest=True)
    records = [json.loads(line) for line in Path(result["full_manifest"]).read_text().splitlines()[1:]]
    by_rel = {r["rel_path"]: r for r in records}

    assert by_rel["link_to_dir"]["kind"] == "symlink"
    assert by_rel["link_to_dir"]["classification"] == "symlink"
    assert by_rel["link_to_file.md"]["kind"] == "symlink"
    # The external target was neither followed nor traversed.
    assert not any("secret" in r["rel_path"] for r in records)
    assert not any(r["rel_path"].startswith("link_to_dir/") for r in records)
    # Summary manifest also tags the top-level symlinks without following.
    summary = json.loads(Path(result["summary_manifest"]).read_text())
    sym_summary = {e["rel_path"]: e for e in summary["entries"] if e["kind"] == "symlink"}
    assert "link_to_dir" in sym_summary and "link_to_file.md" in sym_summary


def test_unsafe_paths_refused(tmp_path: Path) -> None:
    ev = str(tmp_path / "ev")
    for bad in ("/", str(Path.home()), str(Path.home() / "Documents"), ""):
        rc = mod.main(["--vault-path", bad, "--evidence-dir", ev, "--allow-nonstandard-vault-path"])
        assert rc == 3, bad


def test_nonstandard_path_refused_without_flag(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    rc = mod.main(["--vault-path", str(vault), "--evidence-dir", str(tmp_path / "ev")])
    assert rc == 3  # not the configured default and flag not passed


def test_apply_refuses_without_full_manifest(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    ev = tmp_path / "ev"
    ev.mkdir()
    with pytest.raises(mod.ResetError):
        mod.do_apply(vault, ev, "nomanifest", copy_safe_obsidian_settings=False)
    assert vault.is_dir()  # untouched


def test_apply_quarantines_and_creates_clean_tree(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    ev = tmp_path / "ev"
    mod.do_dry_run(vault, ev, "go", full_manifest=True)  # required review step
    receipt = mod.do_apply(vault, ev, "go", copy_safe_obsidian_settings=False)

    quarantine = Path(receipt["quarantine_path"])
    assert quarantine.is_dir()
    assert (quarantine / "Work" / "note.md").is_file()        # old content preserved aside
    assert vault.is_dir()
    for rel in ("Work/01 Projects", "Home/04 Finance", "Source Notes/Work",
                "Source Notes/Home", "Source Notes/Shared", "99 System/Receipts"):
        assert (vault / rel).is_dir(), rel
    assert (vault / "README.md").is_file()
    assert (vault / "99 System" / "Receipts").glob("reset-receipt-go.json")
    assert Path(receipt["receipt_path"]).is_file()
    assert receipt["external_roots_touched"] is False
    assert "rollback" in receipt


def test_apply_full_manifest_must_match_vault_path(tmp_path: Path) -> None:
    vault_a = _make_vault(tmp_path)
    vault_b = tmp_path / "Other Vault"
    vault_b.mkdir()
    ev = tmp_path / "ev"
    mod.do_dry_run(vault_a, ev, "x", full_manifest=True)  # manifest is for vault_a
    with pytest.raises(mod.ResetError):
        mod._verify_full_manifest_for_apply(vault_b, ev, "x")


def test_copy_safe_obsidian_settings(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    (vault / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")  # not whitelisted
    ev = tmp_path / "ev"
    mod.do_dry_run(vault, ev, "s", full_manifest=True)
    mod.do_apply(vault, ev, "s", copy_safe_obsidian_settings=True)
    assert (vault / ".obsidian" / "app.json").is_file()
    assert not (vault / ".obsidian" / "workspace.json").exists()


def test_delete_quarantine_requires_confirm_and_pattern(tmp_path: Path) -> None:
    ev = tmp_path / "ev"
    # No confirm path.
    with pytest.raises(mod.ResetError):
        mod.do_delete_quarantine("", ev, "d")
    # A real dir that is NOT a quarantine.
    normal = tmp_path / "Obsidian Vault"
    normal.mkdir()
    with pytest.raises(mod.ResetError):
        mod.do_delete_quarantine(str(normal), ev, "d")
    # A valid quarantine dir is deleted + receipt written.
    quar = tmp_path / "Obsidian Vault - QUARANTINED - d"
    quar.mkdir()
    receipt = mod.do_delete_quarantine(str(quar), ev, "d")
    assert not quar.exists()
    assert Path(receipt["receipt_path"]).is_file()


def test_apply_refused_when_backend_listening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = _make_vault(tmp_path)
    ev = tmp_path / "ev"
    mod.do_dry_run(vault, ev, "b", full_manifest=True)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: True)
    rc = mod.main(["--vault-path", str(vault), "--evidence-dir", str(ev), "--session-id", "b",
                   "--apply", "--allow-nonstandard-vault-path"])
    assert rc == 3
    assert vault.is_dir() and not list(tmp_path.glob("*QUARANTINED*"))  # untouched
