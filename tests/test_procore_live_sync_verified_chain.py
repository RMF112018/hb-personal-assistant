"""Phase 04A verified endpoint live chain end-to-end (fake transport)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_repositories import count_procore_live_records

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


class _FakeResponse:
    def __init__(self, body: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None):
        self._json_body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""

    def json(self) -> Any:
        return self._json_body


class _FakeTransport:
    """Records every call and returns a fixed JSON body."""

    def __init__(self, payload: List[Dict[str, Any]]):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
    ) -> _FakeResponse:
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "params": dict(params or {})}
        )
        # Return all items on the first call, empty on subsequent (pagination halts).
        if len(self.calls) == 1:
            return _FakeResponse(self.payload)
        return _FakeResponse([])


_RFI_PAYLOAD = [
    {
        "id": 101,
        "number": "RFI-001",
        "subject": "Door schedule clarification",
        "status": "open",
        "updated_at": "2026-01-01T00:00:00Z",
        "assignee_id": 42,
    },
    {
        "id": 102,
        "number": "RFI-002",
        "subject": "Claim impact - delay review",  # triggers review_required
        "status": "open",
        "updated_at": "2026-01-02T00:00:00Z",
        "assignee_id": 43,
    },
]


def _setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")


def test_verified_rfis_endpoint_runs_full_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)

    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=3,
        max_items=100,
        db_path=db,
        transport=transport,
    )

    assert receipt["state"] == "success"
    assert receipt["status"] == "success"
    assert receipt["retrieved_count"] == 2
    assert receipt["normalized_count"] == 2
    assert receipt["sqlite_upserted_count"] == 2
    assert receipt["sqlite_total_count_after"] == 2
    assert receipt["raw_body_persisted"] is False
    assert receipt["secrets_redacted"] is True
    assert receipt["http_method"] == "GET"
    assert receipt["endpoint_id"] == "rfis"
    assert receipt["legacy_endpoint_alias"] == "list-rfis"
    assert receipt["procore_project_id"] == "2525840"


def test_transport_receives_bearer_access_token_not_client_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "MUST_NEVER_APPEAR_IN_AUTH_HEADER")
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    assert transport.calls, "transport must be invoked"
    auth = transport.calls[0]["headers"]["Authorization"]
    assert auth == "Bearer synthetic-bearer-token"
    assert "MUST_NEVER_APPEAR_IN_AUTH_HEADER" not in auth
    assert transport.calls[0]["method"] == "GET"


def test_only_get_method_observed_by_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    for call in transport.calls:
        assert call["method"] == "GET"


def test_verified_chain_is_idempotent_across_re_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()

    def _go() -> Dict[str, Any]:
        return run_live_sync(
            project_key="tropical",
            endpoint="rfis",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            db_path=db,
            transport=_FakeTransport(_RFI_PAYLOAD),
        )

    first = _go()
    second = _go()
    assert first["sqlite_upserted_count"] == 2
    assert second["sqlite_upserted_count"] == 2  # upsert, not duplicate insert
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 2


def test_smoke_mode_does_not_write_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=False,
        sqlite_only=False,
        confirm_live_get=True,
        mode_hint="live_smoke",
        db_path=db,
        transport=transport,
    )
    assert receipt["state"] == "success"
    assert receipt["mode"] == "live_smoke"
    assert receipt["retrieved_count"] == 2
    assert receipt["normalized_count"] == 2
    assert receipt["sqlite_upserted_count"] == 0
    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 0


def test_raw_response_body_never_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT canonical_json_redacted, raw_body_persisted FROM procore_live_records"
        ).fetchall()
    finally:
        conn.close()
    assert rows, "expected at least one persisted row"
    for canonical_json, raw_body_persisted in rows:
        # Body never persisted (constraint enforces 0)
        assert raw_body_persisted == 0
        # Canonical JSON must not include "Bearer" or the synthetic token value
        assert "Bearer" not in canonical_json
        assert "synthetic-bearer-token" not in canonical_json


def test_review_required_flag_set_on_sensitive_rfi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT review_required, sensitive_reason FROM procore_live_records WHERE procore_record_id = '102'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == 1
    assert row[1] is not None and "claim" in row[1].lower()
