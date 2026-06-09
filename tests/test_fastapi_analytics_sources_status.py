"""P08 targeted test: /api/sources/status and /api/environment coverage + security proofs.

Exact module name required by validation plan for `pytest tests/test_fastapi_analytics_sources_status.py`.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "access_token",
    "refresh_token",
    "client_secret",
    "cache_path",
    "Bearer ",
    "eyJ",
    "BEGIN PRIVATE KEY",
    "raw_backend",
)


def _client(tmp_path: Any) -> TestClient:
    db = str(tmp_path / "sources_status.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text, f"forbidden field leaked: {bad}"


def test_sources_status_returns_200_with_summaries(tmp_path: Any) -> None:
    client = _client(tmp_path)
    response = client.get("/api/sources/status")
    assert response.status_code == 200
    payload = response.json()
    assert "environment" in payload or "source_refresh_mode" in payload
    _assert_safe(payload)


def test_environment_and_sources_status_safe_and_have_live_flags(tmp_path: Any) -> None:
    client = _client(tmp_path)
    env = client.get("/api/environment").json()
    src = client.get("/api/sources/status").json()
    assert "source_refresh_mode" in env
    assert "live_refresh" in env or "live_reads" in env
    _assert_safe(env)
    _assert_safe(src)


def test_sources_status_all_roles_accessible(tmp_path: Any) -> None:
    client = _client(tmp_path)
    for role in ("viewer", "operator", "admin"):
        r = client.get("/api/sources/status", headers={"X-HB-UI-Role": role})
        assert r.status_code == 200
        _assert_safe(r.json())


def test_additional_proof_route_exposure_and_no_writeback_under_sources(tmp_path: Any) -> None:
    client = _client(tmp_path)
    app = client.app  # type: ignore[attr-defined]
    sources_routes = []
    env_routes = []
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", "") or getattr(r, "path_format", "")
        methods = getattr(r, "methods", set()) or set()
        if "/sources" in str(path):
            for m in methods:
                sources_routes.append((m, str(path)))
        if "/environment" in str(path):
            for m in methods:
                env_routes.append((m, str(path)))
    # Only documented safe methods
    for m, p in sources_routes:
        if any(p.endswith(a) or a in p for a in ("/status", "/auth/", "/refresh/")):
            assert m in {"GET", "POST"}, f"unexpected method on sources: {m} {p}"
    # No writeback (no PUT/PATCH/DELETE under sources)
    for m, p in sources_routes:
        assert m not in {"PUT", "PATCH", "DELETE"}, f"writeback route exposed: {m} {p}"
    _assert_safe({"routes": sources_routes + env_routes})


def test_additional_proof_no_forbidden_in_any_sources_responses(tmp_path: Any) -> None:
    client = _client(tmp_path)
    for path in ("/api/environment", "/api/sources/status", "/api/sources/graph/status", "/api/sources/procore/status"):
        r = client.get(path)
        assert r.status_code == 200
        _assert_safe(r.json())
