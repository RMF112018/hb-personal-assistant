"""Phase 04B date-window capability + daily-log zero-record handling tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


class _FakeResponse:
    def __init__(self, body: Any):
        self._body = body
        self.status_code = 200
        self.headers: Dict[str, str] = {}
        self.text = ""

    def json(self) -> Any:
        return self._body


class _CapturingTransport:
    """Records the params dict of each GET so tests can assert the date window."""

    def __init__(self, body: Any):
        self.body = body
        self.captured_params: List[Optional[Dict[str, Any]]] = []

    def __call__(self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]) -> _FakeResponse:
        self.captured_params.append(params)
        # Return rows only on the first page; empty thereafter to end pagination.
        return _FakeResponse(self.body if len(self.captured_params) == 1 else [])


def _run(endpoint: str, transport: Any, monkeypatch: pytest.MonkeyPatch, **kw: Any) -> Dict[str, Any]:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    return run_live_sync(
        project_key="tropical", endpoint=endpoint, apply=False, sqlite_only=False,
        confirm_live_get=True, max_pages=1, max_items=5, db_path=_db(), transport=transport, **kw,
    )


def test_date_window_passed_as_query_params(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _CapturingTransport([{"id": 1, "date": "2026-03-15", "num_workers": 4, "man_hours": 32}])
    receipt = _run("daily-log-manpower", transport, monkeypatch,
                   start_date="2026-01-01", end_date="2026-05-29")
    assert receipt["state"] == "success"
    params = transport.captured_params[0] or {}
    assert params.get("start_date") == "2026-01-01"
    assert params.get("end_date") == "2026-05-29"


def test_no_date_window_omits_params(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _CapturingTransport([{"id": 1, "date": "2026-03-15"}])
    _run("daily-log-weather", transport, monkeypatch)
    params = transport.captured_params[0] or {}
    assert "start_date" not in params and "end_date" not in params


def test_daily_log_zero_record_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _CapturingTransport([])  # tenant returns no rows for the window
    receipt = _run("daily-log-deliveries", transport, monkeypatch,
                   start_date="2026-01-01", end_date="2026-05-29")
    assert receipt["state"] == "success"
    assert receipt["retrieved_count"] == 0
    assert receipt["normalized_count"] == 0
