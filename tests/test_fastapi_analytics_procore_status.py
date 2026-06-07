"""P08 targeted test: Procore source status + auth bridge (P05/P06 surfaces).

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
    db = str(tmp_path / "procore_source.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text, f"forbidden field leaked: {bad}"


def test_procore_source_status_returns_200_and_safe(tmp_path: Any) -> None:
    client = _client(tmp_path)
    r = client.get("/api/sources/procore/status")
    assert r.status_code == 200
    _assert_safe(r.json())


def test_procore_source_auth_start_status_exchange_safe(tmp_path: Any) -> None:
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}
    r = client.post("/api/sources/procore/auth/start", headers=headers)
    _assert_safe(r.json() if r.content else {})
    r2 = client.get("/api/sources/procore/auth/status?flow_id=nonexistent", headers=headers)
    _assert_safe(r2.json() if r2.content else {})
    # exchange is POST with code; body may be invalid but response safe
    r3 = client.post("/api/sources/procore/auth/exchange-code", headers=headers, json={"code": "dummy"})
    _assert_safe(r3.json() if r3.content else {})


def test_procore_source_refresh_auth_safe(tmp_path: Any) -> None:
    client = _client(tmp_path)
    r = client.post("/api/sources/procore/auth/refresh", headers={"X-HB-UI-Role": "operator"})
    _assert_safe(r.json() if r.content else {})


def test_additional_proof_no_forbidden_and_only_safe_methods_for_procore(tmp_path: Any) -> None:
    client = _client(tmp_path)
    app = client.app  # type: ignore[attr-defined]
    pro_routes = []
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", "") or ""
        methods = getattr(r, "methods", set()) or set()
        if "/sources/procore" in str(path):
            for m in methods:
                pro_routes.append((m, str(path)))
    for m, _p in pro_routes:
         assert m in {"GET", "POST"}
         assert m not in {"PUT", "PATCH", "DELETE"}
    for p in ("/api/sources/procore/status",):
        _assert_safe(client.get(p).json())
