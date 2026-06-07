"""P08 targeted test: Graph source status + auth bridge (P05/P06 surfaces).

Exact module name required by validation plan.
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
    db = str(tmp_path / "graph_source.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text, f"forbidden field leaked: {bad}"


def test_graph_source_status_returns_200_and_safe(tmp_path: Any) -> None:
    client = _client(tmp_path)
    r = client.get("/api/sources/graph/status")
    assert r.status_code == 200
    payload = r.json()
    # status slice is safe (no tokens)
    _assert_safe(payload)


def test_graph_source_auth_start_and_status_safe(tmp_path: Any) -> None:
    client = _client(tmp_path)
    # start (operator)
    r = client.post("/api/sources/graph/auth/start", headers={"X-HB-UI-Role": "operator"})
    # may 200 or 4xx depending on config, but response body must be safe
    _assert_safe(r.json() if r.content else {})
    # status poll (no flow -> likely error, but safe)
    r2 = client.get("/api/sources/graph/auth/status?flow_id=nonexistent")
    _assert_safe(r2.json() if r2.content else {})


def test_graph_source_refresh_auth_safe(tmp_path: Any) -> None:
    client = _client(tmp_path)
    r = client.post("/api/sources/graph/auth/refresh", headers={"X-HB-UI-Role": "operator"})
    _assert_safe(r.json() if r.content else {})


def test_additional_proof_no_forbidden_and_only_safe_methods_for_graph(tmp_path: Any) -> None:
    client = _client(tmp_path)
    app = client.app  # type: ignore[attr-defined]
    graph_routes = []
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", "") or ""
        methods = getattr(r, "methods", set()) or set()
        if "/sources/graph" in str(path):
            for m in methods:
                graph_routes.append((m, str(path)))
    for m, _p in graph_routes:
         assert m in {"GET", "POST"}
         assert m not in {"PUT", "PATCH", "DELETE"}
    # hit the endpoints and scan
    for p in ("/api/sources/graph/status",):
        _assert_safe(client.get(p).json())
