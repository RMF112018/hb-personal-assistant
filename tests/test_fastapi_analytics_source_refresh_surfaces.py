"""P04 — source-refresh + scheduler/daily-brief status surface tests.

Proves: dry-run does not write the DB, local/mock never constructs a live client, live fails closed
unless env+config+confirm permit, receipts carry no raw payloads, and the scheduler status surface is
safe. Mirrors the analytics FastAPI test harness.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "Bearer ",
    "BEGIN PRIVATE KEY",
    "eyJ",
    '"access_token":',
    '"refresh_token":',
    '"client_secret":',
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
)


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    db = str(tmp_path / "source-refresh.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db)), db


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized, f"forbidden marker leaked: {marker}"


def _row_fingerprint(db: str) -> dict[str, int]:
    """Row count per user table — used to prove dry-run writes nothing."""
    conn = sqlite3.connect(db)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        counts: dict[str, int] = {}
        for t in tables:
            counts[t] = int(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
        return counts
    finally:
        conn.close()


def _raise_if_built(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the live Graph/Procore data clients explode if anything tries to construct them."""

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a live data client must not be constructed by this refresh mode")

    monkeypatch.setattr("hb_assistant.graph.http_client.GraphHttpClient", _boom)
    monkeypatch.setattr("hb_assistant.procore.http_client.ProcoreHTTPClient", _boom)


def test_dry_run_does_not_write_db(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    before = _row_fingerprint(db)

    r = client.post("/api/sources/refresh/dry-run", headers={"X-HB-UI-Role": "operator"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["dry_run"] is True
    assert payload["sqlite_upsert_summary"]["total"]["inserted"] == 0
    assert payload["sqlite_upsert_summary"]["total"]["updated"] == 0
    _assert_safe(payload)

    after = _row_fingerprint(db)
    assert before == after, "dry-run must not mutate the database"


def test_local_refresh_never_calls_live_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _raise_if_built(monkeypatch)
    client, _ = _client(tmp_path)

    r = client.post("/api/sources/refresh/local", headers={"X-HB-UI-Role": "operator"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["live_reads_enabled"] is False
    assert payload["live_mode"] == "local_only"
    assert payload["mock_data"] is True
    _assert_safe(payload)


def test_live_refresh_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_PROCORE_LIVE", raising=False)
    _raise_if_built(monkeypatch)
    client, _ = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}

    for body in ({"confirm": True}, {"confirm": False}):
        r = client.post("/api/sources/refresh/live", headers=headers, json=body)
        assert r.status_code == 200
        payload = r.json()
        assert payload["status"] == "blocked"
        assert payload["live_read_performed"] is False
        _assert_safe(payload)


def test_scheduler_status_is_safe(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/api/scheduler/daily-source-refresh/status", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.scheduler.daily_source_refresh.status"
    assert "schedule_time_local" in payload
    assert "timezone" in payload
    assert "next_expected_run" in payload
    assert "live_reads_enabled" in payload
    assert payload["guardrails"]["read_only"] is True
    _assert_safe(payload)


def test_daily_brief_status_reused(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/api/daily-brief/status", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    _assert_safe(r.json())


def test_role_gating(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    viewer = {"X-HB-UI-Role": "viewer"}

    assert client.post("/api/sources/refresh/dry-run", headers=viewer).status_code == 403
    assert client.post("/api/sources/refresh/local", headers=viewer).status_code == 403
    assert (
        client.post(
            "/api/sources/refresh/live", headers=viewer, json={"confirm": False}
        ).status_code
        == 403
    )
    # status is viewer-safe
    assert (
        client.get("/api/scheduler/daily-source-refresh/status", headers=viewer).status_code == 200
    )
