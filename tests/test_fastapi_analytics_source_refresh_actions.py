"""P08 targeted test: source refresh actions (dry/local/live) + scheduler + security proofs.

Exact module name required by validation plan for `pytest tests/test_fastapi_analytics_source_refresh_actions.py`.
"""

from __future__ import annotations

from typing import Any

import pytest
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


def _client(tmp_path: Any) -> tuple[TestClient, str]:
    db = str(tmp_path / "source_refresh_actions.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db)), db


def _assert_safe(payload: Any) -> None:
    text = str(payload)
    for bad in FORBIDDEN:
        assert bad not in text, f"forbidden field leaked: {bad}"


def _raise_if_built(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a live data client must not be constructed by this refresh mode")
    monkeypatch.setattr("hb_assistant.graph.http_client.GraphHttpClient", _boom)
    monkeypatch.setattr("hb_assistant.procore.http_client.ProcoreHTTPClient", _boom)


def test_dry_run_and_local_are_safe_and_do_not_call_live(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _raise_if_built(monkeypatch)
    client, _ = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}
    for ep in ("/api/sources/refresh/dry-run", "/api/sources/refresh/local"):
        r = client.post(ep, headers=headers)
        assert r.status_code == 200
        _assert_safe(r.json())


def test_live_refresh_fails_closed_without_confirm_and_env(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_PROCORE_LIVE", raising=False)
    _raise_if_built(monkeypatch)
    client, _ = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}
    # even with confirm, in non-prod + no live flag it should be blocked or safe
    for body in ({"confirm": True}, {"confirm": False}, {}):
        r = client.post("/api/sources/refresh/live", headers=headers, json=body)
        # either 200 (receipt with reason) or 4xx; body safe either way
        _assert_safe(r.json() if r.content else {})


def test_scheduler_status_is_safe(tmp_path: Any) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/api/scheduler/daily-source-refresh/status", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    _assert_safe(r.json())


def test_additional_proof_route_exposure_no_writeback_and_body_scans(tmp_path: Any) -> None:
    client, _ = _client(tmp_path)
    app = client.app  # type: ignore[attr-defined]
    refresh_routes = []
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", "") or ""
        methods = getattr(r, "methods", set()) or set()
        if "/sources/refresh" in str(path) or "/sources/" in str(path) and "auth" in str(path):
            for m in methods:
                refresh_routes.append((m, str(path)))
    # no writeback verbs
    for m, _p in refresh_routes:
         assert m not in {"PUT", "PATCH", "DELETE"}
    # exercise and scan bodies
    headers = {"X-HB-UI-Role": "operator"}
    for ep in ("/api/sources/refresh/dry-run", "/api/sources/refresh/local"):
        r = client.post(ep, headers=headers)
        _assert_safe(r.json() if r.content else {})
    _assert_safe(client.get("/api/scheduler/daily-source-refresh/status").json())
