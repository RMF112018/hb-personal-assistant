"""Phase 04B submittal workflow enrichment projection tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from hb_assistant.security.text_vault import decrypt_text
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_submittal_projection import project_submittal

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-29T00:00:00Z"

# Open submittal, overdue, waiting on an approver who has not returned; a second
# approver who returned with a comment + attachment (signed-URL query string); a
# near required-on-site date; custom fields.
_SUBMITTAL: Dict[str, Any] = {
    "id": 4040,
    "number": "S-200",
    "formatted_number": "S-200.0",
    "current_revision": 0,
    "revision": 0,
    "title": "Curtain wall shop drawings",
    "status": "open",
    "is_rejected": False,
    "for_record_only": False,
    "issue_date": "2026-05-10",
    "due_date": "2026-05-20",  # before _NOW -> overdue
    "required_on_site_date": "2026-06-05",  # within 14 days of _NOW -> near
    "received_date": "2026-05-09",
    "specification_section": "08 44 13",
    "submittal_manager": {"id": 31, "login": "mgr@example.test", "name": "Sub Manager"},
    "received_from": {"id": 32, "login": "from@example.test", "name": "Vendor Contact"},
    "responsible_contractor": {"id": 161072, "name": "Synthetic Glazing Co"},
    "scheduled_task": {"id": 99, "name": "Glazing install"},
    "custom_fields": {
        "custom_field_77": {"data_type": "boolean", "value": True},
        "custom_field_88": {"data_type": "string", "value": "secret cost note"},
    },
    "approvers": [
        {
            "id": 1, "approver_type": "Approver", "workflow_group_id": 5,
            "user": {"id": 41, "login": "appr1@example.test", "name": "Approver One"},
            "response_required": True, "sent_date": "2026-05-12", "returned_date": None,
            "due_date": "2026-05-18",
        },
        {
            "id": 2, "approver_type": "Approver", "workflow_group_id": 5,
            "user": {"id": 42, "login": "appr2@example.test", "name": "Approver Two"},
            "response": {"name": "Approved as Noted", "considered": "approved"},
            "response_required": True, "sent_date": "2026-05-12", "returned_date": "2026-05-19",
            "due_date": "2026-05-18",
            "comment": "Confirm anchor spacing per detail 5; coordinate with steel.",
            "attachments": [{"id": 7, "filename": "markup.pdf", "url": "https://example.test/f/abc?token=secret"}],
            "attachment_ids": [8],
        },
    ],
    "responses": [
        {
            "id": "resp-a", "author_id": 42, "response_status": "approved_as_noted",
            "comment": "Proceed as annotated.",
        },
    ],
}

# Rejected submittal (terminal) for the rejected-signal test.
_REJECTED: Dict[str, Any] = {
    "id": 4041, "number": "S-201", "title": "Rejected mockup", "status": "rejected", "is_rejected": True,
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


def test_submittal_approver_extraction_hashed_with_edges() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    c = _conn(db)
    people = c.execute("SELECT * FROM procore_people_entities").fetchall()
    pblob = "|".join(str(x) for r in people for x in r)
    assert "appr1@example.test" not in pblob and "Approver One" not in pblob
    edges = {r[0] for r in c.execute("SELECT edge_type FROM procore_record_edges")}
    assert {"approver", "submittal_manager", "received_from", "responsible_contractor", "scheduled_task"} <= edges
    company = c.execute(
        "SELECT name_redacted FROM procore_company_entities WHERE name_redacted='Synthetic Glazing Co'"
    ).fetchone()
    assert company is not None


def test_submittal_workflow_duration_metrics_on_approver_edge() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    rows = _conn(db).execute(
        "SELECT metadata_json FROM procore_record_edges WHERE edge_type='approver'"
    ).fetchall()
    metas = [json.loads(r["metadata_json"]) for r in rows if r["metadata_json"]]
    returned = [m for m in metas if m.get("returned_date")]
    assert returned and returned[0]["days_to_respond"] == 7  # 2026-05-12 -> 2026-05-19
    assert returned[0]["response_considered"] == "approved"


def test_submittal_attachment_refs_path_only() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    rows = _conn(db).execute("SELECT * FROM procore_attachment_refs").fetchall()
    assert len(rows) == 2  # one URL attachment + one associated id
    blob = "|".join("" if v is None else str(v) for r in rows for v in r)
    assert "?" not in blob and "token=secret" not in blob
    paths = {r["url_path_redacted"] for r in rows}
    assert "/f/abc" in paths


def test_submittal_response_interpretation_and_returned_signal() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert "submittal_response_returned" in sigs
    resp = _conn(db).execute(
        "SELECT * FROM procore_text_intelligence WHERE source_field_path='comment'"
    ).fetchone()
    assert resp is not None and decrypt_text(resp["encrypted_full_text_ref"]) == "Proceed as annotated."


def test_submittal_required_on_site_and_waiting_signals() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert {"submittal_open", "submittal_overdue", "submittal_waiting_on_approver",
            "submittal_required_on_site_date_near"} <= sigs


def test_submittal_rejected_signal() -> None:
    db = _db()
    project_submittal(_REJECTED, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    sigs = _signals(db)
    assert "submittal_rejected" in sigs
    assert "submittal_open" not in sigs


def test_submittal_custom_field_extraction() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    rows = _conn(db).execute("SELECT * FROM procore_custom_field_values").fetchall()
    keys = {r["custom_field_key"]: r for r in rows}
    assert keys["custom_field_77"]["value_json_redacted"] == "true"  # boolean preserved
    # string custom field reduced to hash — raw value never persisted
    blob = "|".join("" if v is None else str(v) for r in rows for v in r)
    assert "secret cost note" not in blob
    assert keys["custom_field_88"]["value_hash"] is not None


def test_submittal_projection_idempotent() -> None:
    db = _db()
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r1", now_utc=_NOW, db_path=db)
    project_submittal(_SUBMITTAL, project_key="tropical", sync_run_id="r2", now_utc=_NOW, db_path=db)
    c = _conn(db)
    assert c.execute("SELECT COUNT(*) FROM procore_attachment_refs").fetchone()[0] == 2
    assert c.execute(
        "SELECT COUNT(*) FROM procore_text_intelligence WHERE source_field_path='approver_comment'"
    ).fetchone()[0] == 1
