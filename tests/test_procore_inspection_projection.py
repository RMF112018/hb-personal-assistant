"""Phase 04B inspection enrichment projection tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_inspection_projection import (
    project_inspection_item,
    project_inspection_record,
    project_inspection_section,
)

_NOW = "2026-05-29T00:00:00Z"


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


_INSPECTION = {
    "id": 777,
    "identifier": "INS-1",
    "number": 1,
    "name": "Jobsite Safety Checklist",
    "status": "Open",
    "private": True,
    "overdue": False,
    "closed_at": None,
    "respondable_item_count": 32,
    "inspected_item_count": 0,
    "deficient_item_count": 2,
    "observations_count": 0,
    "item_count": 32,
    "inspection_type": {"id": 5, "name": "Safety"},
    "list_template_id": 9,
    "list_template_name": "Safety List",
    "created_by": {"id": 160586, "login": "synthetic-carl@example.test", "name": "Synthetic Carl"},
    "inspectors": [{"id": 1, "login": "synthetic-insp@example.test", "name": "Inspector One"}],
    "responsible_contractor": {"id": 161072, "name": "Synthetic Contractor"},
    "created_at": "2026-05-01T00:00:00Z",
    "updated_at": "2026-05-02T00:00:00Z",
}

_RESPONSE_SET = {
    "id": 50,
    "name": "Pass/Fail",
    "active": True,
    "procore_standard": True,
    "updated_at": _NOW,
    "responses": [
        {"id": 1, "name": "Pass", "item_status_id": 1, "status": "conforming"},
        {"id": 2, "name": "Fail", "item_status_id": 2, "status": "deficient"},
        {"id": 3, "name": "No Response", "item_status_id": 3, "status": ""},
    ],
}


def _item(responded_with: str) -> dict:
    return {
        "id": 1251207033,
        "name": "Fall Exposures",
        "number": "1.1",
        "list_id": 777,
        "section_id": 10,
        "status": "not_started",
        "responded_with": responded_with,
        "parent_item_id": None,
        "template_item_id": 3,
        "position": 1,
        "relative_position": 1,
        "updated_at": _NOW,
        "response_set": _RESPONSE_SET,
        "evidence_configuration": {
            "item_id": 1251207033,
            "observation": {"response_option_ids": [2], "status_ids": []},
            "photo": {"response_option_ids": [2], "status_ids": []},
        },
        "item_reference_ids": [],
    }


# --------------------------------------------------------------------------- #
# parent
# --------------------------------------------------------------------------- #


def test_inspection_record_projection_and_signals() -> None:
    db = _db()
    project_inspection_record(
        _INSPECTION, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    row = _conn(db).execute("SELECT * FROM procore_inspection_records").fetchone()
    assert row["name_redacted"] == "Jobsite Safety Checklist"
    assert row["is_safety"] == 1 and row["private"] == 1 and row["status"] == "Open"
    assert row["respondable_item_count"] == 32 and row["inspected_item_count"] == 0
    sigs = _signals(db)
    assert {
        "inspection_open_safety",
        "inspection_has_deficient_items",
        "inspection_has_unanswered_items",
    } <= sigs
    # inspector + created_by hashed; raw login absent
    people = _conn(db).execute("SELECT * FROM procore_people_entities").fetchall()
    assert len(people) == 2
    blob = "|".join(str(c) for r in people for c in r)
    assert "synthetic-carl@example.test" not in blob and "Synthetic Carl" not in blob
    edges = {r[0] for r in _conn(db).execute("SELECT edge_type FROM procore_record_edges")}
    assert {"inspector", "created_by", "responsible_contractor"} <= edges


# --------------------------------------------------------------------------- #
# section
# --------------------------------------------------------------------------- #


def test_section_risk_categorization() -> None:
    db = _db()
    project_inspection_section(
        {
            "id": 10,
            "name": "Areas of Highest Risk",
            "position": 1,
            "template_section_id": 99,
            "updated_at": _NOW,
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = (
        _conn(db)
        .execute("SELECT name_redacted, risk_category FROM procore_inspection_sections")
        .fetchone()
    )
    assert row["name_redacted"] == "Areas of Highest Risk"
    assert row["risk_category"] == "high"


def test_section_low_risk_categorization() -> None:
    db = _db()
    project_inspection_section(
        {"id": 11, "name": "General Housekeeping", "position": 2, "updated_at": _NOW},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = (
        _conn(db)
        .execute("SELECT risk_category FROM procore_inspection_sections WHERE section_id='11'")
        .fetchone()
    )
    assert row["risk_category"] == "general"


# --------------------------------------------------------------------------- #
# item + response set/options + evidence rules
# --------------------------------------------------------------------------- #


def test_item_no_response_projection_and_signal() -> None:
    db = _db()
    out = project_inspection_item(
        _item("No Response"), project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    assert out["interpretation"]["is_unanswered"] is True
    row = _conn(db).execute("SELECT * FROM procore_inspection_items").fetchone()
    assert row["item_number"] == "1.1" and row["item_name_redacted"] == "Fall Exposures"
    assert row["is_unanswered"] == 1 and row["response_status"] == "no_response"
    assert "inspection_item_unanswered" in _signals(db)


def test_item_fail_is_deficient_and_non_conforming() -> None:
    db = _db()
    project_inspection_item(
        _item("Fail"), project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    row = (
        _conn(db)
        .execute(
            "SELECT is_deficient, is_conforming, response_status FROM procore_inspection_items"
        )
        .fetchone()
    )
    assert (
        row["is_deficient"] == 1
        and row["is_conforming"] == 0
        and row["response_status"] == "deficient"
    )
    sigs = _signals(db)
    assert {"inspection_item_failed", "inspection_item_non_conforming"} <= sigs


def test_item_pass_is_conforming() -> None:
    db = _db()
    project_inspection_item(
        _item("Pass"), project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    row = (
        _conn(db)
        .execute("SELECT is_conforming, is_unanswered FROM procore_inspection_items")
        .fetchone()
    )
    assert row["is_conforming"] == 1 and row["is_unanswered"] == 0


def test_response_set_and_options_projection() -> None:
    db = _db()
    project_inspection_item(
        _item("No Response"), project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    sets = _conn(db).execute("SELECT * FROM procore_inspection_response_sets").fetchall()
    opts = (
        _conn(db)
        .execute(
            "SELECT name_redacted, status_category FROM procore_inspection_response_options ORDER BY response_option_id"
        )
        .fetchall()
    )
    assert len(sets) == 1 and sets[0]["name_redacted"] == "Pass/Fail"
    assert {(o["name_redacted"], o["status_category"]) for o in opts} == {
        ("Pass", "conforming"),
        ("Fail", "deficient"),
        ("No Response", ""),
    }


def test_evidence_rules_projection_and_signals() -> None:
    db = _db()
    project_inspection_item(
        _item("No Response"), project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    row = (
        _conn(db)
        .execute(
            "SELECT requires_observation, requires_photo, photo_response_option_ids_json FROM procore_inspection_evidence_rules"
        )
        .fetchone()
    )
    assert row["requires_observation"] == 1 and row["requires_photo"] == 1
    assert "2" in (row["photo_response_option_ids_json"] or "")
    sigs = _signals(db)
    assert {
        "inspection_item_requires_photo_evidence",
        "inspection_item_requires_observation",
    } <= sigs


def test_projection_is_idempotent() -> None:
    db = _db()
    project_inspection_item(
        _item("No Response"), project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    project_inspection_item(
        _item("No Response"), project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db
    )
    assert _conn(db).execute("SELECT COUNT(*) FROM procore_inspection_items").fetchone()[0] == 1
    assert (
        _conn(db).execute("SELECT COUNT(*) FROM procore_inspection_response_options").fetchone()[0]
        == 3
    )


# --------------------------------------------------------------------------- #
# history event when item response changes (sync-flow integration)
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

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append(method)
        return _FakeResponse(self.payload if len(self.calls) == 1 else [])


@pytest.mark.usefixtures("isolated_hb_pa_config")
def test_item_response_change_records_history_and_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    db = _db()

    def _sync(responded_with: str) -> None:
        run_live_sync(
            project_key="tropical",
            endpoint="inspection-items",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            max_pages=1,
            max_items=5,
            db_path=db,
            transport=_FakeTransport([_item(responded_with)]),
        )

    _sync("Pass")
    _sync("Fail")  # response changed
    c = _conn(db)
    # projection reflects the latest response
    item = c.execute("SELECT is_deficient FROM procore_inspection_items").fetchone()
    assert item["is_deficient"] == 1
    # history recorded the response change
    cats = {
        r[0]
        for r in c.execute(
            "SELECT change_category FROM procore_live_record_change_events WHERE endpoint_id='inspection-items'"
        )
    }
    assert "inspection_item_response_changed" in cats
