"""Source indexer: bounded idempotent scan, extraction dispatch, caps, project match."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import (
    index_source_file,
    match_path_to_project,
    scan_source_root,
)
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "i.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root_dir = tmp_path / "proj"
    (root_dir / "22-101-00").mkdir(parents=True)
    root = ExternalSourceRoot(source_root_key="proj", path=str(root_dir))
    config = ObsidianMcpConfig.model_validate({
        "vault_root": str(tmp_path / "vault"), "external_sources": [root.model_dump()],
        "source_index_max_excerpt_chars": 100, "source_index_max_chunks": 3,
        "source_index_max_chunk_chars": 20,
    })
    return SourceIndexRepository(db), config, root, root_dir, db


def test_match_path_to_project() -> None:
    assert match_path_to_project("22-101-00/RFI.pdf") == ("22-101-00", "22-101-00", "high")
    assert match_path_to_project("misc/notes.md") == (None, None, "none")


def test_index_and_project_relationship(env) -> None:
    repo, config, root, root_dir, db = env
    f = root_dir / "22-101-00" / "RFI conduit.md"
    f.write_text("Underground conduit", encoding="utf-8")
    sid = index_source_file(f, root, repo, config)
    assert sid is not None
    con = sqlite3.connect(db)
    rel = con.execute(
        "SELECT relation, dst_ref FROM source_intelligence_relationships WHERE src_source_id=?", (sid,)
    ).fetchone()
    assert rel == ("belongs_to_project", "22-101-00")


def test_scan_idempotent_skip_and_reindex(env) -> None:
    repo, config, root, root_dir, _db = env
    f = root_dir / "a.md"
    f.write_text("alpha", encoding="utf-8")
    r1 = scan_source_root(root, repo, config)
    assert r1.indexed == 1 and r1.skipped == 0
    r2 = scan_source_root(root, repo, config)
    assert r2.indexed == 0 and r2.skipped == 1  # unchanged → skip
    f.write_text("beta changed", encoding="utf-8")
    r3 = scan_source_root(root, repo, config)
    assert r3.indexed == 1  # changed → reindex


def test_scan_marks_deleted(env) -> None:
    repo, config, root, root_dir, db = env
    f = root_dir / "gone.md"
    f.write_text("temp", encoding="utf-8")
    scan_source_root(root, repo, config)
    f.unlink()
    report = scan_source_root(root, repo, config)
    assert report.deleted == 1
    assert repo.search_sources("temp") == []


def test_unsupported_extension_is_metadata_only(env) -> None:
    repo, config, root, root_dir, db = env
    f = root_dir / "image.png"
    f.write_bytes(b"\x89PNG\r\n")
    sid = index_source_file(f, root, repo, config)
    con = sqlite3.connect(db)
    status = con.execute(
        "SELECT extraction_status FROM source_intelligence_metadata WHERE source_id=?", (sid,)
    ).fetchone()[0]
    assert status == "unsupported"
    assert con.execute("SELECT COUNT(*) FROM source_intelligence_text WHERE source_id=?", (sid,)).fetchone()[0] == 0


def test_oversize_file_skipped(env) -> None:
    repo, config, root, root_dir, db = env
    config = config.model_copy(update={"max_file_mb": 0})  # force the size gate
    f = root_dir / "big.md"
    f.write_text("x" * 50, encoding="utf-8")
    sid = index_source_file(f, root, repo, config)
    con = sqlite3.connect(db)
    assert con.execute(
        "SELECT extraction_status FROM source_intelligence_metadata WHERE source_id=?", (sid,)
    ).fetchone()[0] == "skipped_too_large"


def test_excerpt_and_chunk_caps(env) -> None:
    repo, config, root, root_dir, db = env  # caps: excerpt 100, chunks 3 x 20 chars
    f = root_dir / "long.md"
    f.write_text("y" * 500, encoding="utf-8")
    sid = index_source_file(f, root, repo, config)
    con = sqlite3.connect(db)
    excerpt_len = con.execute(
        "SELECT excerpt_char_count FROM source_intelligence_text WHERE source_id=?", (sid,)
    ).fetchone()[0]
    assert excerpt_len <= 100
    chunk_count = con.execute(
        "SELECT COUNT(*) FROM source_intelligence_chunks WHERE source_id=?", (sid,)
    ).fetchone()[0]
    assert chunk_count <= 3


def test_corrupt_pdf_does_not_raise(env) -> None:
    repo, config, root, root_dir, db = env
    # By default pdf is metadata-only (the interim safe policy), so a corrupt pdf is never parsed. Enable
    # the hardened opt-in here to exercise the actual parser robustness path: it must still not raise.
    config = config.model_copy(update={"source_index_enable_synchronous_parser_extraction": True})
    f = root_dir / "broken.pdf"
    f.write_bytes(b"not really a pdf")
    sid = index_source_file(f, root, repo, config)  # must not raise
    con = sqlite3.connect(db)
    status = con.execute(
        "SELECT extraction_status FROM source_intelligence_metadata WHERE source_id=?", (sid,)
    ).fetchone()[0]
    assert status in {"ok", "failed", "unsupported"}


def test_corrupt_pdf_metadata_only_by_default(env) -> None:
    # Default policy: a corrupt pdf is registered metadata-only (pending), NOT hashed or parsed — the
    # safety win that prevents a hung/pathological parser from stalling the scan.
    repo, config, root, root_dir, db = env
    f = root_dir / "broken2.pdf"
    f.write_bytes(b"not really a pdf")
    sid = index_source_file(f, root, repo, config)
    con = sqlite3.connect(db)
    status, sha = con.execute(
        "SELECT extraction_status, content_sha256 FROM source_intelligence_metadata WHERE source_id=?",
        (sid,),
    ).fetchone()
    assert status == "pending" and sha is None


def test_sensitive_root_uses_text_vault(env, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, config, _root, root_dir, db = env
    monkeypatch.setenv("HB_TEXT_VAULT_KEY", "dGVzdC1rZXktZm9yLXRleHQtdmF1bHQtMzJieXRlcyE=")
    sroot = ExternalSourceRoot(source_root_key="proj", path=str(root_dir), sensitive=True)
    f = root_dir / "secret.md"
    f.write_text("confidential salary figures", encoding="utf-8")
    sid = index_source_file(f, sroot, repo, config)
    con = sqlite3.connect(db)
    excerpt, ref = con.execute(
        "SELECT text_excerpt, text_vault_ref FROM source_intelligence_text WHERE source_id=?", (sid,)
    ).fetchone()
    assert excerpt is None and ref is not None  # plaintext not stored; vault ref instead
    # sensitive text is NOT placed into FTS
    assert repo.search_sources("salary") == []
