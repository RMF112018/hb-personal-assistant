"""Phase 05 RFQ / change-event projection tests (rows / facts / edges / signals / queries)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_financials import (
    read_financial_change_events,
    read_financial_rfqs,
)
from hb_assistant.store.procore_rfq_change_event_projection import project_rfq_change_event_family

_NOW = "2026-05-29T00:00:00Z"


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _rows(db: Path, table: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        conn.close()


def _signals(db: Path) -> set[str]:
    return {r["signal_type"] for r in _rows(db, "procore_action_signals")}


def _edges(db: Path) -> set[tuple]:
    return {(e["edge_type"], e["to_record_key"]) for e in _rows(db, "procore_record_edges")}


def test_rfq_rows_facts_edges_signals() -> None:
    db = _db()
    out = project_rfq_change_event_family(
        "rfqs",
        {
            "id": 10,
            "number": "RFQ-1",
            "status": "open",
            "estimated_amount": "50000.00",
            "estimated_schedule_impact": 5,
            "original_quote": "48000.00",
            "intent_to_quote": False,
            "due_date": "2026-05-01",  # past -> overdue
            "commitment_contract_id": 1,
            "change_event": {"id": 77},
            "commitment_change_order_packages": {"id": 88},
            "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True
    row = _rows(db, "procore_financial_rfqs")[0]
    assert row["rfq_id"] == "10" and row["estimated_amount"] == "50000.00"
    assert row["raw_body_persisted"] == 0 and row["redaction_applied"] == 1
    facts = {f["amount_name"] for f in _rows(db, "procore_financial_amount_facts")}
    assert {"estimated_amount", "original_quote", "estimated_schedule_impact"} <= facts
    edges = _edges(db)
    assert ("rfq_of_commitment", "tropical|commitment-contracts||1") in edges
    assert ("rfq_change_event", "tropical|change-events||77") in edges
    assert ("rfq_change_order", "tropical|commitment-change-orders||88") in edges
    assert {
        "rfq_overdue",
        "rfq_no_intent_to_quote",
        "rfq_estimated_schedule_impact",
        "rfq_estimated_cost_exposure",
    } <= _signals(db)


def test_rfq_under_review_signal_and_query() -> None:
    db = _db()
    project_rfq_change_event_family(
        "rfqs",
        {"id": 11, "status": "under_review", "due_date": "2027-01-01", "intent_to_quote": True},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    sigs = _signals(db)
    assert "rfq_under_review" in sigs and "rfq_overdue" not in sigs
    assert "rfq_no_intent_to_quote" not in sigs
    rows = read_financial_rfqs(project_key="tropical", status="under_review", db_path=db)
    assert {r["rfq_id"] for r in rows} == {"11"}


def test_change_event_rows_facts_signals_and_query() -> None:
    db = _db()
    project_rfq_change_event_family(
        "change-events",
        {
            "id": 77,
            "number": 12,
            "status": "open",
            "scope": "in_scope",
            "estimated_cost": "250000.00",
            "estimated_revenue": "300000.00",
            "schedule_impact_amount": 7,
            "owner_cost_amount": "10000.00",
            "commitment_cost_amount": "240000.00",
            "cost_code": {"id": 4},
            "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = _rows(db, "procore_financial_change_events")[0]
    assert row["change_event_id"] == "77" and row["estimated_cost"] == "250000.00"
    facts = {f["amount_name"]: f for f in _rows(db, "procore_financial_amount_facts")}
    assert {
        "estimated_cost",
        "estimated_revenue",
        "owner_cost_amount",
        "commitment_cost_amount",
        "schedule_impact_amount",
    } <= set(facts)
    assert facts["estimated_cost"]["cost_code_id"] == "4"  # WBS/cost on facts
    assert {
        "change_event_pending",
        "change_event_rom_cost_exposure",
        "change_event_schedule_impact",
    } <= _signals(db)
    assert {
        r["change_event_id"]
        for r in read_financial_change_events(project_key="tropical", status="open", db_path=db)
    } == {"77"}


def test_change_event_object_status_projects_name() -> None:
    # Live v1.1 change_events returns status as a nested {id, name, ...} object (not a
    # string); the projection must store the scalar name, never a dict (TEXT-column bind).
    db = _db()
    project_rfq_change_event_family(
        "change-events",
        {
            "id": 90,
            "number": "CE-90",
            "status": {"id": 3, "name": "Open", "mapped_to_status": "open"},
            "scope": {"id": 1, "name": "tbd"},
            "title": "live-shaped change event",
            "created_by": {"id": 5, "login": "pat@example.test", "name": "Pat"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = _rows(db, "procore_financial_change_events")[0]
    assert row["status"] == "Open" and row["scope"] == "tbd"  # scalar, not a dict
    assert "change_event_pending" in _signals(db)


def test_change_event_terminal_status_no_pending_signal() -> None:
    db = _db()
    project_rfq_change_event_family(
        "change-events",
        {"id": 78, "status": "closed", "estimated_cost": "0", "schedule_impact_amount": 0},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert "change_event_pending" not in _signals(db)


def test_rfq_quote_amount_facts_and_edge() -> None:
    db = _db()
    project_rfq_change_event_family(
        "rfq-quotes",
        {"id": 3, "cost": "0.000000000001", "schedule_impact": 2},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="10",
    )
    facts = {
        f["amount_name"]: f["amount_value"] for f in _rows(db, "procore_financial_amount_facts")
    }
    assert facts["cost"] == "0.000000000001"  # precision preserved
    assert ("quote_of", "tropical|rfqs||10") in _edges(db)


def test_rfq_response_edge() -> None:
    db = _db()
    project_rfq_change_event_family(
        "rfq-responses",
        {"id": 2, "created_by": {"id": 9, "name": "Lee", "login": "lee@example.test"}},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="10",
    )
    assert ("response_of", "tropical|rfqs||10") in _edges(db)


def test_change_event_comment_signal_and_edge() -> None:
    db = _db()
    project_rfq_change_event_family(
        "change-event-comments",
        {"id": "c1", "creator": {"id": 5, "name": "Pat"}},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="77",
    )
    assert "change_event_comment_added" in _signals(db)
    assert ("comment_of", "tropical|change-events||77") in _edges(db)


def test_rfq_idempotent() -> None:
    db = _db()
    raw = {"id": 10, "status": "open", "estimated_amount": "1.00"}
    project_rfq_change_event_family("rfqs", raw, project_key="tropical", now_utc=_NOW, db_path=db)
    project_rfq_change_event_family("rfqs", raw, project_key="tropical", now_utc=_NOW, db_path=db)
    assert len(_rows(db, "procore_financial_rfqs")) == 1
