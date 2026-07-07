"""N8C-12 — NAS source-root connector service: root-aware discovery, keyset pagination, bounded reads.

Proves indexed NAS source FILES are searchable/listable/inspectable/bounded-readable as first-class,
root-aware objects: every row carries source_root_key + rel_path + an opaque source_ref; pagination is
deterministic keyset (incl. equal-rank rows) and rejects query/filter/order mismatches; metadata
distinguishes the original file from a supplemental generated card; bounded reads are extension-gated with an
indexed_excerpt_fallback; sensitive roots are never live-read; no absolute host path is ever exposed; and no
directory traversal / scan / mutation occurs in the request path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_connector_service as svc
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.store.migrator import SQLiteMigrator


def _insert(db: str, *, root_key: str, rel_path: str, body: str | None, ext: str,
            extraction_status: str = "ok") -> str:
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        digest = hashlib.sha256((body or "").encode()).hexdigest()
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,?,?,?,NULL,'t')",
                  (sid, ext, len(body or ""), 1, digest, extraction_status))
        if body is not None:
            c.execute("INSERT INTO source_intelligence_text(source_id,text_excerpt,excerpt_char_count,"
                      "excerpt_truncated,raw_body_persisted,redaction_applied,updated_at) "
                      "VALUES(?,?,?,0,0,1,'t')", (sid, body, len(body)))
            rowid = c.execute("INSERT INTO source_intelligence_fts(text_excerpt,rel_path,aux) "
                              "VALUES(?,?,NULL)", (body, rel_path)).lastrowid
            c.execute("UPDATE source_intelligence_metadata SET fts_rowid=? WHERE source_id=?",
                      (rowid, sid))
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.commit()
    return sid


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work / "Projects").mkdir(parents=True)
    (work / "Projects" / "contract_A.txt").write_text("payment application number three for the contract")
    (work / "Projects" / "invoice_B.txt").write_text("invoice total due for payment on this project")
    secure = tmp_path / "secure"
    secure.mkdir()
    (secure / "salary.txt").write_text("confidential payment salary figures")
    ids = {
        "a": _insert(db, root_key="work", rel_path="Projects/contract_A.txt",
                     body="payment application number three for the contract", ext="txt"),
        "b": _insert(db, root_key="work", rel_path="Projects/invoice_B.txt",
                     body="invoice total due for payment on this project", ext="txt"),
        "sensitive": _insert(db, root_key="secure", rel_path="salary.txt",
                             body="confidential payment salary figures", ext="txt"),
        "binary": _insert(db, root_key="work", rel_path="Projects/logo.png", body=None, ext="png",
                          extraction_status="unsupported"),
        "escape": _insert(db, root_key="work", rel_path="../escape.txt", body="indexed escape body",
                          ext="txt"),
    }
    config = ObsidianMcpConfig(external_sources=[
        ExternalSourceRoot(source_root_key="work", path=str(work)),
        ExternalSourceRoot(source_root_key="secure", path=str(secure), sensitive=True),
    ])
    return {"db": db, "repo": SourceIndexRepository(db), "config": config, "ids": ids,
            "root_abs": str(work), "tmp": str(tmp_path)}


def _no_abs(payload, tmp: str) -> None:
    assert tmp not in json.dumps(payload, default=str)
    assert "/Users/" not in json.dumps(payload, default=str)


def test_search_root_aware_rows(env) -> None:
    r = svc.search_source_files(env["repo"], env["config"], query="payment", limit=10)
    assert r["count"] >= 2
    row = r["items"][0]
    assert set(row) >= {"source_id", "source_ref", "source_root_key", "rel_path", "extension",
                        "mime_type", "snippet"}
    assert row["source_root_key"] in {"work", "secure"}
    assert not str(row["rel_path"]).startswith("/")
    _no_abs(r, env["tmp"])


def test_search_root_and_ext_filter(env) -> None:
    r = svc.search_source_files(env["repo"], env["config"], query="payment", source_root_key="secure",
                               limit=10)
    assert r["count"] == 1 and r["items"][0]["source_root_key"] == "secure"
    r2 = svc.search_source_files(env["repo"], env["config"], query="payment", file_ext="txt", limit=10)
    assert all(i["extension"] == "txt" for i in r2["items"])


def test_search_bounded_snippet(env) -> None:
    r = svc.search_source_files(env["repo"], env["config"], query="payment", limit=10)
    for i in r["items"]:
        assert i["snippet"] is None or len(i["snippet"]) <= 260


def test_cursor_deterministic_nonoverlapping(env) -> None:
    seen = []
    cursor = None
    for _ in range(10):
        page = svc.search_source_files(env["repo"], env["config"], query="payment", limit=1,
                                       cursor=cursor)
        seen.extend(i["source_id"] for i in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)), "pages overlapped"
    assert len(seen) >= 3


def test_cursor_equal_rank_rows(env, tmp_path: Path) -> None:
    # two files with identical content → identical bm25 rank; keyset tie-break must still total-order them.
    body = "identical duplicate payment body text"
    _insert(env["db"], root_key="work", rel_path="Dup/one.txt", body=body, ext="txt")
    _insert(env["db"], root_key="work", rel_path="Dup/two.txt", body=body, ext="txt")
    seen, cursor = [], None
    for _ in range(20):
        page = svc.search_source_files(env["repo"], env["config"], query="identical", limit=1,
                                       cursor=cursor)
        seen.extend(i["source_id"] for i in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 2


def test_cursor_query_mismatch_rejected(env) -> None:
    page = svc.search_source_files(env["repo"], env["config"], query="payment", limit=1)
    with pytest.raises(SourceConnectorValidationError) as ei:
        svc.search_source_files(env["repo"], env["config"], query="different", limit=1,
                                cursor=page["next_cursor"])
    assert str(ei.value) == "cursor_query_mismatch"


def test_list_root_scoped_prefix_keyset(env) -> None:
    r = svc.list_source_files(env["repo"], env["config"], source_root_key="work", prefix="Projects/",
                             limit=10)
    assert all(i["source_root_key"] == "work" for i in r["items"])
    assert all(str(i["rel_path"]).startswith("Projects/") for i in r["items"])
    assert all(i["entry_type"] == "file" for i in r["items"])
    _no_abs(r, env["tmp"])


def test_list_requires_root(env) -> None:
    with pytest.raises(SourceConnectorValidationError):
        svc.list_source_files(env["repo"], env["config"], source_root_key="")


def test_metadata_distinguishes_source_and_card(env) -> None:
    # attach a generated card to source 'a'
    env["repo"].record_generated_note(env["ids"]["a"], "Source Notes/contract_A.md", "generated", "t")
    md = svc.source_file_metadata(env["repo"], env["config"], source_id=env["ids"]["a"])
    assert md["object_type"] == "source_file" and md["is_source_file"] is True
    assert md["generated_card_available"] is True
    assert md["generated_card_rel_path"] == "Source Notes/contract_A.md"
    assert md["source_root_key"] == "work" and md["rel_path"] == "Projects/contract_A.txt"
    assert md["indexed_text_available"] is True
    _no_abs(md, env["tmp"])
    # a source with no card is still returned as the primary object (never forced into a card)
    md_b = svc.source_file_metadata(env["repo"], env["config"], source_id=env["ids"]["b"])
    assert md_b["generated_card_available"] is False and md_b["is_source_file"] is True


def test_metadata_by_source_ref(env) -> None:
    md = svc.source_file_metadata(env["repo"], env["config"], source_id=env["ids"]["a"])
    md2 = svc.source_file_metadata(env["repo"], env["config"], source_ref=md["source_ref"])
    assert md2["source_id"] == env["ids"]["a"]


def test_metadata_unknown_raises(env) -> None:
    with pytest.raises(SourceConnectorValidationError) as ei:
        svc.source_file_metadata(env["repo"], env["config"], source_id="0" * 32)
    assert str(ei.value) == "source_not_found"


def test_read_live_bounded(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["a"], max_chars=10)
    assert r["content_source"] == "live_extract"
    assert r["char_count"] == 10 and len(r["content"]) == 10 and r["truncated"] is True
    _no_abs(r, env["tmp"])


def test_read_indexed_fallback_when_not_live(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["a"], prefer_live=False)
    assert r["content_source"] == "indexed_excerpt_fallback" and r["reason"] == "indexed_requested"
    assert r["content"] is not None


def test_read_sensitive_root_never_live(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["sensitive"])
    assert r["content_source"] == "indexed_excerpt_fallback" and r["reason"] == "sensitive_root"


def test_read_denies_unsupported_binary(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["binary"])
    assert r["denied"] is True and r["content"] is None and r["reason"] == "unsupported_type"


def test_read_path_escape_is_contained(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["escape"])
    # a ``../`` rel_path never yields a live read outside the root — it is rejected by the hidden-segment
    # rule (blocked_path) or the containment guard (path_escape); either way → indexed fallback.
    assert r["content_source"] == "indexed_excerpt_fallback"
    assert r["reason"] in {"blocked_path", "path_escape"}


def test_read_no_directory_traversal(env, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real_scandir = os.scandir
    monkeypatch.setattr(os, "scandir", lambda *a, **k: (calls.append("scandir"), real_scandir(*a, **k))[1])
    monkeypatch.setattr(os, "walk", lambda *a, **k: calls.append("walk") or iter(()))
    svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["a"], max_chars=50)
    svc.search_source_files(env["repo"], env["config"], query="payment", limit=5)
    svc.list_source_files(env["repo"], env["config"], source_root_key="work", limit=5)
    assert calls == [], f"unexpected filesystem traversal: {calls}"


def _snapshot(db: str) -> str:
    with sqlite3.connect(db) as c:
        rows = []
        for tbl in ("source_intelligence_sources", "source_intelligence_metadata",
                    "source_intelligence_text", "source_intelligence_generated_notes",
                    "source_intelligence_events"):
            rows.append(str(c.execute(f"SELECT * FROM {tbl} ORDER BY 1").fetchall()))
    return hashlib.sha256("|".join(rows).encode()).hexdigest()


def test_reads_do_not_mutate(env) -> None:
    before = _snapshot(env["db"])
    svc.source_status(env["repo"], env["config"])
    svc.list_source_roots(env["repo"], env["config"])
    svc.search_source_files(env["repo"], env["config"], query="payment", limit=10)
    svc.list_source_files(env["repo"], env["config"], source_root_key="work", limit=10)
    svc.source_file_metadata(env["repo"], env["config"], source_id=env["ids"]["a"])
    svc.read_source_file(env["repo"], env["config"], source_id=env["ids"]["a"], max_chars=50)
    assert _snapshot(env["db"]) == before


def test_status_and_roots_no_abs_paths(env) -> None:
    st = svc.source_status(env["repo"], env["config"])
    assert "configured_roots" not in st and st["index_enabled"] is True
    assert st["configured_root_count"] == 2
    _no_abs(st, env["tmp"])
    roots = svc.list_source_roots(env["repo"], env["config"])
    keys = {r["source_root_key"] for r in roots["roots"]}
    assert keys == {"work", "secure"}
    _no_abs(roots, env["tmp"])
