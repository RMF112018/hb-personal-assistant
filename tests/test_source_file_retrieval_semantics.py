"""Phase B / B1+B3 — complete-read retrieval-state semantics + identity fail-closed.

Covers the explicit non-support / denial / unavailable states that do NOT need real content, and proves
identity is safe: a source_ref is the path-free handoff, cross-root/unconfigured/forged references fail
closed, and traversal/symlink escapes are denied. Every blocked complete response withholds content
(``content is None``, ``completeness_state == "none"``) and leaks no absolute path.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_connector_service as svc
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_connector_models import (
    SourceConnectorValidationError,
    encode_source_ref,
)
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.store.migrator import SQLiteMigrator


def _row(db: str, *, root_key: str, rel_path: str, ext: str) -> str:
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,?,?,?,NULL,?)",
                  (sid, ext, 10, 1, "d", "pending", now))
        c.commit()
    return sid


def _trust(db: str, config: ObsidianMcpConfig, root_key: str) -> None:
    from hb_assistant.obsidian_mcp.source_indexer import _root_fingerprint

    cfg_root = next(r for r in config.external_sources if r.source_root_key == root_key)
    fp = _root_fingerprint(cfg_root, config)
    rph = hashlib.sha256(str(Path(cfg_root.path)).encode()).hexdigest()[:32]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO source_index_scan_generations(generation_id, root_key, status, "
                  "root_path_hash, policy_fingerprint, started_at, updated_at, metadata_walk_completed_at, "
                  "reconciliation_completed_at, finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (f"gen-{root_key}", root_key, "completed", rph, fp, now, now, now, now, now))
        c.commit()


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work / "Sched").mkdir(parents=True)
    (work / "Sched" / "p.xer").write_text("dummy xer")
    (work / "Sched" / "bundle.zip").write_bytes(b"PK\x03\x04zipbytes")
    (work / "Sched" / "app.exe").write_bytes(b"MZbinary")
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work", path=str(work))])
    ids = {
        "xer": _row(db, root_key="work", rel_path="Sched/p.xer", ext="xer"),
        "zip": _row(db, root_key="work", rel_path="Sched/bundle.zip", ext="zip"),
        "exe": _row(db, root_key="work", rel_path="Sched/app.exe", ext="exe"),
    }
    _trust(db, config, "work")
    return {"db": db, "repo": SourceIndexRepository(db), "config": config, "ids": ids,
            "work": work, "tmp": str(tmp_path)}


def _read(env, sid, **kw):
    return svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(sid),
                               mode="complete", **kw)


def _blocked(r) -> None:
    assert r["content"] is None
    assert r["completeness_state"] == "none"


def test_xer_is_explicit_unsupported(env) -> None:
    r = _read(env, env["ids"]["xer"])
    assert r["retrieval_state"] == "unsupported_format"
    assert "not supported" in (r.get("recommended_next_action") or "").lower()
    _blocked(r)


def test_zip_is_archive_not_expanded(env) -> None:
    r = _read(env, env["ids"]["zip"])
    assert r["retrieval_state"] == "archive_not_expanded"
    _blocked(r)


def test_unknown_binary_unsupported(env) -> None:
    r = _read(env, env["ids"]["exe"])
    assert r["retrieval_state"] == "unsupported_format"
    _blocked(r)


def test_sensitive_root_denied(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    secure = tmp_path / "secure"
    secure.mkdir()
    (secure / "s.txt").write_text("secret")
    config = ObsidianMcpConfig(external_sources=[
        ExternalSourceRoot(source_root_key="secure", path=str(secure), sensitive=True)])
    sid = _row(db, root_key="secure", rel_path="s.txt", ext="txt")
    _trust(db, config, "secure")
    r = svc.read_source_file(SourceIndexRepository(db), config, source_ref=encode_source_ref(sid),
                             mode="complete")
    assert r["retrieval_state"] == "denied"
    assert r["denied"] is True
    _blocked(r)


def test_path_escape_denied(env) -> None:
    sid = _row(env["db"], root_key="work", rel_path="../escape.txt", ext="txt")
    r = _read(env, sid)
    assert r["retrieval_state"] == "denied"
    _blocked(r)


def test_symlink_escape_denied(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside secret")
    link = work / "link.txt"
    link.symlink_to(outside)
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work", path=str(work))])
    sid = _row(db, root_key="work", rel_path="link.txt", ext="txt")
    _trust(db, config, "work")
    r = svc.read_source_file(SourceIndexRepository(db), config, source_ref=encode_source_ref(sid),
                             mode="complete")
    assert r["retrieval_state"] == "denied"
    _blocked(r)


# ---------------- identity fail-closed (B3) ----------------

def test_source_ref_is_path_free(env) -> None:
    ref = encode_source_ref(env["ids"]["xer"])
    assert "work" not in ref and "Sched" not in ref and "/" not in ref


def test_unconfigured_root_source_ref_unavailable(tmp_path) -> None:
    # A source row bound to a root that is NOT in the serve config cannot be read (cross-root safety).
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    sid = _row(db, root_key="hidden", rel_path="a.txt", ext="txt")
    config = ObsidianMcpConfig(external_sources=[])  # 'hidden' not configured
    r = svc.read_source_file(SourceIndexRepository(db), config, source_ref=encode_source_ref(sid),
                             mode="complete")
    assert r["retrieval_state"] == "unavailable" and r["content"] is None


def test_forged_source_ref_rejected(env) -> None:
    # valid checksum shape but no such source -> source_not_found; tampered ref -> invalid_source_ref
    ghost = encode_source_ref("0" * 32)
    with pytest.raises(SourceConnectorValidationError) as e1:
        svc.read_source_file(env["repo"], env["config"], source_ref=ghost, mode="complete")
    assert "source_not_found" in str(e1.value)
    with pytest.raises(SourceConnectorValidationError):
        svc.read_source_file(env["repo"], env["config"], source_ref="hbsrc1_tampered", mode="complete")


def test_no_absolute_paths_in_any_blocked_response(env) -> None:
    for key in ("xer", "zip", "exe"):
        r = _read(env, env["ids"][key])
        blob = json.dumps(r, default=str)
        assert env["tmp"] not in blob and "/Users/" not in blob
