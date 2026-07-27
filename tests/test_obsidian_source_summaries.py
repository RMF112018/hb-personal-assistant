"""Ollama-assisted summarize_source: advisory enrichment, receipt, fallback, lifecycle."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import hb_assistant.obsidian_mcp.llm as llm
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file, scan_source_root
from hb_assistant.obsidian_mcp.source_notes import generate_source_card, summarize_source
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError
from hb_assistant.store.migrator import SQLiteMigrator

_FAKE_SUMMARY = {
    "summary": "Conduit RFI; 8-week lead time; decision pending.",
    "key_points": ["8-week lead time", "electrical scope"],
    "action_items": ["Confirm conduit order"],
    "decisions": [], "entities": ["conduit"], "suggested_tags": [], "suggested_links": [],
}


class _FakeBackend:
    def generate_json(self, *, system: str, prompt: str) -> str:
        return json.dumps(_FAKE_SUMMARY)


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root_dir = tmp_path / "proj"
    (root_dir / "22-101-00").mkdir(parents=True, exist_ok=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True, "source_summary_max_input_chars": 4000,
        "external_sources": [{"source_root_key": "proj", "path": str(root_dir), "enabled": True}],
    })
    return SourceIndexRepository(db), config, root_dir, vault, db


def _index(env, name: str, body: str) -> str:
    repo, config, root_dir, _vault, _db = env
    f = root_dir / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return index_source_file(f, config.external_sources[0], repo, config)


def _force_backend(monkeypatch, backend) -> None:
    monkeypatch.setattr(llm, "_resolve_backend", lambda config: backend)


def test_summarize_enriches_card_with_advisory(env, monkeypatch) -> None:
    repo, config, _root, vault, db = env
    _force_backend(monkeypatch, _FakeBackend())
    sid = _index(env, "22-101-00/RFI conduit.md", "Underground conduit. 8-week lead time. Decision pending.")
    out = summarize_source(repo, config, source_id=sid)
    assert out["summarized"] is True and out["mode"] == "llm"
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "## Advisory Summary" in card and "model-generated, not authoritative" in card
    assert "summary_advisory: true" in card
    assert "summary_model_provider:" in card and "summary_prompt_version:" in card
    assert "Verify against the source." in card
    receipt = repo.get_summary(sid)
    assert receipt is not None and receipt["model_provider"] == "ollama"
    # no raw prompt/response persisted in the receipt table
    blob = str(sqlite3.connect(db).execute("SELECT * FROM source_intelligence_summaries").fetchall())
    assert "Underground conduit" not in blob and "8-week lead time" not in blob


def test_ollama_unavailable_keeps_base_no_advisory(env, monkeypatch) -> None:
    repo, config, _root, vault, _db = env
    _force_backend(monkeypatch, None)  # model unavailable
    sid = _index(env, "a.md", "Some indexed content here.")
    out = summarize_source(repo, config, source_id=sid)
    # A None backend means the daemon/model couldn't be reached → specific category code.
    assert out["summarized"] is False and out["reason"] == "ollama_unavailable"
    # base deterministic card WAS created (one-call contract), but with no advisory
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "summary_advisory: false" in card
    assert "## AI Summary" not in card
    assert repo.get_summary(sid) is None


def test_deterministic_generate_strips_advisory_and_receipt(env, monkeypatch) -> None:
    repo, config, _root, vault, _db = env
    _force_backend(monkeypatch, _FakeBackend())
    sid = _index(env, "a.md", "conduit content")
    out = summarize_source(repo, config, source_id=sid)
    assert repo.get_summary(sid) is not None
    generate_source_card(repo, config, source_id=sid, overwrite=True)  # deterministic
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "## AI Summary" not in card and "summary_advisory: false" in card
    assert repo.get_summary(sid) is None  # receipt cleared


def test_source_change_marks_summary_stale(env, monkeypatch) -> None:
    repo, config, root_dir, _vault, _db = env
    _force_backend(monkeypatch, _FakeBackend())
    sid = _index(env, "a.md", "alpha conduit original")
    summarize_source(repo, config, source_id=sid)
    assert repo.index_status()["stale_summary_count"] == 0
    (root_dir / "a.md").write_text("beta tunnel changed", encoding="utf-8")
    scan_source_root(config.external_sources[0], repo, config)  # reindex -> source sha drifts
    st = repo.index_status()
    assert st["summarized_count"] == 1 and st["stale_summary_count"] == 1


def test_link_source_no_summarizable_text(env, monkeypatch) -> None:
    repo, config, _root, vault, _db = env
    _force_backend(monkeypatch, _FakeBackend())
    sid = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                  domain_ref_id="msg-1")
    out = summarize_source(repo, config, source_id=sid)
    assert out["summarized"] is False and out["reason"] == "no_summarizable_text"
    # base card created, no advisory, no receipt, no email body
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "## AI Summary" not in card
    assert repo.get_summary(sid) is None


def test_sensitive_source_not_summarized(env, monkeypatch) -> None:
    repo, config, root_dir, _vault, _db = env
    monkeypatch.setenv("HB_TEXT_VAULT_KEY", "dGVzdC1rZXktZm9yLXRleHQtdmF1bHQtMzJieXRlcyE=")
    _force_backend(monkeypatch, _FakeBackend())
    sroot = ExternalSourceRoot(source_root_key="proj", path=str(root_dir), sensitive=True)
    f = root_dir / "secret.md"
    f.write_text("confidential salary figures", encoding="utf-8")
    sid = index_source_file(f, sroot, repo, config)
    out = summarize_source(repo, config, source_id=sid)
    assert out["summarized"] is False and out["reason"] == "no_summarizable_text"
    assert repo.get_summary(sid) is None


def test_advisory_lists_bounded(env, monkeypatch) -> None:
    repo, config, _root, vault, _db = env
    big = {**_FAKE_SUMMARY, "key_points": [f"point {i}" for i in range(50)]}

    class _Big:
        def generate_json(self, *, system, prompt):
            return json.dumps(big)

    _force_backend(monkeypatch, _Big())
    sid = _index(env, "a.md", "content")
    out = summarize_source(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert card.count("- point ") <= 10  # capped


def test_summarize_source_not_found(env, monkeypatch) -> None:
    repo, config, _root, _vault, _db = env
    _force_backend(monkeypatch, _FakeBackend())
    with pytest.raises(ObsidianMcpToolError) as exc:
        summarize_source(repo, config, source_id="missing")
    assert exc.value.code == "source_not_found"


# ---------------- R11-D2 domain-locator collision coverage (summary/link layer) ----------------

def test_r11_d2_domain_links_distinct_across_table_and_kind(env) -> None:
    repo, _config, _root, _vault, _db = env
    # same (kind, id) across different domain_ref_table → distinct entities + distinct current locators
    a = repo.link_domain_source(source_kind="procore", domain_ref_table="rfis", domain_ref_id="7")
    b = repo.link_domain_source(source_kind="procore", domain_ref_table="submittals", domain_ref_id="7")
    assert a != b
    con = sqlite3.connect(repo.db_path)
    roots = {
        r[0] for r in con.execute(
            "SELECT source_root_key FROM source_index_locators "
            "WHERE source_entity_id IN (?,?) AND is_current_locator=1", (a, b)).fetchall()
    }
    assert roots == {"domain::procore::rfis", "domain::procore::submittals"}
    # idempotent re-link of the SAME identity resolves to the SAME entity
    assert repo.link_domain_source(source_kind="procore", domain_ref_table="rfis",
                                   domain_ref_id="7") == a


def test_r11_d2_cross_kind_same_table_id_fails_closed(env) -> None:
    # repo-truth conflict: frozen UNIQUE(domain_ref_table, domain_ref_id) refuses a distinct second
    # entity for the same (table,id) under a different kind (fail-closed, no silent rebind).
    repo, _config, _root, _vault, _db = env
    repo.link_domain_source(source_kind="procore", domain_ref_table="records", domain_ref_id="c9")
    with pytest.raises(sqlite3.IntegrityError):
        repo.link_domain_source(source_kind="email", domain_ref_table="records", domain_ref_id="c9")
