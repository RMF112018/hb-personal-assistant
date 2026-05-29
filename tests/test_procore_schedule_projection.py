"""Phase 04B schedule-activity enrichment projection tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_schedule_projection import project_activity

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-29T00:00:00Z"

# Critical, zero-float, behind-deadline, hard-constrained activity with a parent,
# an assigned company, a resource and a category.
_ACTIVITY: Dict[str, Any] = {
    "activity_id": "245",
    "activity_name": "Install Windows",
    "schedule_id": "15",
    "parent_id": "418600",
    "percent_complete": 40.0,
    "is_critical": True,
    "total_float": 0,
    "deadline_variance": -3,
    "constraint_type": "MSO",
    "constraint_date": "2026-05-10T08:00:00Z",
    "assigned_company": "ABC Contractors",
    "category_data": [{"name": "Phase_GLOBAL", "value": "Foundation"}],
    "resource_data": [{"resource_id": "101", "resource_name": "Crew 1"}],
}


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _conn(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    return c


def _signals(db: Path) -> set[str]:
    return {r[0] for r in _conn(db).execute("SELECT signal_type FROM procore_action_signals")}


def test_activity_hierarchy_schedule_and_resource_edges() -> None:
    db = _db()
    project_activity(_ACTIVITY, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    edges = {r["edge_type"]: r for r in c.execute("SELECT * FROM procore_record_edges")}
    assert {"in_schedule", "child_of_activity", "assigned_company", "resource", "category"} <= set(edges)
    assert edges["in_schedule"]["to_record_key"] == "tropical|schedules||15"
    assert edges["child_of_activity"]["to_record_key"] == "tropical|activities||418600"
    company = c.execute(
        "SELECT name_redacted FROM procore_company_entities WHERE name_redacted='ABC Contractors'"
    ).fetchone()
    assert company is not None
    res_meta = json.loads(edges["resource"]["metadata_json"])
    assert res_meta["resource_name"] == "Crew 1"


def test_activity_risk_signals_and_classification() -> None:
    db = _db()
    project_activity(_ACTIVITY, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert {"activity_critical", "activity_zero_float", "activity_deadline_variance",
            "activity_constrained"} <= sigs
    # primary signal carries float band + variance class metadata
    row = _conn(db).execute(
        "SELECT metadata_json FROM procore_action_signals WHERE metadata_json IS NOT NULL LIMIT 1"
    ).fetchone()
    meta = json.loads(row["metadata_json"])
    assert meta["float_band"] == "zero_or_negative"
    assert meta["deadline_variance_class"] == "late"


def test_activity_non_risky_emits_no_signal() -> None:
    db = _db()
    calm = {"activity_id": "9", "schedule_id": "15", "is_critical": False, "total_float": 12,
            "deadline_variance": 2, "constraint_type": "ASAP"}
    out = project_activity(calm, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    assert out["projected"] is True
    assert _signals(db) == set()
    # still wires the schedule edge
    edges = {r[0] for r in _conn(db).execute("SELECT edge_type FROM procore_record_edges")}
    assert "in_schedule" in edges


def test_activity_projection_idempotent() -> None:
    db = _db()
    project_activity(_ACTIVITY, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    project_activity(_ACTIVITY, project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db)
    c = _conn(db)
    assert c.execute("SELECT COUNT(*) FROM procore_record_edges WHERE edge_type='resource'").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM procore_action_signals WHERE signal_type='activity_critical'").fetchone()[0] == 1


# --------------------------------------------------------------------------- #
# Schedule snapshot / data-date version history via the generic history path
# --------------------------------------------------------------------------- #


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
        self.calls: List[str] = []

    def __call__(self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]) -> _FakeResponse:
        self.calls.append(method)
        return _FakeResponse(self.payload if len(self.calls) == 1 else {"data": []})


def _schedule_payload(data_date: str) -> dict:
    return {"data": [{
        "schedule_id": "15", "project_id": "12345", "company_id": "5280",
        "schedule_name": "Main Project Schedule", "is_active": True,
        "data_date": data_date, "updated_at": data_date,
    }]}


def test_schedule_snapshot_history_across_data_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    db = _db()

    def _sync(data_date: str) -> None:
        run_live_sync(
            project_key="tropical", endpoint="schedules", apply=True, sqlite_only=True,
            confirm_live_get=True, max_pages=1, max_items=5, db_path=db,
            transport=_FakeTransport(_schedule_payload(data_date)),
        )

    _sync("2026-05-14T00:00:00Z")
    _sync("2026-05-21T00:00:00Z")  # data date advanced -> new schedule version
    c = _conn(db)
    snaps = c.execute(
        "SELECT COUNT(*) FROM procore_live_record_snapshots WHERE endpoint_id='schedules'"
    ).fetchone()[0]
    changes = c.execute(
        "SELECT COUNT(*) FROM procore_live_record_change_events WHERE endpoint_id='schedules'"
    ).fetchone()[0]
    assert snaps >= 2  # one snapshot per data-date version
    assert changes >= 1  # the data-date advance was detected
