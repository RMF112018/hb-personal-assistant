"""Phase 04B RFI + RFI-response enrichment projection tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.security.text_vault import decrypt_text
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_rfi_projection import project_rfi, project_rfi_response

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-29T00:00:00Z"

_RFI: Dict[str, Any] = {
    "id": 501,
    "number": "RFI-001",
    "subject": "Door schedule",
    "status": "Open",
    "translated_status": "Open",
    "due_date": "2026-02-01",
    "full_number": "RFI-001",
    "cost_impact": {"status": "yes", "value": None},
    "schedule_impact": {"status": "no_impact", "value": None},
    "received_from": {"id": 11, "login": "rf@example.test", "name": "RF Person"},
    "rfi_manager": {"id": 12, "login": "mgr@example.test", "name": "Manager"},
    "responsible_contractor": {"id": 161072, "name": "Synthetic Contractor"},
    "assignees": [{"id": 13, "login": "as@example.test", "name": "Assignee"}],
    "ball_in_court": {"id": 14, "login": "bic@example.test", "name": "BIC"},
    "questions": [{"id": 1, "body": "Please confirm RFI 7 and the schedule delay impact."}],
    "proposed_solution": "Adjust the door schedule per submittal 45.",
    "replies": [
        {
            "id": 9001,
            "plain_text_body": "Official answer: proceed as drawn.",
            "official": True,
            "created_by_id": 77,
            "attachments": [
                {"id": 7, "filename": "a.pdf", "url": "https://example.test/f/abc?token=secret"}
            ],
        }
    ],
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


def test_rfi_people_company_edges_hashed() -> None:
    db = _db()
    project_rfi(_RFI, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    people = c.execute("SELECT * FROM procore_people_entities").fetchall()
    pblob = "|".join(str(x) for r in people for x in r)
    assert "rf@example.test" not in pblob and "RF Person" not in pblob
    edges = {r[0] for r in c.execute("SELECT edge_type FROM procore_record_edges")}
    assert {
        "received_from",
        "rfi_manager",
        "assignee",
        "ball_in_court",
        "responsible_contractor",
    } <= edges
    company = c.execute("SELECT name_redacted FROM procore_company_entities").fetchone()
    assert company["name_redacted"] == "Synthetic Contractor"


def test_rfi_question_text_intelligence_encrypted() -> None:
    db = _db()
    project_rfi(_RFI, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    row = (
        _conn(db)
        .execute("SELECT * FROM procore_text_intelligence WHERE source_field_path='question'")
        .fetchone()
    )
    assert row is not None and row["encrypted_full_text_ref"]
    assert decrypt_text(row["encrypted_full_text_ref"]) == _RFI["questions"][0]["body"]
    assert "rfi:7" in (row["mentioned_records_json"] or "")


def test_rfi_cost_impact_flagged_schedule_not() -> None:
    db = _db()
    project_rfi(_RFI, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert "rfi_cost_impact_flagged" in sigs
    assert "rfi_schedule_impact_flagged" not in sigs  # schedule status no_impact
    assert "rfi_open" in sigs


def test_rfi_response_official_answer_and_edge() -> None:
    db = _db()
    project_rfi(_RFI, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    sigs = _signals(db)
    assert {"rfi_official_answer_added", "rfi_answered"} <= sigs
    edges = {r[0] for r in c.execute("SELECT edge_type FROM procore_record_edges")}
    assert "response_to_rfi" in edges
    # response answer text intelligence (encrypted), attachment path-only
    resp_text = c.execute(
        "SELECT * FROM procore_text_intelligence WHERE source_field_path='plain_text_body'"
    ).fetchone()
    assert (
        resp_text
        and decrypt_text(resp_text["encrypted_full_text_ref"])
        == "Official answer: proceed as drawn."
    )
    att = c.execute("SELECT * FROM procore_attachment_refs").fetchone()
    blob = "|".join("" if v is None else str(v) for v in att)
    assert "?" not in blob and "token=secret" not in blob and att["url_path_redacted"] == "/f/abc"


def test_unanswered_when_no_official_reply() -> None:
    db = _db()
    rfi = {**_RFI, "replies": []}
    project_rfi(rfi, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert "rfi_unanswered" in sigs
    assert "rfi_official_answer_added" not in sigs


def test_rfi_projection_idempotent() -> None:
    db = _db()
    project_rfi(_RFI, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    project_rfi(_RFI, project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db)
    c = _conn(db)
    assert c.execute("SELECT COUNT(*) FROM procore_attachment_refs").fetchone()[0] == 1
    assert (
        c.execute(
            "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='question'"
        ).fetchone()[0]
        == 1
    )


def test_response_projection_direct_without_parent() -> None:
    db = _db()
    out = project_rfi_response(
        {
            "id": 9,
            "rich_text_body": "<b>answer</b>",
            "official": False,
            "created_by_id": 5,
            "attachments": [],
        },
        parent_rfi_id=None,
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True and out["official"] is False
    # no parent -> no response_to_rfi edge, but text intelligence still recorded
    assert (
        _conn(db)
        .execute(
            "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='rich_text_body'"
        )
        .fetchone()[0]
        == 1
    )


# --------------------------------------------------------------------------- #
# ball-in-court change event via the orchestrator (history + signal)
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


def _rfi_payload(bic_id: int) -> list[dict]:
    return [
        {
            "id": 700,
            "number": "RFI-700",
            "subject": "Footing depth",
            "status": "Open",
            "ball_in_court": {"id": bic_id, "login": "x@example.test", "name": "X"},
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]


def test_ball_in_court_change_event_and_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    db = _db()

    def _sync(bic_id: int) -> None:
        run_live_sync(
            project_key="tropical",
            endpoint="rfis",
            apply=True,
            sqlite_only=True,
            confirm_live_get=True,
            max_pages=1,
            max_items=5,
            db_path=db,
            transport=_FakeTransport(_rfi_payload(bic_id)),
        )

    _sync(14)
    _sync(20)  # ball_in_court changed
    c = _conn(db)
    cats = {
        r[0]
        for r in c.execute(
            "SELECT change_category FROM procore_live_record_change_events WHERE endpoint_id='rfis'"
        )
    }
    assert "ball_in_court_changed" in cats
    sigs = {r[0] for r in c.execute("SELECT signal_type FROM procore_action_signals")}
    assert "rfi_ball_in_court_changed" in sigs
