"""Phase 10 — acceptance promotion (candidate -> accepted_tasks/accepted_commitments).

Promotion is never automatic: it requires an explicit ``--promote`` together with
``--emit`` and an ``accepted`` decision, and is idempotent. These tests cover the
store writers directly and the ``review-candidate`` CLI wiring, plus the guard-column
invariant on the accepted_* rows.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
)


def _seed_task(db: str, cid: str = "t1") -> None:
    s = ConstructionStore(db_path=db)
    s.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"PRJ:task:{cid}",
        title_redacted="Submit inspection report",
        project_key="PRJ",
        assignee_class="user",
        waiting_state="waiting_on_me",
        safety_category="normal",
        confidence=0.9,
        review_status="pending",
    )
    s.upsert_candidate_source_ref(
        source_ref_id=f"sr-{cid}",
        candidate_type="task",
        candidate_id=cid,
        source_family="email_message_raw_content",
        source_ref_hash="hash-xyz",
        source_table="email_message_raw_content",
        evidence_redacted="Submit inspection report",
    )


def test_insert_accepted_task_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_task(db)
    s = ConstructionStore(db_path=db)
    assert (
        s.insert_accepted_task(
            candidate_id="t1",
            title_redacted="Submit inspection report",
            waiting_state="waiting_on_me",
            safety_category="normal",
            project_key="PRJ",
        )
        is True
    )
    # Re-promotion is a no-op (deterministic id, ON CONFLICT DO NOTHING).
    assert (
        s.insert_accepted_task(
            candidate_id="t1",
            title_redacted="Submit inspection report",
            waiting_state="waiting_on_me",
            safety_category="normal",
            project_key="PRJ",
        )
        is False
    )
    rows = s.list_accepted_tasks()
    assert len(rows) == 1
    assert rows[0]["candidate_id"] == "t1"


def test_accepted_task_guard_columns_zero(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_task(db)
    ConstructionStore(db_path=db).insert_accepted_task(
        candidate_id="t1",
        title_redacted="x",
        waiting_state="waiting_on_me",
        safety_category="normal",
    )
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    row = conn.execute(f"SELECT {cols} FROM accepted_tasks").fetchone()
    conn.close()
    assert all(v == 0 for v in row)


def test_review_candidate_no_promote_by_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_task(db)
    res = runner.invoke(
        app,
        [
            "phase-10",
            "review-candidate",
            "--candidate-id",
            "t1",
            "--candidate-type",
            "task",
            "--decision",
            "accepted",
            "--emit",
            "--db",
            db,
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["promotion_attempted"] is False
    assert payload["promoted"] is False
    assert ConstructionStore(db_path=db).list_accepted_tasks() == []


def test_review_candidate_promote_on_accepted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_task(db)
    res = runner.invoke(
        app,
        [
            "phase-10",
            "review-candidate",
            "--candidate-id",
            "t1",
            "--candidate-type",
            "task",
            "--decision",
            "accepted",
            "--emit",
            "--promote",
            "--db",
            db,
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["promoted"] is True
    rows = ConstructionStore(db_path=db).list_accepted_tasks()
    assert len(rows) == 1 and rows[0]["candidate_id"] == "t1"


def test_promote_ignored_when_decision_not_accepted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_task(db)
    res = runner.invoke(
        app,
        [
            "phase-10",
            "review-candidate",
            "--candidate-id",
            "t1",
            "--candidate-type",
            "task",
            "--decision",
            "rejected",
            "--emit",
            "--promote",
            "--db",
            db,
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["promotion_attempted"] is False
    assert ConstructionStore(db_path=db).list_accepted_tasks() == []


def test_promote_requires_emit(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_task(db)
    # --promote without --emit must write nothing (dry-run posture).
    res = runner.invoke(
        app,
        [
            "phase-10",
            "review-candidate",
            "--candidate-id",
            "t1",
            "--candidate-type",
            "task",
            "--decision",
            "accepted",
            "--no-emit",
            "--promote",
            "--db",
            db,
        ],
    )
    assert res.exit_code == 0, res.output
    assert ConstructionStore(db_path=db).list_accepted_tasks() == []
