"""Phase 10 — daily-brief candidate synthesis (unifies email + Procore families).

Covers section routing (actions/waiting/follow_up), dry-run zero writes, apply needs flag+cap,
max-persist cap, idempotency, guard columns 0, the unified brief view including Procore digest
rows, source-linking, the empty clean path, and the CLI wiring.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import build_daily_brief_candidates
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

NOW = "2026-06-08T00:00:00+00:00"

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


def _seed_accepted(store: ConstructionStore, cid: str, *, waiting_state: str) -> str:
    store.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"PRJ:task:{cid}",
        title_redacted=f"Task {cid}",
        project_key="PRJ",
        waiting_state=waiting_state,
        safety_category="normal",
        confidence=0.9,
        review_status="accepted",
    )
    store.insert_accepted_task(
        candidate_id=cid,
        title_redacted=f"Task {cid}",
        waiting_state=waiting_state,
        safety_category="normal",
        project_key="PRJ",
        accepted_utc="2026-06-01T00:00:00+00:00",
    )
    return store.accepted_task_id_for(cid)


def _seed(db: str) -> ConstructionStore:
    s = ConstructionStore(db_path=db)
    _seed_accepted(s, "a1", waiting_state="unknown")  # -> actions
    _seed_accepted(s, "a2", waiting_state="waiting_on_me")  # -> waiting
    # a stale watch item -> follow_up
    s.upsert_follow_up_watch_item(
        watch_item_id="watch:acc-task:a3",
        watch_status="stale",
        waiting_state="unknown",
        accepted_task_id="acc-task:a3",
        project_key="PRJ",
        reason_redacted="aged_no_due",
    )
    return s


def test_section_routing(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_daily_brief_candidates(store=s, now_utc=NOW)
    assert out["by_section"] == {"actions": 1, "follow_up": 1, "waiting": 1}
    assert out["summary"]["scanned_accepted"] == 2
    assert out["summary"]["scanned_watch"] == 1
    assert out["summary"]["would_persist"] == 3


def test_dry_run_writes_zero(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_daily_brief_candidates(store=s, now_utc=NOW)
    assert out["applied"] is False
    assert out["summary"]["persisted"] == 0
    assert s.list_daily_brief_action_candidates(brief_date="2026-06-08") == []


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    try:
        build_daily_brief_candidates(store=s, now_utc=NOW, dry_run=False)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "max_persist" in str(e)


def test_max_persist_caps(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_daily_brief_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=2)
    assert out["summary"]["persisted"] == 2
    assert out["summary"]["would_persist"] == 3
    assert len(s.list_daily_brief_action_candidates(brief_date="2026-06-08")) == 2


def test_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    build_daily_brief_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=10)
    out2 = build_daily_brief_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=10)
    assert out2["summary"]["persisted"] == 0
    assert out2["summary"]["skipped_existing"] == 3


def test_guard_columns_zero(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    build_daily_brief_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=10)
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    for row in conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall():
        assert all(v == 0 for v in row)
    conn.close()


def test_unified_brief_includes_procore_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    # Simulate a Procore digest row already written for the date.
    s.insert_daily_brief_action_candidate(
        brief_date="2026-06-08",
        section="procore",
        title_redacted="12 open invoice_payment_due signals",
        confidence=1.0,
        project_key="beta",
        group_key="beta|invoice_payment_due",
    )
    out = build_daily_brief_candidates(store=s, now_utc=NOW)
    assert "procore" in out["brief"]
    assert out["brief"]["procore"][0]["title_redacted"].startswith("12 open")
    # source-linking present on synthesized sections
    assert out["brief"]["actions"][0]["source"].startswith("accepted-task|")


def test_empty_is_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    out = build_daily_brief_candidates(store=s, now_utc=NOW)
    assert out["ok"] is True
    assert out["summary"]["scanned_accepted"] == 0
    assert out["by_section"] == {}


def test_cli_dry_run_then_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    res = runner.invoke(
        app, ["daily-brief", "synthesize-candidates", "--db", db, "--as-of", NOW, "--summary"]
    )
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["applied"] is False
    res2 = runner.invoke(app, ["daily-brief", "synthesize-candidates", "--db", db, "--apply"])
    assert res2.exit_code == 2
    assert json.loads(res2.output)["error"] == "apply_requires_max_persist"
    res3 = runner.invoke(
        app,
        [
            "daily-brief",
            "synthesize-candidates",
            "--db",
            db,
            "--apply",
            "--max-persist",
            "5",
            "--as-of",
            NOW,
        ],
    )
    assert res3.exit_code == 0, res3.output
    assert json.loads(res3.output)["summary"]["persisted"] == 3
