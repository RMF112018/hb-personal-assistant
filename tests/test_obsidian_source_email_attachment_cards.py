"""Phase 10F — bounded attachment extraction script: gates, apply, reciprocal links, idempotency.

Synthetic temp env only; no real corpus/email/Ollama. Seeds a Phase 10E parent email card, then runs the
Phase 10F extraction script over the same selection.
"""

from __future__ import annotations

import json
import sys
from email.message import EmailMessage
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_email_attachments as att_mod
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.mdutil import split_frontmatter as md_split
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import _VAULT_ROOT_KEY, scan_vault_notes
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import obsidian_source_extract_email_attachments as mod  # noqa: E402
import obsidian_source_index_eml_archive as eml10e  # noqa: E402  (same module mod imports)

_ROWS = [{"project_key": "tropical", "project_number": "23-435-01",
          "display_name": "23-435-01 - Tropical World Nursery Senior Living Facility",
          "procore_project_id": "2525840"}]


@pytest.fixture(autouse=True)
def _patches(monkeypatch):
    monkeypatch.setattr(eml10e, "_backend_listening", lambda *a, **k: False)
    monkeypatch.setattr(eml10e, "_readability", lambda p: "readable")
    import hb_assistant.construction.analytics.project_summary_readmodel as rm

    class _Fake:
        def build(self):
            return {"projects": _ROWS}
    monkeypatch.setattr(rm, "ProjectSummaryReadModelService", lambda *, db_path=None: _Fake())


def _eml_with_attachments() -> bytes:
    m = EmailMessage()
    m["Subject"] = "RE: TWN Fire Alarm Design"
    m["From"] = "Jane Roe <jane@powerdesign.example>"
    m["To"] = "John Doe <john@hbconstruction.example>"
    m["Date"] = "Thu, 14 Aug 2025 10:30:00 -0400"
    m.set_content("Transmittal — see attached permit and tool.")
    m.add_attachment(b"%PDF-1.4 permit comments text", maintype="application", subtype="pdf",
                     filename="permit.pdf")
    m.add_attachment(b"MZ executable payload", maintype="application", subtype="octet-stream",
                     filename="tool.exe")
    m.add_attachment(b"\x89PNG inline logo", maintype="image", subtype="png", filename="logo.png",
                     cid="<logo@cid>")
    return m.as_bytes()


def _env(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    y = tmp_path / "c.yml"
    y.write_text(f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
                 f"  obsidian_vault: {vault.as_posix()!r}\n")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    base = tmp_path / "synbase"
    troot = base / "NAS - HB" / "Projects" / "2023" / "23-435-01 - Tropical" / "00_Project_Admin"
    troot.mkdir(parents=True)
    (troot / "RE Fire Alarm.eml").write_bytes(_eml_with_attachments())
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


def _args(env, *, apply=False, update=False, confirm=True, source_root=None, backup="bk",
          summary=False, **over):
    sr = source_root or str(env["troot"])
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--source-root", sr, "--root-key", "syn-work", "--max-eml", "10", "--max-attachments", "50",
         "--json-output", "--confirm-project-number", "23-435-01", "--confirm-project-key", "tropical"]
    if summary:
        a.append("--summarize")  # deterministic-only by default; opt in per-test for the qwen path
    if backup:
        a += ["--backup-dir", str(env["tmp"] / backup)]
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


def _seed_parent_card(env, capsys):
    """Run the Phase 10E indexer so the parent email card exists (10F links back to it)."""
    argv = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
            "--source-root", str(env["troot"]), "--root-key", "syn-work", "--max-eml", "10", "--apply",
            "--confirm-source-root", str(env["troot"]), "--confirm-project-number", "23-435-01",
            "--confirm-project-key", "tropical", "--confirm-vault-path", str(env["vault"]),
            "--confirm-db-path", env["db"], "--backup-dir", str(env["tmp"] / "seed-bk"), "--json-output"]
    rc = eml10e.main(argv)
    capsys.readouterr()
    assert rc == 0


def _run(argv, capsys):
    rc = mod.main(argv)
    out = capsys.readouterr().out
    return rc, (json.loads(out) if rc == 0 and out.strip() else None)


def _cards(env):
    return list((env["vault"] / "Source Notes" / "Work").glob("*.md"))


def test_dry_run_writes_nothing(tmp_path, capsys):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    cards_before = sorted(p.name for p in _cards(env))
    rc, out = _run(_args(env, apply=False), capsys)
    assert rc == 0
    assert out["attachments_discovered"] == 2 and out["inline_parts"] == 1
    assert out["attachments_extractable"] == 1 and out["skipped_unsafe"] == 1
    assert out["attachment_binaries_written"] == 0  # dry-run writes nothing
    assert not (env["vault"] / "Email Archive" / "Work" / "Attachments").exists()
    assert sorted(p.name for p in _cards(env)) == cards_before  # no new cards


def test_apply_extracts_cards_and_reciprocal_links(tmp_path, capsys):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    rc, out = _run(_args(env, apply=True), capsys)
    assert rc == 0
    assert out["attachment_binaries_written"] == 1 and out["skipped_unsafe"] == 1
    assert out["metadata_only_attachments"] == 0  # pdf is a supported type -> 'extracted'
    assert out["attachment_cards_generated"] == 1 and out["attachment_cards_updated"] == 0
    assert out["parent_email_cards_updated"] == 1 and out["reciprocal_links_added"] == 1
    assert out["generated_note_delta"] == 1 and out["vault_markdown_delta"] == 1
    assert out["queue_delta"] == 0 and out["ollama_calls"] == 0  # --no-summary here
    # binary is TRANSIENT: written to card the attachment, then always deleted (none persists)
    assert out["attachment_binaries_deleted"] == 1
    att_root = env["vault"] / "Email Archive" / "Work" / "Attachments"
    assert list(att_root.rglob("*.pdf")) == []  # no attachment binary left in the vault
    assert list(att_root.rglob("*")) == []  # empty per-email dirs pruned too
    # attachment card exists under Source Notes/Work with exactly one attachment block linking to parent
    att_cards = [p for p in _cards(env) if "permit" in p.name]
    assert len(att_cards) == 1
    txt = att_cards[0].read_text(encoding="utf-8")
    assert txt.count(att_mod.ATTACH_BEGIN_PREFIX) == 1
    assert "Parent email card:" in txt and "Parent email archive:" in txt
    # deterministic-only default: no Ollama, hb-local-summary left pending
    assert out["ollama_calls"] == 0 and out["qwen_summaries_written"] == 0
    assert 'hb-local-summary:start model="qwen2.5:14b" status="pending"' in txt
    # inherited identity is self-consistent: frontmatter + visible bullet + managed block all agree
    assert txt.count("hb-project-identity:start") == 1  # exactly one managed block
    fm, _body = md_split(txt)
    assert fm.get("project_number") == "23-435-01" and fm.get("project_key") == "tropical"
    assert "project/23-435-01" in [str(t) for t in (fm.get("tags") or [])]
    assert "No project number detected" not in txt  # no contradiction with the block
    assert "- Project (inherited from parent email): 23-435-01 · tropical" in txt
    # parent email card links to the attachment card (reciprocal), exactly one block
    parent = [p for p in _cards(env) if "Fire Alarm" in p.name and "permit" not in p.name][0]
    ptxt = parent.read_text(encoding="utf-8")
    assert ptxt.count(att_mod.ATTACHMENTS_BEGIN) == 1
    assert att_cards[0].stem in ptxt  # wiki link to the attachment card


def test_attachment_not_in_obsidian_note_fts(tmp_path, capsys):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    _run(_args(env, apply=True), capsys)
    scan_vault_notes(env["repo"], env["config"])
    indexed = env["repo"].active_rel_paths(_VAULT_ROOT_KEY)
    assert not any(r.replace("\\", "/").startswith("Email Archive/") for r in indexed)


def test_rerun_without_update_skips_no_duplicates(tmp_path, capsys):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    _run(_args(env, apply=True), capsys)
    cards_before = sorted(p.name for p in _cards(env))
    rc, out = _run(_args(env, apply=True), capsys)  # no --update
    assert rc == 0 and out["already_indexed"] == 1
    assert out["attachment_cards_generated"] == 0 and out["reciprocal_links_added"] == 0
    assert sorted(p.name for p in _cards(env)) == cards_before  # no duplicate cards


def test_rerun_with_update_no_duplicate_links(tmp_path, capsys):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    _run(_args(env, apply=True), capsys)
    rc, out = _run(_args(env, apply=True, update=True), capsys)
    assert rc == 0 and out["attachment_cards_updated"] == 1
    att_card = [p for p in _cards(env) if "permit" in p.name][0]
    parent = [p for p in _cards(env) if "Fire Alarm" in p.name and "permit" not in p.name][0]
    assert att_card.read_text(encoding="utf-8").count(att_mod.ATTACH_BEGIN_PREFIX) == 1
    assert parent.read_text(encoding="utf-8").count(att_mod.ATTACHMENTS_BEGIN) == 1


def test_reciprocal_or_neither_rollback(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    # force the parent-block write to fail -> the whole email pair must roll back (no one-way links)
    monkeypatch.setattr(att_mod, "upsert_email_attachments_block", lambda *a, **k: (None, "boom"))
    rc, out = _run(_args(env, apply=True), capsys)
    assert rc == 0
    assert out["reciprocal_links_added"] == 0 and out["parent_email_cards_updated"] == 0
    att_card = [p for p in _cards(env) if "permit" in p.name][0]
    parent = [p for p in _cards(env) if "Fire Alarm" in p.name and "permit" not in p.name][0]
    # attachment card exists (base) but carries NO one-way link block; parent has none either
    assert att_card.read_text(encoding="utf-8").count(att_mod.ATTACH_BEGIN_PREFIX) == 0
    assert parent.read_text(encoding="utf-8").count(att_mod.ATTACHMENTS_BEGIN) == 0


def test_default_is_deterministic_no_ollama_client(tmp_path, capsys, monkeypatch):
    # Hard stop: the DEFAULT apply (no --summarize) must never build an Ollama client / call the model.
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)

    def _forbidden(model, timeout):
        raise AssertionError("default apply must not build an Ollama client")

    monkeypatch.setattr(mod, "_default_client_factory", _forbidden)
    rc, out = _run(_args(env, apply=True), capsys)  # no summary=True
    assert rc == 0
    assert out["summarize_requested"] is False and out["summary_model"] is None
    assert out["ollama_calls"] == 0 and out["qwen_summaries_written"] == 0
    assert out["summary_failed"] == 0
    att_card = [p for p in _cards(env) if "permit" in p.name][0]
    assert 'hb-local-summary:start model="qwen2.5:14b" status="pending"' \
        in att_card.read_text(encoding="utf-8")


class _FakeClient:
    """Deterministic local-model stand-in — returns a valid canonical 4-section advisory."""

    def generate_text(self, *, system: str, prompt: str) -> str:
        return ("_Advisory — locally generated by qwen2.5:14b. Verify against the source._\n\n"
                "### Summary\nAdvisory test summary for the permit attachment.\n\n"
                "### PM Attention\n- none\n\n### Follow-Up Questions\n- none\n\n"
                "### Limits / Uncertainty\n- advisory only\n")


class _BadClient:
    """Returns the observed bad shape: invented filename + size, noncanonical headers."""

    def generate_text(self, *, system: str, prompt: str) -> str:
        return ("**File**: INVENTED-PART-NAME\n\n**Size**: 38 KB\n\n"
                "**Description**: an order tracking report.\n")


def test_summarize_optin_writes_valid_summary(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    monkeypatch.setattr(mod, "_default_client_factory", lambda model, timeout: _FakeClient())
    rc, out = _run(_args(env, apply=True, summary=True), capsys)
    assert rc == 0
    assert out["summarize_requested"] is True and out["summary_model"] == mod.SUMMARY_MODEL == "qwen2.5:14b"
    assert out["ollama_calls"] == 1 and out["qwen_summaries_written"] == 1 and out["summary_failed"] == 0
    # binary deleted regardless of (here successful) qwen summary
    assert out["attachment_binaries_written"] == 1 and out["attachment_binaries_deleted"] == 1
    assert list((env["vault"] / "Email Archive" / "Work" / "Attachments").rglob("*")) == []
    ctext = [p for p in _cards(env) if "permit" in p.name][0].read_text(encoding="utf-8")
    assert 'hb-local-summary:start model="qwen2.5:14b" status="generated"' in ctext
    assert "Advisory test summary for the permit attachment." in ctext
    assert f"Model: {mod.SUMMARY_MODEL}" in ctext


def test_summarize_optin_rejects_bad_summary_leaves_pending(tmp_path, capsys, monkeypatch):
    # A summary that invents a filename/size + uses a noncanonical shape must be REJECTED (quality gate);
    # the block stays deterministic/pending and summary_failed is counted.
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    monkeypatch.setattr(mod, "_default_client_factory", lambda model, timeout: _BadClient())
    rc, out = _run(_args(env, apply=True, summary=True), capsys)
    assert rc == 0
    assert out["ollama_calls"] == 1 and out["qwen_summaries_written"] == 0 and out["summary_failed"] == 1
    ctext = [p for p in _cards(env) if "permit" in p.name][0].read_text(encoding="utf-8")
    assert 'hb-local-summary:start model="qwen2.5:14b" status="pending"' in ctext
    assert "INVENTED-PART-NAME" not in ctext and "38 KB" not in ctext  # bad content never written
    assert out["attachment_binaries_deleted"] == 1  # binary still deleted


def test_apply_deletes_binary_even_when_ollama_down(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)

    def _boom(model, timeout):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(mod, "_default_client_factory", _boom)
    rc, out = _run(_args(env, apply=True, summary=True), capsys)
    assert rc == 0
    assert out["summary_model"] is None  # client build failed -> no summaries attempted
    assert out["qwen_summaries_written"] == 0 and out["ollama_calls"] == 0
    assert out["attachment_cards_generated"] == 1  # card still generated deterministically
    assert out["attachment_binaries_deleted"] == 1  # binary still always deleted
    att_root = env["vault"] / "Email Archive" / "Work" / "Attachments"
    assert list(att_root.rglob("*")) == []


def test_refusals(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path)
    _seed_parent_card(env, capsys)
    # confirm mismatch
    bad = _args(env, apply=True)
    bad[bad.index("--confirm-project-key") + 1] = "wrong"
    assert mod.main(bad) == 3
    capsys.readouterr()
    # backend listening
    monkeypatch.setattr(eml10e, "_backend_listening", lambda *a, **k: True)
    assert mod.main(_args(env, apply=True)) == 3
    capsys.readouterr()
    monkeypatch.setattr(eml10e, "_backend_listening", lambda *a, **k: False)
    # no backup dir
    assert mod.main(_args(env, apply=True, backup=None)) == 3
    capsys.readouterr()
    # queue not empty
    env["repo"].enqueue_event(event_type="created", rel_path="x.pdf", source_root_key="syn-work")
    assert mod.main(_args(env, apply=True)) == 3
