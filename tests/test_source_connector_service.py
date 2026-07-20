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
from hb_assistant.obsidian_mcp.source_connector_models import (
    SourceConnectorValidationError,
    encode_source_ref,
)
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.store.migrator import SQLiteMigrator

# A parseable, non-future indexed_at so the freshness state resolves to "fresh" (needed for a root to be
# trust-safe). A bare sentinel like "t" is unparseable → freshness "unknown" → the root fails closed.
_RECENT_TS = "2026-07-01T12:00:00+00:00"


def _insert(db: str, *, root_key: str, rel_path: str, body: str | None, ext: str,
            extraction_status: str = "ok") -> str:
    """Seed one indexed external-file ENTITY (post-V128 permanent-identity schema): a LIVE entity + a
    CURRENT locator carrying the legacy deterministic source_id + entity-keyed metadata/text/FTS. Returns
    the durable ``source_entity_id`` — callers hand it off via ``encode_source_ref`` (a v2 entity ref)."""
    import uuid
    legacy = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    eid = uuid.uuid4().hex
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_index_entities(source_entity_id,created_at,status) "
                  "VALUES(?,?, 'LIVE')", (eid, _RECENT_TS))
        c.execute("INSERT INTO source_index_locators(locator_id,source_entity_id,source_id,"
                  "source_root_key,rel_path,is_current_locator,tombstoned_at,generation_seq) "
                  "VALUES(?,?,?,?,?,1,NULL,0)", (uuid.uuid4().hex, eid, legacy, root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_sources(source_entity_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (eid, "external_file", root_key, rel_path))
        digest = hashlib.sha256((body or "").encode()).hexdigest()
        c.execute("INSERT INTO source_intelligence_metadata(source_entity_id,file_ext,size_bytes,"
                  "mtime_ns,content_sha256,extraction_status,fts_rowid,indexed_at) "
                  "VALUES(?,?,?,?,?,?,NULL,?)",
                  (eid, ext, len(body or ""), 1, digest, extraction_status, _RECENT_TS))
        if body is not None:
            c.execute("INSERT INTO source_intelligence_text(source_entity_id,text_excerpt,"
                      "excerpt_char_count,excerpt_truncated,raw_body_persisted,redaction_applied,"
                      "updated_at) VALUES(?,?,?,0,0,1,'t')", (eid, body, len(body)))
            rowid = c.execute("INSERT INTO source_intelligence_fts(text_excerpt,rel_path,aux) "
                              "VALUES(?,?,NULL)", (body, rel_path)).lastrowid
            c.execute("UPDATE source_intelligence_metadata SET fts_rowid=? WHERE source_entity_id=?",
                      (rowid, eid))
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.commit()
    return eid


def _make_root_trusted(db: str, config: ObsidianMcpConfig, root_key: str) -> None:
    """A2 test helper: certify ``root_key`` as SAFE — a recent parseable last_indexed_at (freshness=fresh)
    plus a COMPLETED generation whose policy_fingerprint matches the current root policy (policy=current).
    This is exactly what the shared trust authority requires before a root may serve client answers."""
    from datetime import datetime, timezone

    from hb_assistant.obsidian_mcp.source_indexer import _root_fingerprint

    cfg_root = next(r for r in config.external_sources if r.source_root_key == root_key)
    fp = _root_fingerprint(cfg_root, config)
    root_path_hash = hashlib.sha256(str(Path(cfg_root.path)).encode("utf-8")).hexdigest()[:32]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_metadata SET indexed_at=?", (now,))
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
    # A2: both configured roots are certified SAFE so the positive-path serving tests exercise a TRUSTED
    # root. ``secure`` stays sensitive (safe for path lookup, never live-readable). New fail-closed tests
    # (test_source_root_trust.py) use separate, deliberately-uncertified roots.
    _make_root_trusted(db, config, "work")
    _make_root_trusted(db, config, "secure")
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


def test_search_hyphenated_project_number_no_fts_error(env) -> None:
    # Defect E: an unquoted hyphenated project number must NOT raise "no such column: 435" — it is
    # matched as a literal phrase, and the seeded doc containing it is found.
    _insert(env["db"], root_key="work", rel_path="Projects/po-23-435-01.txt",
            body="purchase order for project 23-435-01 approved", ext="txt")
    r = svc.search_source_files(env["repo"], env["config"], query="23-435-01", limit=10)
    assert any("po-23-435-01" in i["rel_path"] for i in r["items"])


def test_search_empty_query_returns_empty(env) -> None:
    # A whitespace-only query sanitizes to nothing; return an empty page rather than an invalid MATCH.
    r = svc.search_source_files(env["repo"], env["config"], query="   ", limit=5)
    assert r["count"] == 0


def test_search_invalid_root_fails_closed(env) -> None:
    # A2: an unknown source_root_key returns a structured fail-closed envelope (unknown_root), zero items,
    # authoritative:false — never stale items and never a silent empty page.
    r = svc.search_source_files(env["repo"], env["config"], query="payment", source_root_key="nope", limit=5)
    assert r["status"] == "unknown_root"
    assert r["items"] == []
    assert r["authoritative"] is False
    assert r["root_readiness"]["trust_state"] == "unknown"


def test_list_invalid_root_fails_closed(env) -> None:
    r = svc.list_source_files(env["repo"], env["config"], source_root_key="nope")
    assert r["status"] == "unknown_root"
    assert r["items"] == []
    assert r["authoritative"] is False


def test_list_traversal_prefix_rejected(env) -> None:
    # Defect F3: a traversal/absolute prefix fails closed instead of matching nothing.
    with pytest.raises(SourceConnectorValidationError, match="unsafe_prefix"):
        svc.list_source_files(env["repo"], env["config"], source_root_key="work", prefix="../")


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
    md = svc.source_file_metadata(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]))
    assert md["object_type"] == "source_file" and md["is_source_file"] is True
    assert md["generated_card_available"] is True
    assert md["generated_card_rel_path"] == "Source Notes/contract_A.md"
    assert md["source_root_key"] == "work" and md["rel_path"] == "Projects/contract_A.txt"
    assert md["indexed_text_available"] is True
    _no_abs(md, env["tmp"])
    # a source with no card is still returned as the primary object (never forced into a card)
    md_b = svc.source_file_metadata(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["b"]))
    assert md_b["generated_card_available"] is False and md_b["is_source_file"] is True


def test_metadata_by_source_ref(env) -> None:
    md = svc.source_file_metadata(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]))
    md2 = svc.source_file_metadata(env["repo"], env["config"], source_ref=md["source_ref"])
    assert md2["source_id"] == env["ids"]["a"]


def test_metadata_unknown_raises(env) -> None:
    with pytest.raises(SourceConnectorValidationError) as ei:
        svc.source_file_metadata(env["repo"], env["config"], source_id="0" * 32)
    assert str(ei.value) == "source_not_found"


def test_read_live_bounded(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]), max_chars=10)
    assert r["content_source"] == "live_extract"
    assert r["char_count"] == 10 and len(r["content"]) == 10 and r["truncated"] is True
    _no_abs(r, env["tmp"])


def test_read_indexed_fallback_when_not_live(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]), prefer_live=False)
    assert r["content_source"] == "indexed_excerpt_fallback" and r["reason"] == "indexed_requested"
    assert r["content"] is not None


def test_read_sensitive_root_never_live(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["sensitive"]))
    assert r["content_source"] == "indexed_excerpt_fallback" and r["reason"] == "sensitive_root"


def test_read_denies_unsupported_binary(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["binary"]))
    assert r["denied"] is True and r["content"] is None and r["reason"] == "unsupported_type"


def test_read_path_escape_is_contained(env) -> None:
    r = svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["escape"]))
    # a ``../`` rel_path never yields a live read outside the root — it is rejected by the hidden-segment
    # rule (blocked_path) or the containment guard (path_escape); either way → indexed fallback.
    assert r["content_source"] == "indexed_excerpt_fallback"
    assert r["reason"] in {"blocked_path", "path_escape"}


def test_read_no_directory_traversal(env, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real_scandir = os.scandir
    monkeypatch.setattr(os, "scandir", lambda *a, **k: (calls.append("scandir"), real_scandir(*a, **k))[1])
    monkeypatch.setattr(os, "walk", lambda *a, **k: calls.append("walk") or iter(()))
    svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]), max_chars=50)
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
    svc.source_file_metadata(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]))
    svc.read_source_file(env["repo"], env["config"], source_ref=encode_source_ref(env["ids"]["a"]), max_chars=50)
    assert _snapshot(env["db"]) == before


def test_roots_fall_back_to_index_when_config_empty(tmp_path: Path) -> None:
    # Serve profile carries NO external_sources, but the index has rows keyed by real roots. roots_list /
    # source_status must report those roots (provenance=index) instead of returning zero.
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _insert(db, root_key="hb-onedrive", rel_path="Projects/plan.txt", body="tropical world nursery", ext="txt")
    _insert(db, root_key="syn-work", rel_path="Contracts/a.txt", body="contract terms", ext="txt")
    repo = SourceIndexRepository(db)
    config = ObsidianMcpConfig(external_sources=[])  # empty, like the internet-facing serve profile

    roots = svc.list_source_roots(repo, config)
    keys = {r["source_root_key"] for r in roots["roots"]}
    assert keys == {"hb-onedrive", "syn-work"}
    assert roots["count"] == 2
    assert all(r["provenance"] == "index" for r in roots["roots"])
    assert {r["source_root_key"]: r["file_count"] for r in roots["roots"]} == {"hb-onedrive": 1, "syn-work": 1}

    st = svc.source_status(repo, config)
    assert st["configured_root_count"] == 2  # was 0 before the fix
    _no_abs(roots, str(tmp_path))


def test_status_and_roots_no_abs_paths(env) -> None:
    st = svc.source_status(env["repo"], env["config"])
    assert "configured_roots" not in st and st["index_enabled"] is True
    assert st["configured_root_count"] == 2
    _no_abs(st, env["tmp"])
    roots = svc.list_source_roots(env["repo"], env["config"])
    keys = {r["source_root_key"] for r in roots["roots"]}
    assert keys == {"work", "secure"}
    _no_abs(roots, env["tmp"])
