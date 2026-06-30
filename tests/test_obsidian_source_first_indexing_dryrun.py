"""Bounded first-indexing dry-run tool: refusals, caps, read-only, classification. Temp roots only."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_first_indexing_dryrun.py"
_spec = importlib.util.spec_from_file_location("obsidian_source_first_indexing_dryrun", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _write_config(tmp_path: Path, roots: list[dict], vault: Path) -> Path:
    cfg = {"enabled": True, "vault_root": str(vault), "external_sources": roots,
           "unknown_future_key": "ignored"}  # forward-compat: unknown key must be tolerated
    p = tmp_path / "obsidian_mcp_config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir(exist_ok=True)
    return v


def _seed_root(tmp_path: Path) -> Path:
    root = tmp_path / "syn-work-root"
    (root / "25-244").mkdir(parents=True)
    (root / "25-244" / "RFI 032 Door.pdf").write_text("rfi", encoding="utf-8")
    (root / "25-244" / "PCCO 004 Millwork.pdf").write_text("co", encoding="utf-8")
    (root / "25-244" / "Tracker.xlsx").write_text("a,b", encoding="utf-8")
    (root / "25-244" / "photo.png").write_text("img", encoding="utf-8")
    return root


def _base_args(config_path, vault, **extra):
    args = ["--config-path", str(config_path), "--vault-path", str(vault)]
    for k, v in extra.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return args


def test_missing_root_key_lists_roots_no_scan(tmp_path, capsys):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    rc = mod.main(_base_args(cfg, vault))  # no --root-key
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "list_roots" and out["enabled_root_keys"] == ["syn-work"]


def test_disabled_root_refused(tmp_path):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": False}], vault)
    assert mod.main(_base_args(cfg, vault, root_key="syn-work")) == 3


def test_missing_root_refused(tmp_path):
    vault = _vault(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(tmp_path / "nope"), "enabled": True}], vault)
    assert mod.main(_base_args(cfg, vault, root_key="syn-work")) == 3


def test_unknown_root_key_refused(tmp_path):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    assert mod.main(_base_args(cfg, vault, root_key="does-not-exist")) == 3


def test_active_vault_root_refused(tmp_path):
    vault = _vault(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "vault", "path": str(vault), "enabled": True}], vault)
    assert mod.main(_base_args(cfg, vault, root_key="vault")) == 3


def test_quarantine_root_refused(tmp_path):
    vault = _vault(tmp_path)
    quar = tmp_path / "Obsidian Vault - QUARANTINED - SYNTHETIC"  # synthetic name; tests the refusal
    quar.mkdir()
    cfg = _write_config(tmp_path, [{"source_root_key": "quar", "path": str(quar), "enabled": True}], vault)
    assert mod.main(_base_args(cfg, vault, root_key="quar")) == 3


def test_symlinks_recorded_not_followed(tmp_path, capsys):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    external = tmp_path / "external_secret"
    (external / "deep").mkdir(parents=True)
    (external / "deep" / "secret.pdf").write_text("secret", encoding="utf-8")
    (root / "link_dir").symlink_to(external)
    (root / "link_file.pdf").symlink_to(external / "deep" / "secret.pdf")
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    rc = mod.main(_base_args(cfg, vault, root_key="syn-work"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["symlinks_recorded"] >= 2
    # external target never traversed → "secret" never examined (counts come only from the root files)
    assert out["files_examined"] == 4  # the 4 real seed files, not the symlink target


def test_max_files_cap_honored(tmp_path, capsys):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    rc = mod.main(_base_args(cfg, vault, root_key="syn-work", max_files=2))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["files_examined"] == 2 and out["cap_reached"] is True


def test_max_seconds_cap_honored_injected_clock(tmp_path, capsys):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    # Clock jumps past max_seconds after the first read → cap on the first examined file.
    ticks = iter([0.0, 0.0, 999.0, 999.0, 999.0, 999.0, 999.0])
    rc = mod.main(_base_args(cfg, vault, root_key="syn-work", max_seconds=10),
                  now_fn=lambda: next(ticks))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["cap_reached"] is True and out["files_examined"] <= 1


def test_classification_counts_and_no_paths_in_summary(tmp_path, capsys):
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    ev = tmp_path / "ev"
    rc = mod.main(_base_args(cfg, vault, root_key="syn-work", evidence_dir=ev))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # rfi + change_order classify HIGH; png unsupported; xlsx metadata_only.
    assert out["counts_by_document_type"].get("rfi", 0) >= 1
    assert out["counts_by_document_type"].get("change_order", 0) >= 1
    assert sum(out["counts_by_disposition"].values()) == out["files_examined"] == 4
    assert out["counts_by_domain"].get("work", 0) == 4  # syn-work → work
    # Safe summary contains no file paths.
    safe = (ev / "first-indexing-dryrun-syn-work-summary-safe.json").read_text()
    for token in ("RFI 032", "PCCO 004", "25-244", str(tmp_path)):
        assert token not in safe, token
    # Local-sensitive detail DOES carry rel paths (kept local, not committed).
    detail = (ev / "first-indexing-dryrun-syn-work-detail-local-sensitive.json").read_text()
    assert "RFI 032 Door.pdf" in detail


def test_no_db_writes(tmp_path, capsys):
    # Pass a --db-path that does NOT exist; tool must never create/write it (read-only).
    vault = _vault(tmp_path)
    root = _seed_root(tmp_path)
    cfg = _write_config(tmp_path, [{"source_root_key": "syn-work", "path": str(root), "enabled": True}], vault)
    db = tmp_path / "should_not_be_created.sqlite"
    rc = mod.main(_base_args(cfg, vault, root_key="syn-work", db_path=db))
    assert rc == 0
    assert not db.exists()  # no DB connection/write of any kind
