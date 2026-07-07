"""N8C-12 read-only NAS source-connector API surface: GET-only, bounded, root-aware, redacted, cursor-aware,
no scan/write route."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import source_id_for
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "/Users/", "final_answer", "answer_text")


def _assert_safe(payload: object) -> None:
    blob = json.dumps(payload)
    for needle in FORBIDDEN:
        assert needle not in blob, f"forbidden token leaked: {needle}"


def _seed(db: str, root_key: str, rel_path: str, body: str) -> str:
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,1,?,?,NULL,'t')",
                  (sid, "txt", len(body), hashlib.sha256(body.encode()).hexdigest(), "ok"))
        c.execute("INSERT INTO source_intelligence_text(source_id,text_excerpt,excerpt_char_count,"
                  "excerpt_truncated,raw_body_persisted,redaction_applied,updated_at) "
                  "VALUES(?,?,?,0,0,1,'t')", (sid, body, len(body)))
        rowid = c.execute("INSERT INTO source_intelligence_fts(text_excerpt,rel_path,aux) "
                          "VALUES(?,?,NULL)", (body, rel_path)).lastrowid
        c.execute("UPDATE source_intelligence_metadata SET fts_rowid=? WHERE source_id=?", (rowid, sid))
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.commit()
    return sid


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work / "Projects").mkdir(parents=True)
    (work / "Projects" / "contract_A.txt").write_text("payment application for the contract")
    (work / "Projects" / "invoice_B.txt").write_text("invoice payment due")
    sid_a = _seed(db, "work", "Projects/contract_A.txt", "payment application for the contract")
    _seed(db, "work", "Projects/invoice_B.txt", "invoice payment due")
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work",
                                                                    path=str(work))])
    monkeypatch.setattr("hb_assistant.obsidian_mcp.config.load_config", lambda: config)
    return TestClient(create_app(db_path=db)), sid_a, str(tmp_path)


def test_routes_ok_and_safe(client) -> None:
    c, sid, tmp = client
    for path in ("/api/assistant/source-index/status",
                 "/api/assistant/source-roots",
                 "/api/assistant/source-files/search?query=payment",
                 "/api/assistant/source-files?source_root_key=work",
                 f"/api/assistant/source-files/{sid}",
                 f"/api/assistant/source-files/{sid}/read?max_chars=50"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)
        assert tmp not in json.dumps(body)


def test_search_is_root_aware(client) -> None:
    c, _sid, _tmp = client
    body = c.get("/api/assistant/source-files/search?query=payment",
                 headers={"X-HB-UI-Role": "viewer"}).json()
    assert body["count"] >= 2
    assert all("source_root_key" in i and "source_ref" in i for i in body["items"])


def test_search_cursor_round_trips(client) -> None:
    c, _sid, _tmp = client
    p1 = c.get("/api/assistant/source-files/search?query=payment&limit=1").json()
    assert p1["has_more"] and p1["next_cursor"]
    import urllib.parse
    cur = urllib.parse.quote(p1["next_cursor"], safe="")
    p2 = c.get(f"/api/assistant/source-files/search?query=payment&limit=1&cursor={cur}").json()
    assert p2["items"][0]["source_id"] != p1["items"][0]["source_id"]


def test_metadata_and_read(client) -> None:
    c, sid, _tmp = client
    md = c.get(f"/api/assistant/source-files/{sid}", headers={"X-HB-UI-Role": "viewer"}).json()
    assert md["object_type"] == "source_file" and md["source_root_key"] == "work"
    rd = c.get(f"/api/assistant/source-files/{sid}/read?max_chars=10").json()
    assert rd["char_count"] <= 10 and rd["content_source"] in {"live_extract",
                                                               "indexed_excerpt_fallback"}


def test_missing_returns_404(client) -> None:
    c, _sid, _tmp = client
    assert c.get(f"/api/assistant/source-files/{'0' * 32}").status_code == 404
    assert c.get(f"/api/assistant/source-files/{'0' * 32}/read").status_code == 404


def test_bad_cursor_is_400(client) -> None:
    c, _sid, _tmp = client
    assert c.get("/api/assistant/source-files/search?query=x&cursor=not-a-cursor").status_code == 400


def test_all_roles_allowed(client) -> None:
    c, _sid, _tmp = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/source-roots",
                     headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _sid, _tmp = client
    surface = {
        "/api/assistant/source-index/status",
        "/api/assistant/source-roots",
        "/api/assistant/source-files/search",
        "/api/assistant/source-files",
        "/api/assistant/source-files/{source_id}",
        "/api/assistant/source-files/{source_id}/read",
    }
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_or_scan_route(client) -> None:
    c, sid, _tmp = client
    assert c.post("/api/assistant/source-files").status_code in {401, 404, 405}
    assert c.post(f"/api/assistant/source-files/{sid}/read").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/source-files").status_code in {401, 404, 405}


def test_bounded_limit_is_clamped(client) -> None:
    c, _sid, _tmp = client
    r = c.get("/api/assistant/source-files/search?query=payment&limit=100000",
              headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200 and r.json()["limit"] <= 100
