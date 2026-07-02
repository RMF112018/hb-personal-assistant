"""Phase 10D — bounded project-corpus selector + apply gates. Synthetic temp only; no real corpus/Ollama."""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_index_project_corpus.py"
_spec = importlib.util.spec_from_file_location("index_project_corpus", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_ROWS = [{"project_key": "tropical", "project_number": "23-435-01",
          "display_name": "23-435-01 - Tropical World Nursery Senior Living Facility",
          "procore_project_id": "2525840"}]


@pytest.fixture(autouse=True)
def _patches(monkeypatch):
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    import hb_assistant.construction.analytics.project_summary_readmodel as rm

    class _Fake:
        def build(self):
            return {"projects": _ROWS}
    monkeypatch.setattr(rm, "ProjectSummaryReadModelService", lambda *, db_path=None: _Fake())


def _env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    monkeypatch.setenv("HB_PA_CONFIG",
                       str(_write_yml(tmp_path, vault)))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    base = tmp_path / "synbase"
    troot = base / "NAS - HB" / "Projects" / "2023" / "23-435-01 - Tropical"
    (troot / "10_Preconstruction").mkdir(parents=True)
    (troot / "20_Construction").mkdir(parents=True)
    (troot / "10_Preconstruction" / "RFI 001 Doors.md").write_text("RFI about doors.", encoding="utf-8")
    (troot / "10_Preconstruction" / "Submittal 03.md").write_text("Submittal content.", encoding="utf-8")
    (troot / "20_Construction" / "Cost Report.md").write_text("Cost report.", encoding="utf-8")
    (troot / "20_Construction" / "~$temp.md").write_text("temp", encoding="utf-8")
    (troot / "20_Construction" / ".hidden.md").write_text("hidden", encoding="utf-8")
    (troot / "20_Construction" / "EVICTED file.md").write_text("evicted", encoding="utf-8")
    cfg = {"enabled": True, "vault_root": str(vault), "writes_enabled": True,
           "vault_markdown_write_enabled": True, "source_card_generation_enabled": True,
           "external_source_watch_enabled": False, "source_card_auto_generate_enabled": False,
           "source_summary_auto_generate_enabled": False, "source_note_auto_refresh_enabled": False,
           "external_sources": [{"source_root_key": "syn-work", "path": str(base), "enabled": True}]}
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps(cfg))
    ObsidianMcpConfig.model_validate(cfg)
    return {"db": db, "cfgp": str(cfgp), "vault": vault, "base": base, "troot": troot, "tmp": tmp_path}


def _write_yml(tmp_path, vault):
    y = tmp_path / "c.yml"
    y.write_text(f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
                 f"  obsidian_vault: {vault.as_posix()!r}\n")
    return y


def _args(env, *, apply=False, enrich=False, confirm=True, source_root=None, **over):
    sr = source_root or str(env["troot"])
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--source-root", sr, "--root-key", "syn-work", "--max-files", "100",
         "--evidence-dir", str(env["tmp"] / "ev"), "--backup-dir", str(env["tmp"] / "bk"),
         "--json-output", "--confirm-project-number", "23-435-01", "--confirm-project-key", "tropical"]
    if apply:
        a.append("--apply")
    if enrich:
        a.append("--enrich")
    if confirm:
        a += ["--confirm-source-root", sr, "--confirm-vault-path", str(env["vault"]),
              "--confirm-db-path", env["db"]]
    for k, v in over.items():
        flag = "--" + k.replace("_", "-")
        a.append(flag) if v is True else a.extend([flag, str(v)])
    return a


def _run(argv, capsys):
    rc = mod.main(argv)
    out = capsys.readouterr().out
    return rc, (json.loads(out) if rc == 0 and out.strip() else None)


def test_dry_run_selects_readable_skips_temp_and_reports_identity(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_readability",
                        lambda p: "online_only_or_dataless" if "EVICTED" in p.name else "readable")
    rc, out = _run(_args(env), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["source_root_confirmed"] and out["project_number"] == "23-435-01"
    assert out["project_key"] == "tropical" and out["procore_project_id"] == "2525840"
    assert out["files_selected"] == 3 and out["cloud_evicted"] == 1  # temp/hidden skipped, EVICTED skipped
    assert out["cards_generated"] == 0 and out["ollama_calls"] == 0  # dry-run writes nothing


def test_refuses_confirm_source_root_mismatch(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    argv = _args(env, confirm=False)
    argv += ["--confirm-source-root", str(env["base"]), "--confirm-vault-path", str(env["vault"]),
             "--confirm-db-path", env["db"]]
    assert _run(argv, capsys)[0] == 3


def test_refuses_source_root_outside_configured_root(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    outside = tmp_path / "elsewhere" / "23-435-01 - Tropical"
    outside.mkdir(parents=True)
    assert _run(_args(env, source_root=str(outside)), capsys)[0] == 3


def test_refuses_when_folder_not_project(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    plain = env["base"] / "NAS - HB" / "Projects" / "2023" / "No Number Folder"
    plain.mkdir(parents=True)
    assert _run(_args(env, source_root=str(plain)), capsys)[0] == 3


def test_max_files_cap(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_readability", lambda p: "readable")
    rc, out = _run(_args(env, max_files=1), capsys)
    assert rc == 0 and out["files_selected"] == 1


def test_apply_refusals(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    # confirm mismatch
    assert _run(_args(env, apply=True, confirm=False), capsys)[0] == 3
    # backend listening
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: True)
    assert _run(_args(env, apply=True), capsys)[0] == 3


def test_apply_refuses_when_queue_not_empty(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    c = sqlite3.connect(env["db"])
    c.execute("INSERT INTO source_intelligence_events (event_type,rel_path,source_root_key,status)"
              " VALUES ('modified','x','syn-work','queued')")
    c.commit()
    c.close()
    assert _run(_args(env, apply=True), capsys)[0] == 3


def test_apply_refuses_without_backup_dir(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    argv = [a for a in _args(env, apply=True) if a not in ("--backup-dir", str(env["tmp"] / "bk"))]
    # strip the backup-dir pair
    argv = _strip_flag(argv, "--backup-dir")
    assert mod.main(argv) == 3


def _strip_flag(argv, flag):
    out, i = [], 0
    while i < len(argv):
        if argv[i] == flag:
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out


def test_module_has_no_ollama_or_scan_calls():
    src = _SCRIPT.read_text()
    for forbidden in ("OllamaChatClient", "generate_json", "generate_text", "list_ollama_models",
                      "scan_source_root", "drain_queue", "enqueue_event", "claim_queued"):
        assert forbidden not in src, forbidden


def test_include_subroot_selects_under_subroot_and_keeps_identity(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_readability", lambda p: "readable")
    rc, out = _run(_args(env, include_subroot="20_Construction"), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["include_subroots_requested"] == 1 and out["include_subroots_listable"] == 1
    assert out["include_subroots_failed"] == 0
    assert out["project_number"] == "23-435-01" and out["project_key"] == "tropical"  # from source-root
    assert out["files_selected"] >= 1  # Cost Report.md under 20_Construction
    assert out["cards_generated"] == 0 and out["ollama_calls"] == 0  # dry-run writes nothing


def test_include_subroot_escape_refused(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    assert _run(_args(env, include_subroot="../../escape"), capsys)[0] == 3
    assert _run(_args(env, include_subroot="/etc"), capsys)[0] == 3


def test_include_file_selected_even_when_scandir_fails(tmp_path, monkeypatch, capsys):
    # Prove exact-file selection needs NO directory listing: break every os.scandir and confirm the
    # directly-addressable file is still selected, with identity still derived from --source-root.
    env = _env(tmp_path, monkeypatch)
    nested = env["troot"] / "00_Admin" / "Permits"
    nested.mkdir(parents=True)
    (nested / "Doc.pdf").write_text("pdf", encoding="utf-8")

    def _boom(*a, **k):
        raise OSError(errno.EINTR, "Interrupted system call")

    monkeypatch.setattr(os, "scandir", _boom)
    rc, out = _run(_args(env, include_file="00_Admin/Permits/Doc.pdf"), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["include_files_requested_raw"] == 1 and out["include_files_validated"] == 1
    assert out["include_files_selected"] == 1 and out["files_selected"] == 1
    assert out["project_number"] == "23-435-01" and out["project_key"] == "tropical"
    assert out["cards_generated"] == 0 and out["ollama_calls"] == 0  # dry-run writes nothing


def test_include_file_unsupported_ext_counted_not_selected(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    (env["troot"] / "20_Construction" / "archive.zip").write_text("zip", encoding="utf-8")
    rc, out = _run(_args(env, include_file="20_Construction/archive.zip"), capsys)
    assert rc == 0
    assert out["include_files_validated"] == 1 and out["include_files_selected"] == 0
    assert out["include_files_unsupported_ext"] == 1 and out["files_selected"] == 0


def test_include_file_missing_counted(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, include_file="20_Construction/nope.pdf"), capsys)
    assert rc == 0
    assert out["include_files_missing"] == 1 and out["include_files_selected"] == 0


def test_include_file_escape_refused(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    assert _run(_args(env, include_file="../../escape.pdf"), capsys)[0] == 3
    assert _run(_args(env, include_file="/etc/passwd"), capsys)[0] == 3


def test_source_manifest_mixes_file_and_subroot(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_readability", lambda p: "readable")
    (env["troot"] / "00_Admin").mkdir(parents=True, exist_ok=True)
    (env["troot"] / "00_Admin" / "Doc.pdf").write_text("pdf", encoding="utf-8")
    manifest = env["tmp"] / "manifest.txt"
    manifest.write_text("# operator-local manifest\n00_Admin/Doc.pdf\n20_Construction/\n"
                        "../escape.pdf\n", encoding="utf-8")
    rc, out = _run(_args(env, source_manifest=str(manifest)), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["include_files_requested_raw"] == 2         # Doc.pdf + escape.pdf
    assert out["include_files_validated"] == 1             # escape rejected
    assert out["include_files_containment_rejected"] == 1
    assert out["include_subroots_requested"] == 1          # 20_Construction/
    assert out["files_selected"] >= 2                      # Doc.pdf + files under 20_Construction
