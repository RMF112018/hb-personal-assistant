"""Phase 10E — bounded `.eml` archive indexer script: gates, apply, idempotency, accounting.

Synthetic temp env only; no real corpus/email/Ollama. Mirrors the Phase 10D corpus-indexer test harness.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from email.message import EmailMessage
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import (
    _VAULT_ROOT_KEY,
    is_email_archive_path,
    is_source_notes_path,
    scan_vault_notes,
)
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_index_eml_archive.py"
_spec = importlib.util.spec_from_file_location("index_eml_archive", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_ROWS = [{"project_key": "tropical", "project_number": "23-435-01",
          "display_name": "23-435-01 - Tropical World Nursery Senior Living Facility",
          "procore_project_id": "2525840"}]


@pytest.fixture(autouse=True)
def _patches(monkeypatch):
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_readability", lambda p: "readable")
    import hb_assistant.construction.analytics.project_summary_readmodel as rm

    class _Fake:
        def build(self):
            return {"projects": _ROWS}
    monkeypatch.setattr(rm, "ProjectSummaryReadModelService", lambda *, db_path=None: _Fake())


def _eml_bytes(subject, frm, to, *, thread=None, attach=None) -> bytes:
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = frm
    m["To"] = to
    m["Message-ID"] = f"<{abs(hash(subject)) % 100000}@mail.example>"
    m["Date"] = "Thu, 14 Aug 2025 10:30:00 -0400"
    if thread:
        m["Thread-Topic"] = thread
    m.set_content("Body of the email.\n\n> quoted reply chain line\n")
    if attach:
        m.add_attachment(b"%PDF data", maintype="application", subtype="pdf", filename=attach)
    return m.as_bytes()


def _env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    y = tmp_path / "c.yml"
    y.write_text(f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
                 f"  obsidian_vault: {vault.as_posix()!r}\n")
    monkeypatch.setenv("HB_PA_CONFIG", str(y))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    base = tmp_path / "synbase"
    troot = base / "NAS - HB" / "Projects" / "2023" / "23-435-01 - Tropical" / "20_Construction"
    troot.mkdir(parents=True)
    (troot / "RE Fire Alarm Design.eml").write_bytes(
        _eml_bytes("RE: TWN Fire Alarm Design", "Jane Roe <jane@powerdesign.example>",
                   "John Doe <john@hbconstruction.example>", thread="TWN Fire Alarm Design",
                   attach="proposal.pdf"))
    (troot / "FW Fire Alarm Design.eml").write_bytes(
        _eml_bytes("FW: TWN Fire Alarm Design", "Mark <mark@subcontractor.example>",
                   "pm@hbconstruction.example", thread="TWN Fire Alarm Design"))
    (troot / "Elevator Shaft.eml").write_bytes(
        _eml_bytes("Elevator shaft coordination", "eng@aor.example", "gc@hbconstruction.example",
                   thread="Elevator shaft coordination"))
    cfg = {"enabled": True, "vault_root": str(vault), "writes_enabled": True,
           "vault_markdown_write_enabled": True, "source_card_generation_enabled": True,
           "external_source_watch_enabled": False, "source_card_auto_generate_enabled": False,
           "source_summary_auto_generate_enabled": False, "source_note_auto_refresh_enabled": False,
           "external_sources": [{"source_root_key": "syn-work", "path": str(base), "enabled": True}]}
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps(cfg))
    config = ObsidianMcpConfig.model_validate(cfg)
    return {"db": db, "cfgp": str(cfgp), "vault": vault, "base": base,
            "troot": base / "NAS - HB" / "Projects" / "2023" / "23-435-01 - Tropical",
            "config": config, "repo": SourceIndexRepository(db), "tmp": tmp_path}


def _args(env, *, apply=False, update=False, confirm=True, source_root=None, **over):
    sr = source_root or str(env["troot"])
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--source-root", sr, "--root-key", "syn-work", "--max-eml", "10",
         "--evidence-dir", str(env["tmp"] / "ev"), "--backup-dir", str(env["tmp"] / "bk"),
         "--json-output", "--confirm-project-number", "23-435-01", "--confirm-project-key", "tropical"]
    if apply:
        a.append("--apply")
    if update:
        a.append("--update")
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


def test_dry_run_selects_writes_nothing(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["project_number"] == "23-435-01" and out["procore_project_id"] == "2525840"
    assert out["eml_selected"] == 3 and out["eml_found"] == 3
    assert out["source_cards_generated"] == 0 and out["archive_notes_created"] == 0
    assert out["ollama_calls"] == 0
    # nothing written to the vault
    assert not list(env["vault"].rglob("*.md"))


def test_apply_creates_archive_notes_and_email_cards(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, apply=True), capsys)
    assert rc == 0 and out["mode"] == "apply"
    assert out["eml_parsed"] == 3 and out["eml_parse_failed"] == 0
    assert out["source_cards_generated"] == 3 and out["archive_notes_created"] == 3
    assert out["graph_facts_written"] == 3 and out["emails_with_attachments"] == 1
    assert out["attachments_total"] == 1 and out["plain_body_present"] == 3
    assert out["queue_delta"] == 0 and out["ollama_calls"] == 0
    # amendment #1: archive notes are NOT generated-note rows.
    assert out["generated_note_delta"] == 3  # only the 3 cards
    assert out["vault_markdown_delta"] == 6  # 3 cards + 3 archive notes
    # rollback bundle exists
    assert (env["tmp"] / "bk" / "db-backup.sqlite").is_file()
    assert (env["tmp"] / "bk" / "rollback-manifest.json").is_file()
    # every email card is document_type: email and links to an archive note without the body
    cards = list((env["vault"] / "Source Notes" / "Work").glob("*.md"))
    assert len(cards) == 3
    for c in cards:
        t = c.read_text(encoding="utf-8")
        assert "document_type: " + '"email"' in t or "document_type: email" in t
        assert "hb-email:start" in t and "Full email archive:" in t
        assert "Body of the email." not in t  # concise card carries no body


def test_archive_notes_are_not_cards_and_protected_from_self_index(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env, apply=True), capsys)
    # amendment #4: archive notes live under a SEPARATE root Email Archive/Work/ (NOT Source Notes)
    assert not (env["vault"] / "Source Notes" / "Email Archive").exists()
    archives = list((env["vault"] / "Email Archive" / "Work").rglob("*.md"))
    assert len(archives) == 3
    gen_rows = env["repo"].list_generated_notes(statuses=("generated",))
    gen_paths = {r["note_rel_path"] for r in gen_rows}
    # amendment #4: no archive note is recorded as a generated (card) note
    assert all("Email Archive" not in p for p in gen_paths)
    archive_rels = set()
    for a in archives:
        rel = str(a.relative_to(env["vault"]))
        archive_rels.add(rel.replace("\\", "/"))
        assert is_email_archive_path(rel)  # protected from self-indexing
        assert not is_source_notes_path(rel, env["config"])  # NOT a Source Notes card path
        assert a.read_text(encoding="utf-8").startswith("---\nnote_type: email_archive")
    # amendment #4 proof: a full vault scan never indexes an archive note into the note FTS —
    # full email bodies/addresses must never reach obsidian_note rows.
    scan_vault_notes(env["repo"], env["config"])
    indexed = env["repo"].active_rel_paths(_VAULT_ROOT_KEY)
    assert not (archive_rels & indexed)


def test_update_upgrades_existing_no_duplicate_card(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env, apply=True), capsys)
    cards_before = sorted(p.name for p in (env["vault"] / "Source Notes" / "Work").glob("*.md"))
    rows_before = len(env["repo"].list_generated_notes(statuses=("generated",)))
    # second apply WITH --update: upgrade in place, no duplicates
    rc, out = _run(_args(env, apply=True, update=True), capsys)
    assert rc == 0
    assert out["source_cards_updated"] == 3 and out["source_cards_generated"] == 0
    assert out["archive_notes_updated"] == 3 and out["archive_notes_created"] == 0
    assert out["generated_note_delta"] == 0  # no new card rows
    cards_after = sorted(p.name for p in (env["vault"] / "Source Notes" / "Work").glob("*.md"))
    assert cards_after == cards_before  # same files, no duplicate card
    assert len(env["repo"].list_generated_notes(statuses=("generated",))) == rows_before


def test_second_apply_without_update_skips(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env, apply=True), capsys)
    capsys.readouterr()
    rc, out = _run(_args(env, apply=True), capsys)
    assert rc == 0 and out["already_indexed"] == 3
    assert out["source_cards_generated"] == 0 and out["archive_notes_created"] == 0


def test_refusals(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    # confirm mismatch
    assert _run(_args(env, apply=True, confirm=False), capsys)[0] == 3
    # source root outside configured external root
    outside = tmp_path / "elsewhere" / "23-435-01 - Tropical"
    outside.mkdir(parents=True)
    assert _run(_args(env, source_root=str(outside)), capsys)[0] == 3
    # backend listening
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: True)
    assert _run(_args(env, apply=True), capsys)[0] == 3


def test_apply_refuses_without_backup_dir(tmp_path, monkeypatch):
    env = _env(tmp_path, monkeypatch)
    argv = _args(env, apply=True)
    out, i = [], 0
    while i < len(argv):
        if argv[i] == "--backup-dir":
            i += 2
            continue
        out.append(argv[i])
        i += 1
    assert mod.main(out) == 3


def test_apply_refuses_when_queue_not_empty(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    c = sqlite3.connect(env["db"])
    c.execute("INSERT INTO source_intelligence_events (event_type,rel_path,source_root_key,status)"
              " VALUES ('modified','x','syn-work','queued')")
    c.commit()
    c.close()
    assert _run(_args(env, apply=True), capsys)[0] == 3


def test_module_has_no_ollama_or_scan_calls():
    src = _SCRIPT.read_text()
    for forbidden in ("OllamaChatClient", "generate_json", "generate_text", "list_ollama_models",
                      "scan_source_root", "drain_queue", "enqueue_event", "claim_queued"):
        assert forbidden not in src, forbidden


def test_include_subroot_selects_eml_under_subroot(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, include_subroot="20_Construction"), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["include_subroots_requested"] == 1 and out["include_subroots_listable"] == 1
    assert out["include_subroots_failed"] == 0
    assert out["project_number"] == "23-435-01"  # identity still from source-root
    assert out["eml_selected"] >= 1              # .eml live under 20_Construction
    assert out["archive_notes_created"] == 0 and out["ollama_calls"] == 0  # dry-run writes nothing


def test_include_subroot_escape_refused(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    assert _run(_args(env, include_subroot="../../escape"), capsys)[0] == 3


def test_include_file_eml_selected(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, include_file="20_Construction/Elevator Shaft.eml"), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["include_files_requested_raw"] == 1 and out["include_files_validated"] == 1
    assert out["include_files_selected"] == 1 and out["eml_selected"] == 1
    assert out["archive_notes_created"] == 0 and out["ollama_calls"] == 0  # dry-run writes nothing


def test_include_file_pdf_is_unsupported_for_eml_negative_control(tmp_path, monkeypatch, capsys):
    # Negative control: a non-.eml include-file is reported unsupported_for_eml and selects 0 emails.
    env = _env(tmp_path, monkeypatch)
    (env["troot"] / "20_Construction" / "proposal.pdf").write_text("pdf", encoding="utf-8")
    rc, out = _run(_args(env, include_file="20_Construction/proposal.pdf"), capsys)
    assert rc == 0 and out["mode"] == "dry-run"
    assert out["include_files_validated"] == 1 and out["include_files_selected"] == 0
    assert out["include_files_unsupported_for_eml"] == 1 and out["eml_selected"] == 0
    assert out["archive_notes_created"] == 0
    assert not list(env["vault"].rglob("*.md"))  # nothing written


def test_include_file_escape_refused(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    assert _run(_args(env, include_file="../../escape.eml"), capsys)[0] == 3
    assert _run(_args(env, include_file="/etc/passwd"), capsys)[0] == 3
