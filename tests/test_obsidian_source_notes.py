"""Deterministic source cards: traceability, guardrails, generate -> stale -> refresh."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file, scan_source_root
from hb_assistant.obsidian_mcp.source_notes import generate_source_card, refresh_stale_source_notes
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # HB_PA_CONFIG points app-support (backups/receipts) + vault under tmp.
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
        "vault_markdown_write_enabled": True, "source_card_excerpt_chars": 120,
        "external_sources": [{"source_root_key": "proj", "path": str(root_dir), "enabled": True}],
    })
    return SourceIndexRepository(db), config, root_dir, vault, db


def _index_file(env, name: str, body: str) -> str:
    repo, config, root_dir, _vault, _db = env
    f = root_dir / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return index_source_file(f, config.external_sources[0], repo, config)


def test_generate_card_traceability(env) -> None:
    repo, config, _root, vault, db = env
    sid = _index_file(env, "22-101-00/RFI 12 conduit.md", "Underground conduit for electrical.")
    out = generate_source_card(repo, config, source_id=sid)
    assert out["status"] == "generated" and out["overwritten"] is False
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert card.startswith("---")
    for token in ("note_type: source_card", f'source_id: "{sid}"', "source_kind: \"external_file\"",
                  "source_path: \"22-101-00/RFI 12 conduit.md\"", "source_sha256:", "source_mtime_ns:",
                  "indexed_at:", "generated_at:", "stale: false", "project_number: \"22-101-00\""):
        assert token in card, token
    assert "## Source Basis" in card and f"Source ID: `{sid}`" in card
    assert sqlite3.connect(db).execute(
        "SELECT generation_status FROM source_intelligence_generated_notes WHERE source_entity_id=?", (sid,)
    ).fetchone()[0] == "generated"


def test_no_raw_body_dump(env) -> None:
    repo, config, _root, vault, _db = env
    long_body = "PARAGRAPH ONE. " + ("verylongtoken " * 80)
    sid = _index_file(env, "big.md", long_body)
    out = generate_source_card(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    # Phase 8 drops the raw indexed-text preview entirely; the file body is never dumped into the card.
    assert "Indexed Text Preview" not in card
    assert "verylongtoken" not in card


def test_obsidian_note_not_applicable(env) -> None:
    repo, config, _root, _vault, _db = env
    sid = repo.upsert_source_file({
        "source_kind": "obsidian_note", "rel_path": "Notes/X.md", "content_sha256": "s",
        "mtime_ns": 1, "file_ext": "md", "extraction_status": "ok", "text_excerpt": "x",
    })
    with pytest.raises(ObsidianMcpToolError) as exc:
        generate_source_card(repo, config, source_id=sid)
    assert exc.value.code == "source_card_not_applicable"


def test_email_link_card_has_no_body(env) -> None:
    repo, config, _root, vault, _db = env
    sid = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                  domain_ref_id="msg-secret-1", project_number="22-101-00")
    out = generate_source_card(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "Linked record:" in card  # link-only source summary, not a body section
    assert "Indexed Text Preview" not in card  # no body section for link sources
    assert "email_messages" in card and "msg-secret-1" in card


def test_sensitive_source_preview_withheld(env, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, config, root_dir, vault, _db = env
    monkeypatch.setenv("HB_TEXT_VAULT_KEY", "dGVzdC1rZXktZm9yLXRleHQtdmF1bHQtMzJieXRlcyE=")
    sroot = ExternalSourceRoot(source_root_key="proj", path=str(root_dir), sensitive=True)
    f = root_dir / "secret.md"
    f.write_text("confidential salary figures", encoding="utf-8")
    sid = index_source_file(f, sroot, repo, config)
    out = generate_source_card(repo, config, source_id=sid)
    card = (vault / out["note_path"]).read_text(encoding="utf-8")
    assert "extracted text withheld" in card  # card basis flags the sensitive source
    assert "Indexed Text Preview" not in card
    assert "confidential salary" not in card  # sensitive text never in the card


def test_writes_disabled_blocks_card(env) -> None:
    repo, config, _root, _vault, _db = env
    config = config.model_copy(update={"writes_enabled": False})
    sid = _index_file(env, "a.md", "hello")
    with pytest.raises(ObsidianMcpToolError):
        generate_source_card(repo, config, source_id=sid)


def test_exists_requires_overwrite_then_single_row(env) -> None:
    repo, config, _root, vault, db = env
    sid = _index_file(env, "a.md", "hello conduit")
    generate_source_card(repo, config, source_id=sid)
    with pytest.raises(ObsidianMcpToolError) as exc:
        generate_source_card(repo, config, source_id=sid)  # exists, no overwrite
    assert exc.value.code == "note_already_exists"
    generate_source_card(repo, config, source_id=sid, overwrite=True)  # SHA-gated refresh
    assert sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE source_entity_id=?", (sid,)
    ).fetchone()[0] == 1


def test_stale_then_refresh(env) -> None:
    repo, config, root_dir, vault, db = env
    sid = _index_file(env, "a.md", "alpha conduit original")
    out = generate_source_card(repo, config, source_id=sid)
    # change the source + reindex -> card row goes stale (auto)
    (root_dir / "a.md").write_text("beta tunnel revised content", encoding="utf-8")
    scan_source_root(config.external_sources[0], repo, config)
    assert sqlite3.connect(db).execute(
        "SELECT generation_status FROM source_intelligence_generated_notes WHERE source_entity_id=?", (sid,)
    ).fetchone()[0] == "stale"
    res = refresh_stale_source_notes(repo, config)
    assert res["count"] == 1 and res["failed"] == []
    assert sqlite3.connect(db).execute(
        "SELECT generation_status FROM source_intelligence_generated_notes WHERE source_entity_id=?", (sid,)
    ).fetchone()[0] == "generated"
    # Refreshed deterministic card was re-rendered (the body carries no raw source text to assert on).
    assert "## Source Basis" in (vault / out["note_path"]).read_text(encoding="utf-8")


def test_source_not_found(env) -> None:
    repo, config, _root, _vault, _db = env
    with pytest.raises(ObsidianMcpToolError) as exc:
        generate_source_card(repo, config, source_id="does-not-exist")
    assert exc.value.code == "source_not_found"


# ---------------- R11-D2 domain-locator collision coverage (card layer) ----------------

def test_r11_d2_cross_table_link_cards_distinct(env) -> None:
    # same (source_kind, domain_ref_id) across DIFFERENT domain_ref_table → distinct entities + distinct
    # cards (the synthetic locator address includes domain_ref_table).
    repo, config, _root, vault, _db = env
    e1 = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                 domain_ref_id="dup-1", project_number="22-101-00")
    e2 = repo.link_domain_source(source_kind="email", domain_ref_table="email_threads",
                                 domain_ref_id="dup-1", project_number="22-101-00")
    assert e1 != e2
    o1 = generate_source_card(repo, config, source_id=e1)
    o2 = generate_source_card(repo, config, source_id=e2)
    assert o1["note_path"] != o2["note_path"]
    c1 = (vault / o1["note_path"]).read_text(encoding="utf-8")
    c2 = (vault / o2["note_path"]).read_text(encoding="utf-8")
    assert "email_messages" in c1 and "email_threads" in c2


def test_r11_d2_cross_kind_same_table_id_fails_closed(env) -> None:
    # same (domain_ref_table, id) across DIFFERENT source_kind: the frozen V128 UNIQUE(domain_ref_table,
    # domain_ref_id) forbids a distinct second entity, so the link is refused fail-closed (no silent
    # rebind to the first entity). Repo truth supersedes the accepted "distinct entities" here — flagged
    # for reauthorization in the implementation report.
    repo, _config, _root, _vault, _db = env
    repo.link_domain_source(source_kind="email", domain_ref_table="records", domain_ref_id="col-1")
    with pytest.raises(sqlite3.IntegrityError):
        repo.link_domain_source(source_kind="schedule", domain_ref_table="records",
                                domain_ref_id="col-1")
