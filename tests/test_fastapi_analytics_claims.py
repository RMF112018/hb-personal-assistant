"""N8C-4 — /api/assistant/claims* read-only endpoints (local UI surface).

Claims are exposed read-only on the LOCAL API only; there is no remote MCP claim tool and no
claim-write route. GET-only, all-roles, guardrailed, bounded, no secret leakage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "cache_path", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "raw_backend")


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text


@pytest.fixture()
def client_env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = ClaimRepository(db)
    repo.ingest_candidates(
        [ClaimCandidate("risk", "risk: switchgear may slip", "risk: switchgear may slip", 0.7),
         ClaimCandidate("date", "warranty expires March 4, 2027", "warranty expires March 4, 2027")],
        source_id="s1", note_rel_path="Source Notes/x.md", extractor_version="rule_based-v1")
    return {"client": TestClient(create_app(db_path=db)), "db": db}


def test_list_claims(client_env) -> None:
    r = client_env["client"].get("/api/assistant/claims", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and body["guardrails"]["read_only"] is True
    assert {c["claim_type"] for c in body["claims"]} == {"risk", "date"}
    _assert_safe(body)


def test_list_claims_filtered(client_env) -> None:
    r = client_env["client"].get("/api/assistant/claims", params={"claim_type": "risk"})
    assert r.status_code == 200 and r.json()["count"] == 1


def test_claims_for_source(client_env) -> None:
    r = client_env["client"].get("/api/assistant/sources/s1/claims")
    assert r.status_code == 200
    body = r.json()
    assert body["source_id"] == "s1" and body["count"] == 2


def test_claims_for_card(client_env) -> None:
    r = client_env["client"].get("/api/assistant/cards/claims", params={"note_rel_path": "Source Notes/x.md"})
    assert r.status_code == 200 and r.json()["count"] == 2


def test_all_roles(client_env) -> None:
    for role in ("viewer", "operator", "admin"):
        r = client_env["client"].get("/api/assistant/claims", headers={"X-HB-UI-Role": role})
        assert r.status_code == 200


def test_claim_routes_are_get_only(client_env) -> None:
    app = client_env["client"].app  # type: ignore[attr-defined]
    methods: set[str] = set()
    for route in getattr(app, "routes", []):
        path = str(getattr(route, "path", "") or getattr(route, "path_format", ""))
        if "/assistant" in path and "claim" in path:
            methods |= set(getattr(route, "methods", set()) or set())
    assert methods <= {"GET"}
    assert not (methods & {"POST", "PUT", "PATCH", "DELETE"})
