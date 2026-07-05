"""N8C-3 — /api/assistant/* read-only navigation endpoints (LOCAL UI surface).

API-side safety proof ONLY (kept separate from the MCP safety proof): every endpoint is GET,
all-roles, read-only; responses carry the ``guardrails`` block and leak no secrets; bad input is a
clean 404/400; there is NO PUT/PATCH/DELETE anywhere under ``/api/assistant``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "cache_path", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "raw_backend")
REL_A = "docs/alpha.txt"


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text, f"forbidden field leaked: {bad}"


@pytest.fixture()
def client_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    repo = SourceIndexRepository(db)
    (root / "docs").mkdir(parents=True)
    (root / REL_A).write_text("alpha content findme_yyy", encoding="utf-8")
    sid = index_source_file(root / REL_A, config.external_sources[0], repo, config)
    card = generate_source_card(repo, config, source_id=sid)["note_path"]
    return {"client": TestClient(create_app(db_path=db)), "sid": sid, "card": card, "root": str(root)}


ALL_ENDPOINTS = [
    "/api/assistant/sources?q=findme_yyy",
    "/api/assistant/cards/search?q=alpha",
    "/api/assistant/cards/stale",
    "/api/assistant/cards/duplicates",
    "/api/assistant/cards/ambiguous",
    "/api/assistant/recent-changes",
]


def test_all_list_endpoints_200_guardrails_safe(client_env) -> None:
    client = client_env["client"]
    for path in ALL_ENDPOINTS:
        r = client.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        assert {"count", "limit", "truncated"} <= set(body)
        _assert_safe(body)


def test_source_detail_and_linkage(client_env) -> None:
    client, sid, card = client_env["client"], client_env["sid"], client_env["card"]
    r = client.get(f"/api/assistant/sources/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["source"]["rel_path"] == REL_A
    assert body["card"]["note_rel_path"] == card
    assert client_env["root"] not in str(body)     # no absolute source-root path leaks
    for suffix in ("/card", "/state", "/related"):
        rr = client.get(f"/api/assistant/sources/{sid}{suffix}")
        assert rr.status_code == 200
        assert rr.json()["guardrails"]["read_only"] is True


def test_card_source_reverse_lookup(client_env) -> None:
    r = client_env["client"].get("/api/assistant/card-source",
                                 params={"note_rel_path": client_env["card"]})
    assert r.status_code == 200
    assert r.json()["resolution"] in {"unique", "ambiguous", "none"}


def test_vault_note_complete_content(client_env) -> None:
    r = client_env["client"].get("/api/assistant/vault-note",
                                 params={"note_rel_path": client_env["card"]})
    assert r.status_code == 200
    body = r.json()
    assert body["file_type"] == "md" and body["content"]
    assert body["metadata"]["truncated"] is False


def test_missing_source_404(client_env) -> None:
    r = client_env["client"].get("/api/assistant/sources/deadbeefdeadbeefdeadbeefdeadbeef")
    assert r.status_code == 404


def test_vault_note_traversal_400(client_env) -> None:
    for bad in ["../etc/passwd", "/etc/passwd", ".obsidian/app.json"]:
        r = client_env["client"].get("/api/assistant/vault-note", params={"note_rel_path": bad})
        assert r.status_code == 400, bad


def test_all_roles_accessible(client_env) -> None:
    client = client_env["client"]
    for role in ("viewer", "operator", "admin"):
        r = client.get("/api/assistant/recent-changes", headers={"X-HB-UI-Role": role})
        assert r.status_code == 200
        _assert_safe(r.json())


def test_route_shape_get_only_no_writeback(client_env) -> None:
    app = client_env["client"].app  # type: ignore[attr-defined]
    methods: set[str] = set()
    count = 0
    for route in getattr(app, "routes", []):
        path = str(getattr(route, "path", "") or getattr(route, "path_format", ""))
        if path.startswith("/api/assistant"):
            count += 1
            methods |= set(getattr(route, "methods", set()) or set())
    assert count >= 12
    assert methods <= {"GET"}, f"non-GET method under /api/assistant: {methods}"
    assert not (methods & {"POST", "PUT", "PATCH", "DELETE"})
