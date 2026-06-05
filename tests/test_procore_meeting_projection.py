"""Phase 04B meeting-detail enrichment projection tests."""

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
from hb_assistant.store.procore_meeting_projection import project_meeting, project_meeting_detail

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

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


_DETAIL = {
    "id": 555,
    "title": "Weekly Coordination",
    "created_by_id": 160586,
    "description": "Reviewed RFI 123 and the schedule delay. Email carl@example.test for details.",
    "conclusion": "Agreed to expedite submittal 45.",
    "attendees": [
        {
            "id": 1,
            "status": None,
            "login_information": {"id": 9, "login": "alice@example.test", "name": "Alice A"},
        },
    ],
    "attachments": [
        {"id": 7, "filename": "agenda.pdf", "url": "https://example.test/f/abc?token=secret"}
    ],
    "meeting_categories": [
        {
            "id": 10,
            "title": "Open Items",
            "position": 1,
            "meeting_topic": [
                {
                    "id": 1001,
                    "title": "Fall protection",
                    "number": "1.1",
                    "status": "open",
                    "priority": "high",
                    "description": "Need permit and utilities coordination. RFI 123 pending.",
                    "minutes": None,
                    "attachments": [
                        {
                            "id": 8,
                            "filename": "photo.jpg",
                            "url": "https://example.test/p/xyz?company_id=15",
                        }
                    ],
                }
            ],
        }
    ],
}


def test_meeting_detail_attendees_categories_topics() -> None:
    db = _db()
    project_meeting_detail(
        _DETAIL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    c = _conn(db)
    # attendee + created_by hashed, no raw login/name
    people = c.execute("SELECT * FROM procore_people_entities").fetchall()
    assert len(people) == 2
    pblob = "|".join(str(x) for r in people for x in r)
    assert "alice@example.test" not in pblob and "Alice A" not in pblob
    edges = {r[0] for r in c.execute("SELECT edge_type FROM procore_record_edges")}
    assert {"attendee", "created_by", "category", "has_topic"} <= edges
    assert {"mentioned_rfi", "mentioned_permit", "mentioned_utilities"} <= edges


def test_meeting_detail_attachment_refs_path_only() -> None:
    db = _db()
    project_meeting_detail(
        _DETAIL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    rows = _conn(db).execute("SELECT * FROM procore_attachment_refs").fetchall()
    assert len(rows) == 2  # meeting agenda + topic photo
    for row in rows:
        blob = "|".join("" if v is None else str(v) for v in row)
        assert "?" not in blob and "token=secret" not in blob and "company_id" not in blob
        assert row["url_path_redacted"] in ("/f/abc", "/p/xyz")


def test_meeting_text_intelligence_encrypted_and_tokenized() -> None:
    db = _db()
    project_meeting_detail(
        _DETAIL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    rows = (
        _conn(db)
        .execute("SELECT * FROM procore_text_intelligence WHERE source_field_path='description'")
        .fetchall()
    )
    # one for the meeting description, one for the topic description
    assert len(rows) == 2
    meeting_row = next(r for r in rows if r["endpoint_id"] == "meeting-detail")
    assert meeting_row["encrypted_full_text_ref"]
    description = str(_DETAIL["description"])
    assert decrypt_text(meeting_row["encrypted_full_text_ref"]) == description
    assert meeting_row["text_hash"] and meeting_row["text_length"] == len(description)
    # excerpt masks the email + url; mentioned token captured
    assert "alice@example.test" not in (meeting_row["excerpt_redacted"] or "")
    assert "rfi:123" in (meeting_row["mentioned_records_json"] or "")
    topic_row = next(r for r in rows if r["endpoint_id"] == "meeting-topics")
    assert "rfi:123" in (topic_row["mentioned_records_json"] or "")


def test_open_high_priority_topic_action_signal() -> None:
    db = _db()
    project_meeting_detail(
        _DETAIL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    sigs = {r[0] for r in _conn(db).execute("SELECT signal_type FROM procore_action_signals")}
    assert "meeting_topic_open_high_priority" in sigs


def test_meeting_series_edge() -> None:
    db = _db()
    project_meeting(
        {"id": 200, "parent_id": 100, "title": "Mtg #2"},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = (
        _conn(db)
        .execute(
            "SELECT from_record_key, to_record_key FROM procore_record_edges WHERE edge_type='previous_meeting'"
        )
        .fetchone()
    )
    assert row is not None
    assert row["from_record_key"] == "tropical|meetings||200"
    assert row["to_record_key"] == "tropical|meetings||100"


def test_projection_idempotent() -> None:
    db = _db()
    project_meeting_detail(
        _DETAIL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db
    )
    project_meeting_detail(
        _DETAIL, project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db
    )
    c = _conn(db)
    assert c.execute("SELECT COUNT(*) FROM procore_attachment_refs").fetchone()[0] == 2
    assert (
        c.execute(
            "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='description'"
        ).fetchone()[0]
        == 2
    )


# --------------------------------------------------------------------------- #
# grouped flattening + series edge via the orchestrator
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


def test_grouped_meetings_flattening_and_series_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")
    db = _db()
    grouped = [
        {
            "group_title": "May",
            "meetings": [
                {
                    "id": 100,
                    "title": "Kickoff",
                    "starts_at": "2026-05-01T00:00:00Z",
                    "updated_at": "2026-05-01T00:00:00Z",
                },
                {
                    "id": 200,
                    "title": "Follow-up",
                    "parent_id": 100,
                    "starts_at": "2026-05-08T00:00:00Z",
                    "updated_at": "2026-05-08T00:00:00Z",
                },
            ],
        }
    ]
    run_live_sync(
        project_key="tropical",
        endpoint="meetings",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1,
        max_items=10,
        db_path=db,
        transport=_FakeTransport(grouped),
    )
    c = _conn(db)
    # both grouped meetings were flattened + persisted as latest-state rows
    assert (
        c.execute(
            "SELECT COUNT(*) FROM procore_live_records WHERE endpoint_id='meetings'"
        ).fetchone()[0]
        == 2
    )
    # the child meeting links to its parent via a previous_meeting edge
    assert (
        c.execute(
            "SELECT COUNT(*) FROM procore_record_edges WHERE edge_type='previous_meeting'"
        ).fetchone()[0]
        == 1
    )
