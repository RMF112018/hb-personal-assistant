"""Controlled in-place re-render of existing generated source cards (Phase 9). Synthetic temp only.

Covers selection/staging, the full refusal matrix, the no-DB-mutation / no-queue-change guarantees,
and the staged-card quality contract (11 sections, phase8-v1, no old sections / raw preview, doc-type
PM guidance, strengthened Source Basis, no invented relationships, safe-summary redaction).
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_card_rerender_existing.py"
_spec = importlib.util.spec_from_file_location("obsidian_source_card_rerender_existing", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_SEED = [
    ("25-244/RFI 032 - Door Hardware.md", "Request for Information RFI #032 regarding door hardware."),
    ("25-244/Executed Change Order 004.md", "Executed change order PCCO 004 for added millwork."),
    ("25-244/Project Notes.md", "# Notes\n\nGeneral project notes for the team."),
]


@pytest.fixture(autouse=True)
def _no_real_backend(monkeypatch):
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)


def _env(tmp_path: Path, monkeypatch):
    # Redirect app-support (backups + mutation receipts) under tmp so tests stay hermetic.
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cyml = tmp_path / "c.yml"
    cyml.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
        f"  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cyml))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "syn-work-root"
    (root / "25-244").mkdir(parents=True)
    cfg = {"enabled": True, "vault_root": str(vault), "writes_enabled": True,
           "vault_markdown_write_enabled": True, "source_card_generation_enabled": True,
           "external_sources": [{"source_root_key": "syn-work", "path": str(root), "enabled": True}]}
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps(cfg))
    config = ObsidianMcpConfig.model_validate(cfg)
    repo = SourceIndexRepository(db)
    sids = []
    for rel, body in _SEED:
        f = root / rel
        f.write_text(body, encoding="utf-8")
        sid = index_source_file(f, config.external_sources[0], repo, config)
        generate_source_card(repo, config, source_id=sid)
        sids.append(sid)
    return {"db": db, "cfgp": str(cfgp), "vault": vault, "root": root, "repo": repo, "sids": sids,
            "config": config, "tmp": tmp_path}


def _args(env, *, expected=3, apply=False, confirm=False, **extra):
    a = ["--db-path", env["db"], "--vault-path", str(env["vault"]), "--config-path", env["cfgp"],
         "--domain", "work", "--expected-count", str(expected),
         "--backup-dir", str(env["tmp"] / "backup"), "--staging-dir", str(env["tmp"] / "staging"),
         "--evidence-dir", str(env["tmp"] / "ev"), "--json-output"]
    if apply:
        a.append("--apply")
    if confirm:
        a.append("--confirm-overwrite-existing-cards")
    for k, v in extra.items():
        flag = "--" + k.replace("_", "-")
        a.append(flag) if v is True else a.extend([flag, str(v)])
    return a


def _run(argv, capsys):
    rc = mod.main(argv)
    out = capsys.readouterr()
    return rc, (json.loads(out.out) if rc == 0 and out.out.strip() else None)


def _staged_files(env):
    return sorted((env["tmp"] / "staging" / "Source Notes" / "Work").glob("*.md"))


def _work_cards(env):
    return sorted((env["vault"] / "Source Notes" / "Work").glob("*.md"))


# --------------------------------------------------------------------------------- selection / dry-run

def test_dry_run_selects_existing_work_rows_and_stages_only(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    before = {p.name: p.read_text() for p in _work_cards(env)}
    rc, out = _run(_args(env), capsys)
    assert rc == 0
    assert out["mode"] == "dry-run"
    assert out["selected_existing_cards"] == 3 and out["staged_cards_rendered"] == 3
    assert out["overwritten_cards"] == 0 and out["created_cards"] == 0 and out["queue_delta"] == 0
    assert len(_staged_files(env)) == 3
    assert not list((tmp_path / "backup").glob("**/*.md"))  # no backups in dry-run
    after = {p.name: p.read_text() for p in _work_cards(env)}
    assert before == after  # production cards untouched


def test_dry_run_reports_db_only_and_no_cloud(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env), capsys)
    assert rc == 0
    assert out["renderer_input_source"] == "stored_db_metadata"
    assert out["external_source_files_read"] == 0
    assert out["cloud_download_triggered"] is False
    assert out["source_readability_observed_only"] is True
    assert out["generated_at_preserved"] is True
    assert out["db_mutations"] == {"generated_note_rows_created": 0, "generated_note_rows_refreshed": 0,
                                   "source_rows_written": 0, "summaries_deleted": 0,
                                   "relationships_written": 0, "events_enqueued": 0}


# ----------------------------------------------------------------------------------------- refusals

def test_apply_refuses_without_confirm(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, apply=True, confirm=False), capsys)
    assert rc == 3 and out is None


def test_apply_refuses_on_count_mismatch(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, _ = _run(_args(env, expected=99, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_on_missing_target_card(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _work_cards(env)[0].unlink()  # delete one production card file
    rc, _ = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_on_path_outside_work(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    # ".." is checked before the filename-suffix check, so a plain name still exercises this refusal.
    env["repo"].record_generated_note(env["sids"][0], "Source Notes/Work/../evil.md",
                                      "generated", "2026-06-30T00:00:00+00:00")
    rc, _ = _run(_args(env, expected=4, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_on_bad_filename_suffix(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    env["repo"].record_generated_note(env["sids"][0], "Source Notes/Work/plainname.md",
                                      "generated", "2026-06-30T00:00:00+00:00")
    rc, _ = _run(_args(env, expected=4, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_on_non_generated_row(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    # status is checked before the suffix check, so a plain name still exercises this refusal.
    env["repo"].record_generated_note(env["sids"][0], "Source Notes/Work/stale.md",
                                      "stale", "2026-06-30T00:00:00+00:00")
    rc, _ = _run(_args(env, expected=4, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_on_missing_source_record(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    target = env["sids"][0]
    orig = mod.SourceIndexRepository.get_source_detail
    monkeypatch.setattr(mod.SourceIndexRepository, "get_source_detail",
                        lambda self, sid, **k: None if sid == target else orig(self, sid, **k))
    rc, _ = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 3


def test_require_readable_sources_gate_both_modes(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_readability_status", lambda p: "online_only_or_dataless")
    # strict gate ON → refuse
    rc, _ = _run(_args(env, apply=True, confirm=True, require_readable_sources=True), capsys)
    assert rc == 3
    # default (gate OFF) → proceeds despite online-only sources (render is DB-only)
    rc2, out2 = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc2 == 0 and out2["overwritten_cards"] == 3
    assert out2["source_readability_counts"]["online_only_or_dataless"] == 3


def test_apply_refuses_on_staging_validation_failure(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_render_card", lambda *a, **k: "---\nbad card\n---\n# x\n")
    rc, _ = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_if_would_create(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    real = mod.create_note

    def _creating(*a, **k):
        out = real(*a, **k)
        out["created"] = True  # simulate a create where an overwrite was expected
        return out

    monkeypatch.setattr(mod, "create_note", _creating)
    rc, _ = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 3


def test_apply_refuses_if_would_delete(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    real = mod.create_note

    def _deleting(config, *, path, content, **k):
        out = real(config, path=path, content=content, **k)
        (env["vault"] / path).unlink()  # simulate a delete
        return out

    monkeypatch.setattr(mod, "create_note", _deleting)
    rc, _ = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 3


# -------------------------------------------------------------------------------------------- apply

def test_apply_backs_up_and_overwrites_exact_targets(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    names_before = {p.name for p in _work_cards(env)}
    rc, out = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 0
    assert out["backed_up_cards"] == 3 and out["overwritten_cards"] == 3
    assert out["created_cards"] == 0 and out["deleted_cards"] == 0
    assert out["create_note_receipts"] == 3
    # backups exist for exactly the 3 cards
    assert len(list((tmp_path / "backup" / "Source Notes" / "Work").glob("*.md"))) == 3
    # no new/removed production cards
    assert {p.name for p in _work_cards(env)} == names_before


def test_apply_preserves_generated_at_updates_updated_at(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    card = _work_cards(env)[0]
    original_gen = mod._frontmatter_value(card.read_text(), "generated_at")
    rc = mod.main(_args(env, apply=True, confirm=True), now_iso_fn=lambda: "2099-12-31T00:00:00+00:00")
    assert rc == 0
    text = card.read_text()
    assert mod._frontmatter_value(text, "generated_at") == original_gen  # preserved
    assert mod._frontmatter_value(text, "updated_at") == "2099-12-31T00:00:00+00:00"  # re-render


def test_apply_makes_no_queue_changes(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)

    def _count():
        c = sqlite3.connect(env["db"])
        try:
            return c.execute("SELECT COUNT(*) FROM source_intelligence_events").fetchone()[0]
        finally:
            c.close()

    before = _count()
    rc, out = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 0 and out["queue_delta"] == 0
    assert _count() == before


def test_apply_makes_no_db_mutations(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)

    def _counts():
        c = sqlite3.connect(env["db"])
        try:
            gen = c.execute("SELECT COUNT(*) FROM source_intelligence_generated_notes").fetchone()[0]
            src = c.execute("SELECT COUNT(*) FROM source_intelligence_sources").fetchone()[0]
            summ = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0]
            return gen, src, summ
        finally:
            c.close()

    before = _counts()
    rc, _ = _run(_args(env, apply=True, confirm=True), capsys)
    assert rc == 0
    assert _counts() == before  # no rows created/deleted anywhere


# --------------------------------------------------------------------------- staged-card quality

def test_staged_cards_have_canonical_sections_in_order(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    for f in _staged_files(env):
        headings = [ln for ln in f.read_text().splitlines() if ln.startswith("## ")]
        assert headings == mod.CANONICAL_SECTIONS


def test_staged_cards_have_phase8_card_version(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    for f in _staged_files(env):
        assert mod._frontmatter_value(f.read_text(), "card_version") == "phase8-v1"
        assert mod._frontmatter_value(f.read_text(), "domain") == "work"


def test_staged_cards_have_no_old_sections_or_preview(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    for f in _staged_files(env):
        text = f.read_text()
        for old in mod.FORBIDDEN_OLD_SECTIONS:
            assert old not in text
        assert "Indexed Text Preview" not in text


def test_staged_cards_have_doc_type_guidance(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    follow = {}
    for f in _staged_files(env):
        text = f.read_text()
        body = "\n".join(mod._section_body(text, "## Follow-Up"))
        assert body.strip()  # never empty boilerplate
        follow[f.name] = body
    assert len(set(follow.values())) >= 2  # different doc types → different guidance


def test_staged_cards_have_strengthened_source_basis(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    for f in _staged_files(env):
        basis = "\n".join(mod._section_body(f.read_text(), "## Source Basis"))
        for needle in ("Card basis:", "Document type:", "Classification reason:", "Source ID:"):
            assert needle in basis, needle


def test_staged_cards_do_not_invent_relationships(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    for f in _staged_files(env):
        text = f.read_text()
        assert "No related decisions linked yet." in text
        assert "No related meetings linked yet." in text
        assert "[[" not in text


def test_safe_summary_is_redacted(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env), capsys)
    safe = (tmp_path / "ev" / "rerender-work-dry-run-summary-safe.json").read_text()
    for needle in ("25-244", "RFI 032", "Door Hardware", "Project Notes", str(env["vault"]),
                   "__", str(env["root"])):
        assert needle not in safe, needle
    # the local-sensitive detail file DOES carry note paths (kept local, not committed)
    detail = (tmp_path / "ev" / "rerender-work-dry-run-detail-local-sensitive.json").read_text()
    assert "Source Notes/Work/" in detail
