"""Bounded first-indexing apply: gates, deterministic selection, direct generation, no queue drain.

Temp DB / source root / vault only. Never touches production data.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_first_indexing_apply.py"
_spec = importlib.util.spec_from_file_location("obsidian_source_first_indexing_apply", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


@pytest.fixture(autouse=True)
def _no_real_backend(monkeypatch):
    # Hermetic: never depend on the real port 8000 being free.
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)


def _env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    root = tmp_path / "syn-work-root"
    (root / "25-244").mkdir(parents=True, exist_ok=True)
    files = {
        "RFI 032 Door.md": "Request for Information RFI #032 door hardware.",
        "PCCO 004 Millwork.md": "PCCO 004 lobby millwork change order.",
        "Submittal 05 51 00 Stairs.md": "Submittal 05 51 00 metal stairs.",
        "notes.md": "misc notes",            # general_document -> auto_card_normal
        "Tracker.xlsx": "a,b",               # spreadsheet -> metadata_only
        "photo.png": "img",                  # unsupported
    }
    for n, c in files.items():
        (root / "25-244" / n).write_text(c, encoding="utf-8")
    cfg = {"enabled": True, "vault_root": str(vault), "writes_enabled": True,
           "vault_markdown_write_enabled": True,
           "external_sources": [{"source_root_key": "syn-work", "path": str(root), "enabled": True}]}
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps(cfg), encoding="utf-8")
    return db, str(cfgp), str(vault), root


def _args(db, cfg, vault, root_key="syn-work", *, apply=False, confirms=True, **extra):
    a = ["--db-path", db, "--config-path", cfg, "--vault-path", vault, "--root-key", root_key]
    if apply:
        a.append("--apply")
        if confirms:
            a += ["--confirm-root-key", root_key, "--confirm-db-path", db, "--confirm-vault-path", vault]
    for k, v in extra.items():
        flag = "--" + k.replace("_", "-")
        if v is True:
            a.append(flag)
        else:
            a += [flag, str(v)]
    return a


def _gen_count(db: str) -> int:
    return sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE generation_status='generated'"
    ).fetchone()[0]


# ----- preview / gates -----------------------------------------------------------------------
def test_preview_writes_nothing(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    rc = mod.main(_args(db, cfg, vault))  # no --apply
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # 3 auto_card_high in the pool; preview reports readability (all materialized temp files readable).
    assert out["mode"] == "preview" and out["pool_size"] == 3
    assert out["readable_considered"] == 3
    assert _gen_count(db) == 0
    assert not (Path(vault) / "Source Notes").exists()  # nothing written


def test_apply_refuses_without_confirmations(tmp_path):
    db, cfg, vault, _root = _env(tmp_path)
    assert mod.main(_args(db, cfg, vault, apply=True, confirms=False)) == 3
    assert _gen_count(db) == 0


def test_apply_refuses_when_backend_listening(tmp_path, monkeypatch):
    db, cfg, vault, _root = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: True)
    assert mod.main(_args(db, cfg, vault, apply=True)) == 3


def test_apply_refuses_when_queue_nonempty(tmp_path):
    db, cfg, vault, _root = _env(tmp_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_events "
                  "(event_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
                  "VALUES ('e1','x/y.md','syn-work','modified','queued',0,'t','t')")
        c.commit()
    assert mod.main(_args(db, cfg, vault, apply=True)) == 3


def test_refuses_disabled_root(tmp_path):
    db, cfg, vault, root = _env(tmp_path)
    cfg2 = json.loads(Path(cfg).read_text())
    cfg2["external_sources"][0]["enabled"] = False
    Path(cfg).write_text(json.dumps(cfg2), encoding="utf-8")
    assert mod.main(_args(db, cfg, vault, apply=True)) == 3


def test_refuses_active_vault_root(tmp_path):
    db, cfg, vault, _root = _env(tmp_path)
    cfg2 = json.loads(Path(cfg).read_text())
    cfg2["external_sources"][0]["path"] = vault  # root == active vault
    Path(cfg).write_text(json.dumps(cfg2), encoding="utf-8")
    assert mod.main(_args(db, cfg, vault, apply=True)) == 3


def test_refuses_quarantine_root(tmp_path):
    db, cfg, vault, _root = _env(tmp_path)
    quar = tmp_path / "Obsidian Vault - QUARANTINED - SYNTHETIC"
    (quar / "25-244").mkdir(parents=True)
    (quar / "25-244" / "RFI 1.md").write_text("rfi #1", encoding="utf-8")
    cfg2 = json.loads(Path(cfg).read_text())
    cfg2["external_sources"][0]["path"] = str(quar)
    Path(cfg).write_text(json.dumps(cfg2), encoding="utf-8")
    assert mod.main(_args(db, cfg, vault, apply=True)) == 3


def test_max_summaries_nonzero_refused(tmp_path):
    db, cfg, vault, _root = _env(tmp_path)
    assert mod.main(_args(db, cfg, vault, apply=True, max_summaries=2)) == 3


# ----- selection -----------------------------------------------------------------------------
def test_pool_is_only_auto_card_high_work(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    mod.main(_args(db, cfg, vault))  # preview
    out = json.loads(capsys.readouterr().out)
    # 3 high (rfi/change_order/submittal); excludes normal/metadata/unsupported. All domain work.
    assert out["pool_size"] == 3


def test_card_cap_limits_generation(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    # Pool is 3, but the card cap (min(max_cards,max_candidates)) limits generation to 2.
    mod.main(_args(db, cfg, vault, apply=True, max_cards=2, max_candidates=2))
    out = json.loads(capsys.readouterr().out)
    assert out["pool_size"] == 3 and out["generated_card_count"] == 2 and out["reached_cap"] is True


# ----- apply (direct generation) -------------------------------------------------------------
def test_apply_generates_routed_cards(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    rc = mod.main(_args(db, cfg, vault, apply=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["generated_card_count"] == 3
    assert out["summary_count"] == 0 and out["enqueued_count"] == 0
    assert out["queued_event_delta"] == 0 and "DEVIATION" not in out
    work = Path(vault) / "Source Notes" / "Work"
    cards = list(work.glob("*.md"))
    assert len(cards) == 3
    for card in cards:
        # filename scheme: <basename>__<12 hex>.md ; no source directory replication
        assert "__" in card.name and card.name.endswith(".md")
        suffix = card.stem.rsplit("__", 1)[1]
        assert len(suffix) == 12
        assert "25-244" not in card.name
        text = card.read_text(encoding="utf-8")
        for fm in ('domain: "work"', "source_disposition:", "source_confidence:",
                   "review_status:", 'template_version:', "card_version:"):
            assert fm in text, fm
        for sec in ("## Why This Matters", "## PM Review Cues", "## Source Basis", "## Follow-Up"):
            assert sec in text, sec
    # No cards in Home/Shared.
    assert not list((Path(vault) / "Source Notes" / "Home").glob("*.md"))
    assert not list((Path(vault) / "Source Notes" / "Shared").glob("*.md"))


def test_apply_honors_max_cards(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    mod.main(_args(db, cfg, vault, apply=True, max_cards=1, max_candidates=3))
    out = json.loads(capsys.readouterr().out)
    assert out["generated_card_count"] == 1


def test_apply_does_not_overwrite_user_file(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    # Pre-create one card path with user content. Find the would-be path via a preview detail.
    mod.main(_args(db, cfg, vault, apply=True, max_cards=3))
    capsys.readouterr()
    work = Path(vault) / "Source Notes" / "Work"
    victim = sorted(work.glob("*.md"))[0]
    victim.write_text("# my own note\nhand written", encoding="utf-8")
    # Re-run apply: existing card paths must be skipped, not overwritten.
    mod.main(_args(db, cfg, vault, apply=True, max_cards=3))
    out = json.loads(capsys.readouterr().out)
    assert out["skipped_count"] >= 1
    assert victim.read_text(encoding="utf-8") == "# my own note\nhand written"


def test_apply_does_not_drain_unrelated_queue(tmp_path, capsys):
    db, cfg, vault, _root = _env(tmp_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_events "
                  "(event_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
                  "VALUES ('keepme','other/z.md','syn-work','modified','queued',0,'t','t')")
        c.commit()
    # Allow apply despite the nonempty queue, to prove the unrelated event is NOT drained.
    rc = mod.main(_args(db, cfg, vault, apply=True, no_require_empty_queue=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["generated_card_count"] == 3
    status = sqlite3.connect(db).execute(
        "SELECT status FROM source_intelligence_events WHERE event_id='keepme'").fetchone()[0]
    assert status == "queued"  # unrelated event untouched


def test_safe_summary_has_no_paths(tmp_path):
    db, cfg, vault, _root = _env(tmp_path)
    ev = tmp_path / "ev"
    mod.main(_args(db, cfg, vault, apply=True, evidence_dir=str(ev)))
    safe = (ev / "first-indexing-apply-syn-work-apply-summary-safe.json").read_text()
    for token in ("RFI 032", "PCCO 004", "Submittal", "25-244", str(tmp_path)):
        assert token not in safe, token
    detail = (ev / "first-indexing-apply-syn-work-apply-detail-local-sensitive.json").read_text()
    assert "RFI 032 Door.md" in detail  # local detail does carry rel paths


def test_external_source_files_unmodified(tmp_path, capsys):
    db, cfg, vault, root = _env(tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in (root / "25-244").glob("*.md")}
    mod.main(_args(db, cfg, vault, apply=True))
    for p, content in before.items():
        assert p.read_text(encoding="utf-8") == content  # source files never modified


# ===== Phase 6B: online-only / dataless / unreadable placeholder handling =====
class _FakeStat:
    st_size = 100_000
    st_blocks = 0  # logical size > 0 but 0 allocated blocks == cloud online-only placeholder


def test_readability_status_branches(tmp_path, monkeypatch):
    p = tmp_path / "real.md"
    p.write_text("materialized", encoding="utf-8")
    assert mod._readability_status(p) == "readable"
    assert mod._readability_status(tmp_path / "missing.md") == "read_error"
    monkeypatch.setattr(type(p), "lstat", lambda self: _FakeStat())  # simulate dataless placeholder
    assert mod._readability_status(p) == "online_only_or_dataless"


def test_dataless_skipped_and_selection_continues(tmp_path, capsys, monkeypatch):
    db, cfg, vault, _root = _env(tmp_path)
    monkeypatch.setattr(mod, "_readability_status",
                        lambda p: "online_only_or_dataless" if "RFI 032" in str(p) else "readable")
    rc = mod.main(_args(db, cfg, vault, apply=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["skips_by_reason"]["online_only_or_dataless"] == 1
    assert out["generated_card_count"] == 2  # continued to the 2 readable high candidates
    # The dataless file produced no card.
    work = Path(vault) / "Source Notes" / "Work"
    assert not any("RFI 032" in c.name for c in work.glob("*.md"))


def _fake_index_raising(monkeypatch, needle: str, exc: Exception):
    real = mod.index_source_file

    def fake(abs_path, *a, **k):
        if needle in str(abs_path):
            raise exc
        return real(abs_path, *a, **k)

    monkeypatch.setattr(mod, "index_source_file", fake)


def test_read_timeout_skipped_and_continues(tmp_path, capsys, monkeypatch):
    db, cfg, vault, _root = _env(tmp_path)
    _fake_index_raising(monkeypatch, "PCCO 004", TimeoutError("cloud read timed out"))
    mod.main(_args(db, cfg, vault, apply=True))
    out = json.loads(capsys.readouterr().out)
    assert out["skips_by_reason"]["read_timeout"] == 1
    assert out["generated_card_count"] == 2  # RFI + Submittal still generated


def test_read_permission_error_skipped(tmp_path, capsys, monkeypatch):
    db, cfg, vault, _root = _env(tmp_path)
    _fake_index_raising(monkeypatch, "PCCO 004", PermissionError("denied"))
    mod.main(_args(db, cfg, vault, apply=True))
    out = json.loads(capsys.readouterr().out)
    assert out["skips_by_reason"]["read_permission_error"] == 1
    assert out["generated_card_count"] == 2


def test_read_error_skipped(tmp_path, capsys, monkeypatch):
    db, cfg, vault, _root = _env(tmp_path)
    _fake_index_raising(monkeypatch, "PCCO 004", OSError("io error"))
    mod.main(_args(db, cfg, vault, apply=True))
    out = json.loads(capsys.readouterr().out)
    assert out["skips_by_reason"]["read_error"] == 1
    assert out["generated_card_count"] == 2


def test_pool_exhausted_before_cap_reports_blocker(tmp_path, capsys, monkeypatch):
    db, cfg, vault, _root = _env(tmp_path)
    monkeypatch.setattr(mod, "_readability_status", lambda p: "online_only_or_dataless")
    rc = mod.main(_args(db, cfg, vault, apply=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["generated_card_count"] == 0
    assert out["skips_by_reason"]["online_only_or_dataless"] == 3
    assert out["pool_exhausted_before_cap"] is True and out["reached_cap"] is False
    assert out["queued_event_delta"] == 0  # no queue events even when nothing is generated
