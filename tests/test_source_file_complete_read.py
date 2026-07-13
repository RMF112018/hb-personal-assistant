"""Phase B / B1 — complete-or-explicit-failure reads of NAS source FILES by source_ref.

Proves ``assistant_source_file_read(mode="complete")`` returns a *whole* supported text file with
explicit complete/raw_text/complete states, never truncates-and-labels-complete, redacts absolute
paths, and fails closed (too_large / unavailable / denied / stale) with content withheld. Uses a real
SQLite index + real temp filesystem (no mocks); files are indexed with their true size/mtime so the
index-divergence guard passes on an unchanged file and trips on a changed one.
"""

from __future__ import annotations

import hashlib
import json
import os
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


def _index_file(db: str, *, root_key: str, rel_path: str, abs_file: Path | None, ext: str,
                body: str | None = None, extraction_status: str = "ok",
                mtime_ns: int | None = None, size_bytes: int | None = None) -> str:
    """Insert a source row + metadata (+ excerpt) using the REAL on-disk size/mtime by default so a
    complete read is not spuriously flagged stale."""
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    if abs_file is not None and abs_file.exists():
        st = abs_file.stat()
        size = size_bytes if size_bytes is not None else st.st_size
        mt = mtime_ns if mtime_ns is not None else st.st_mtime_ns
    else:
        size = size_bytes if size_bytes is not None else len(body or "")
        mt = mtime_ns if mtime_ns is not None else 1
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        digest = hashlib.sha256((body or "").encode()).hexdigest()
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,?,?,?,NULL,?)",
                  (sid, ext, size, mt, digest, extraction_status, now))
        if body is not None:
            c.execute("INSERT INTO source_intelligence_text(source_id,text_excerpt,excerpt_char_count,"
                      "excerpt_truncated,raw_body_persisted,redaction_applied,updated_at) "
                      "VALUES(?,?,?,0,0,1,'t')", (sid, body[:600], len(body[:600])))
            rowid = c.execute("INSERT INTO source_intelligence_fts(text_excerpt,rel_path,aux) "
                              "VALUES(?,?,NULL)", (body, rel_path)).lastrowid
            c.execute("UPDATE source_intelligence_metadata SET fts_rowid=? WHERE source_id=?",
                      (rowid, sid))
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.commit()
    return sid


def _trust(db: str, config: ObsidianMcpConfig, root_key: str) -> None:
    from hb_assistant.obsidian_mcp.source_indexer import _root_fingerprint

    cfg_root = next(r for r in config.external_sources if r.source_root_key == root_key)
    fp = _root_fingerprint(cfg_root, config)
    root_path_hash = hashlib.sha256(str(Path(cfg_root.path)).encode("utf-8")).hexdigest()[:32]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO source_index_scan_generations(generation_id, root_key, status, root_path_hash, "
            "policy_fingerprint, started_at, updated_at, metadata_walk_completed_at, "
            "reconciliation_completed_at, finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (f"gen-{root_key}", root_key, "completed", root_path_hash, fp, now, now, now, now, now),
        )
        c.commit()


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work / "Projects").mkdir(parents=True)
    text_body = "Pay Application No. 3\nContract A\n" + ("line of scope\n" * 50)
    (work / "Projects" / "payapp.txt").write_text(text_body)
    (work / "Projects" / "data.csv").write_text("col1,col2\n1,2\n3,4\n")
    (work / "Projects" / "meta.json").write_text('{"project": "A", "amount": 12345}')
    config = ObsidianMcpConfig(external_sources=[
        ExternalSourceRoot(source_root_key="work", path=str(work)),
    ])
    ids = {
        "txt": _index_file(db, root_key="work", rel_path="Projects/payapp.txt",
                           abs_file=work / "Projects" / "payapp.txt", ext="txt", body=text_body),
        "csv": _index_file(db, root_key="work", rel_path="Projects/data.csv",
                           abs_file=work / "Projects" / "data.csv", ext="csv", body="col1,col2\n1,2\n3,4\n"),
        "json": _index_file(db, root_key="work", rel_path="Projects/meta.json",
                            abs_file=work / "Projects" / "meta.json", ext="json",
                            body='{"project": "A", "amount": 12345}'),
    }
    _trust(db, config, "work")
    return {"db": db, "repo": SourceIndexRepository(db), "config": config, "ids": ids,
            "work": work, "tmp": str(tmp_path), "text_body": text_body}


def _read(env, source_ref=None, source_id=None, **kw):
    return svc.read_source_file(env["repo"], env["config"], source_ref=source_ref,
                               source_id=source_id, **kw)


def _no_abs(payload, tmp: str) -> None:
    blob = json.dumps(payload, default=str)
    assert tmp not in blob
    assert "/Users/" not in blob


# ---------------------------------------------------------------- complete text reads

def test_complete_txt_returns_whole_file(env) -> None:
    ref = encode_source_ref(env["ids"]["txt"])
    r = _read(env, source_ref=ref, mode="complete")
    assert r["retrieval_state"] == "complete"
    assert r["content_state"] == "raw_text"
    assert r["completeness_state"] == "complete"
    assert r["content"] == env["text_body"]  # WHOLE file, not an excerpt
    assert r["truncated"] is False
    _no_abs(r, env["tmp"])


def test_complete_csv_and_json_whole(env) -> None:
    for key, expected in (("csv", "col1,col2\n1,2\n3,4\n"), ("json", '{"project": "A", "amount": 12345}')):
        r = _read(env, source_ref=encode_source_ref(env["ids"][key]), mode="complete")
        assert r["retrieval_state"] == "complete" and r["content"] == expected


def test_complete_carries_provenance_block(env) -> None:
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="complete")
    p = r["provenance"]
    assert p["source_ref"] == encode_source_ref(env["ids"]["txt"])
    assert p["root_key"] == "work" and p["relative_path"] == "Projects/payapp.txt"
    assert p["filename"] == "payapp.txt" and p["extension"] == "txt"
    # top-level state fields are authoritative; provenance mirrors them
    assert p["retrieval_state"] == r["retrieval_state"] == "complete"
    assert p["content_state"] == r["content_state"]
    assert p["completeness_state"] == r["completeness_state"]
    _no_abs(r, env["tmp"])


def test_search_ref_then_complete_roundtrip(env) -> None:
    res = svc.search_source_files(env["repo"], env["config"], query="Pay Application", limit=10)
    hit = next(i for i in res["items"] if i["rel_path"] == "Projects/payapp.txt")
    r = _read(env, source_ref=hit["source_ref"], mode="complete")
    assert r["retrieval_state"] == "complete" and r["content"] == env["text_body"]


# ---------------------------------------------------------------- fail-closed states

def test_complete_over_output_budget_is_too_large_not_partial(env) -> None:
    # A complete request whose representation exceeds the budget must NOT degrade to a truncated partial.
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="complete", max_bytes=10)
    assert r["retrieval_state"] == "too_large"
    assert r["completeness_state"] == "none"
    assert r["content"] is None
    assert r["content_state"] == "none"


def test_complete_input_over_limit_too_large(env, monkeypatch) -> None:
    monkeypatch.setattr(env["config"], "source_complete_read_max_input_bytes", 5)
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="complete")
    assert r["retrieval_state"] == "too_large" and r["content"] is None


def test_complete_deleted_is_unavailable(env) -> None:
    sid = env["ids"]["txt"]
    with sqlite3.connect(env["db"]) as c:
        c.execute("UPDATE source_intelligence_sources SET deleted=1, active=0 WHERE source_id=?", (sid,))
        c.commit()
    r = _read(env, source_ref=encode_source_ref(sid), mode="complete")
    assert r["retrieval_state"] == "unavailable" and r["content"] is None


def test_complete_untrusted_root_is_stale(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work).mkdir()
    (work / "a.txt").write_text("hello")
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work", path=str(work))])
    sid = _index_file(db, root_key="work", rel_path="a.txt", abs_file=work / "a.txt", ext="txt", body="hello")
    # deliberately NOT trusted (no completed generation)
    r = svc.read_source_file(SourceIndexRepository(db), config, source_ref=encode_source_ref(sid),
                             mode="complete")
    assert r["retrieval_state"] == "stale" and r["content"] is None


def test_complete_missing_live_file_is_unavailable(env) -> None:
    (env["work"] / "Projects" / "payapp.txt").unlink()
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="complete")
    assert r["retrieval_state"] == "unavailable" and r["reason"] == "file_absent"


def test_complete_index_divergence_is_stale(env) -> None:
    # Bump the file's mtime after indexing -> live no longer matches the index -> stale (not served).
    f = env["work"] / "Projects" / "payapp.txt"
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="complete")
    assert r["retrieval_state"] == "stale" and r["reason"] == "index_metadata_stale"


def test_complete_change_during_read_is_stale(env, monkeypatch) -> None:
    f = env["work"] / "Projects" / "payapp.txt"
    real_read_bytes = Path.read_bytes

    def _bump_then_read(self):
        if str(self) == str(f):
            st = f.stat()
            os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 3_000_000_000))
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _bump_then_read)
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="complete")
    assert r["retrieval_state"] == "stale" and r["reason"] == "changed_during_read"


# ---------------------------------------------------------------- mode validation

def test_invalid_mode_fails_closed(env) -> None:
    with pytest.raises(SourceConnectorValidationError) as exc:
        _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="full")
    assert "invalid_request" in str(exc.value)


def test_excerpt_mode_still_partial(env) -> None:
    r = _read(env, source_ref=encode_source_ref(env["ids"]["txt"]), mode="excerpt")
    assert r["mode"] == "excerpt"
    assert r["retrieval_state"] == "partial"
    assert r["completeness_state"] == "partial"
