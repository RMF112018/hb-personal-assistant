"""Phase 04B punch-item workflow enrichment projection tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from hb_assistant.security.text_vault import decrypt_text
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_punch_projection import project_punch_item

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-29T00:00:00Z"

# Open punch item, overdue, unresolved response, an assignment notified but not
# responded (waiting), with vendor + login + comment + attachment (signed URL).
_PUNCH: Dict[str, Any] = {
    "id": 83978,
    "name": "Seal penetration at electrical closet",
    "status": "Open",
    "workflow_status": "initiated",
    "due_date": "2026-05-20",  # before _NOW -> overdue
    "closed_at": None,
    "has_resolved_responses": False,
    "has_unresolved_responses": True,
    "cost_impact": "yes_known",
    "cost_impact_amount": "100.0",
    "schedule_impact": "yes_known",
    "schedule_impact_days": 3,
    "schedule_risk": "ml_high",
    "description": "Fire-rated sealant missing around conduit penetration.",
    "schedule_risk_reason": "Blocks inspection sign-off; delays close-out.",
    "location": {
        "id": 15504,
        "name": "North Building>First Floor>Electrical Closet",
        "code": "L1",
        "parent_id": 788866,
    },
    "trade": {"id": 999, "name": "09 - acoustical panels", "active": True},
    "ball_in_court": [{"id": 1738090, "name": "John Doe", "locale": "ko"}],
    "created_by": {"id": 1738090, "name": "John Doe", "company_name": "Brickworks"},
    "assignees": [
        {"id": 160586, "login": "carl.contractor@example.com", "name": "Carl Contractor"}
    ],
    "assignments": [
        {
            "id": 333675,
            "approved": False,
            "status": "unresolved",
            "login_information": {
                "id": 160586,
                "login": "carl.contractor@example.com",
                "name": "Carl Contractor",
            },
            "vendor": {"id": 161072, "name": "SID Architecture"},
            "attachments": [
                {"id": 5324, "url": "https://example.test/f/abc?token=secret", "filename": "x.jpg"}
            ],
            "comment": "Need RFI 12 answered before repair; coordinate with electrician.",
            "notified_at": "2026-05-25T22:22:42Z",
            "responded_at": None,
            "manager_accepted_at": None,
        },
    ],
    "custom_fields": {
        "custom_field_decimal_def": {"data_type": "decimal", "value": 2.2},
        "custom_field_string_def": {"data_type": "string", "value": "secret custom value"},
    },
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


def test_punch_assignment_graph_hashed() -> None:
    db = _db()
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    people = c.execute("SELECT * FROM procore_people_entities").fetchall()
    pblob = "|".join(str(x) for r in people for x in r)
    assert "carl.contractor@example.com" not in pblob and "Carl Contractor" not in pblob
    edges = {r[0] for r in c.execute("SELECT edge_type FROM procore_record_edges")}
    assert {"assignee", "vendor", "at_location", "trade", "ball_in_court", "created_by"} <= edges
    vendor = c.execute(
        "SELECT name_redacted FROM procore_company_entities WHERE name_redacted='SID Architecture'"
    ).fetchone()
    assert vendor is not None
    # assignment metadata captured on the assignee edge
    meta_rows = [
        json.loads(r["metadata_json"])
        for r in c.execute(
            "SELECT metadata_json FROM procore_record_edges WHERE edge_type='assignee'"
        )
        if r["metadata_json"]
    ]
    assert any(m.get("status") == "unresolved" and m.get("notified_at") for m in meta_rows)


def test_punch_location_hierarchy_edge() -> None:
    db = _db()
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    loc = _conn(db).execute("SELECT * FROM procore_location_entities").fetchone()
    assert loc is not None and loc["parent_location_id"] == "788866"


def test_punch_unresolved_and_overdue_and_waiting_signals() -> None:
    db = _db()
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert {"punch_overdue", "punch_unresolved_response", "punch_assignment_waiting"} <= sigs


def test_punch_due_tomorrow_signal() -> None:
    db = _db()
    near = {
        **_PUNCH,
        "due_date": "2026-05-30",
        "has_unresolved_responses": False,
        "assignments": [],
    }
    project_punch_item(near, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert "punch_due_tomorrow" in sigs
    assert "punch_overdue" not in sigs


def test_punch_attachment_path_only_and_text_intelligence() -> None:
    db = _db()
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    att = c.execute("SELECT * FROM procore_attachment_refs").fetchone()
    blob = "|".join("" if v is None else str(v) for v in att)
    assert "?" not in blob and "token=secret" not in blob and att["url_path_redacted"] == "/f/abc"
    risk = c.execute(
        "SELECT * FROM procore_text_intelligence WHERE source_field_path='schedule_risk_reason'"
    ).fetchone()
    assert (
        risk is not None
        and decrypt_text(risk["encrypted_full_text_ref"]) == _PUNCH["schedule_risk_reason"]
    )
    desc = c.execute(
        "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='description'"
    ).fetchone()[0]
    assert desc == 1


def test_punch_custom_fields_string_hashed() -> None:
    db = _db()
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    rows = _conn(db).execute("SELECT * FROM procore_custom_field_values").fetchall()
    blob = "|".join("" if v is None else str(v) for r in rows for v in r)
    assert "secret custom value" not in blob


def test_punch_projection_idempotent() -> None:
    db = _db()
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    project_punch_item(_PUNCH, project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db)
    c = _conn(db)
    assert c.execute("SELECT COUNT(*) FROM procore_attachment_refs").fetchone()[0] == 1
    assert (
        c.execute(
            "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='schedule_risk_reason'"
        ).fetchone()[0]
        == 1
    )
