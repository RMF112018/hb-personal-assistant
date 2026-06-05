"""Phase 04B history recording wired into the live-sync flow (fake transport).

Proves the orchestrator records snapshots / change events / timeline events
alongside the unchanged latest-state upsert, and that re-syncing identical data
is idempotent (no duplicate history).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_history import get_procore_changes, get_procore_record_history
from hb_assistant.store.procore_repositories import count_procore_live_records

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_RECORD_KEY = "tropical|rfis||101"


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


class _FakeTransport:
    def __init__(self, payload: Any):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append({"method": method})
        return _FakeResponse(self.payload if len(self.calls) == 1 else [])


def _setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")


def _rfi(
    status: str, *, due: str = "2026-01-10", updated: str = "2026-01-01T00:00:00Z"
) -> list[dict]:
    return [
        {
            "id": 101,
            "number": "RFI-001",
            "subject": "Door schedule clarification",
            "status": status,
            "due_date": due,
            "assignee_id": 42,
            "updated_at": updated,
        }
    ]


def _sync(db: Path, payload: list[dict]) -> None:
    run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=5,
        db_path=db,
        transport=_FakeTransport(payload),
    )


def _count(db: Path, table: str, **where: str) -> int:
    conn = sqlite3.connect(str(db))
    try:
        if where:
            clause = " AND ".join(f"{k} = ?" for k in where)
            return conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {clause}", tuple(where.values())
            ).fetchone()[0]
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_first_sync_records_state_snapshot_and_created_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    _sync(db, _rfi("open"))
    assert _count(db, "procore_live_record_state_index", record_key=_RECORD_KEY) == 1
    assert _count(db, "procore_live_record_snapshots", record_key=_RECORD_KEY) == 1
    assert (
        _count(
            db,
            "procore_live_record_change_events",
            record_key=_RECORD_KEY,
            change_category="record_created",
        )
        == 1
    )
    # latest-state row also written (unchanged Phase 04A behavior)
    assert count_procore_live_records(project_key="tropical", endpoint_id="rfis", db_path=db) == 1


def test_unchanged_resync_adds_no_duplicate_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    _sync(db, _rfi("open"))
    _sync(db, _rfi("open"))  # identical
    assert _count(db, "procore_live_record_snapshots", record_key=_RECORD_KEY) == 1
    assert (
        _count(db, "procore_live_record_change_events", record_key=_RECORD_KEY) == 1
    )  # only record_created
    # latest-state upsert remains idempotent (still one row)
    assert count_procore_live_records(project_key="tropical", endpoint_id="rfis", db_path=db) == 1


def test_changed_resync_records_snapshot_change_and_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _db()
    _sync(db, _rfi("open"))
    _sync(db, _rfi("closed", updated="2026-02-01T00:00:00Z"))  # status changed
    assert _count(db, "procore_live_record_snapshots", record_key=_RECORD_KEY) == 2
    assert (
        _count(
            db,
            "procore_live_record_change_events",
            record_key=_RECORD_KEY,
            change_category="closed",
        )
        == 1
    )
    assert (
        _count(db, "procore_record_timeline_events", record_key=_RECORD_KEY, event_type="closed")
        == 1
    )
    # still one latest-state row
    assert count_procore_live_records(project_key="tropical", endpoint_id="rfis", db_path=db) == 1


def test_history_reconstruction_from_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    _sync(db, _rfi("open"))
    _sync(db, _rfi("closed", updated="2026-02-01T00:00:00Z"))
    history = get_procore_record_history(record_key=_RECORD_KEY, db_path=db)
    assert len(history) == 2
    assert history[0]["observed_at_utc"] <= history[1]["observed_at_utc"]
    # snapshots carry redacted canonical JSON, never a raw body flag
    assert all(h["canonical_json_redacted"] for h in history)


def test_recent_changes_query(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _db()
    _sync(db, _rfi("open"))
    _sync(db, _rfi("closed", updated="2026-02-01T00:00:00Z"))
    changes = get_procore_changes(
        project_key="tropical", since_utc="2000-01-01T00:00:00Z", db_path=db
    )
    cats = {c["change_category"] for c in changes}
    assert "record_created" in cats
    assert "closed" in cats
    # filtering by a future window returns nothing
    assert (
        get_procore_changes(project_key="tropical", since_utc="2999-01-01T00:00:00Z", db_path=db)
        == []
    )
