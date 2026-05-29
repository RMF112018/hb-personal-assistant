"""Phase 05 subcontractor-billing projection tests (rows / facts / edges / signals / queries)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_financials import (
    read_financial_billing_periods,
    read_financial_subcontractor_invoices,
)
from hb_assistant.store.procore_invoice_projection import project_invoice_family

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


def test_billing_period_open_and_due_soon_signals() -> None:
    db = _db()
    out = project_invoice_family(
        "billing-periods",
        {"id": 7, "status": "open", "start_date": "2026-05-01", "end_date": "2026-05-31",
         "due_date": "2026-06-02", "position": 3},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True
    row = _rows(db, "procore_financial_billing_periods")[0]
    assert row["status"] == "open" and row["due_date"] == "2026-06-02"
    assert {"billing_period_open", "billing_period_due_soon"} <= _signals(db)
    # queryable anchor
    periods = read_financial_billing_periods(project_key="tropical", db_path=db)
    assert len(periods) == 1 and periods[0]["billing_period_id"] == "7"


def test_billing_period_closed_far_due_emits_no_signal() -> None:
    db = _db()
    project_invoice_family(
        "billing-periods",
        {"id": 8, "status": "closed", "due_date": "2027-01-01"},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert _signals(db) == set()


def test_subcontractor_invoice_rows_facts_edges_signals() -> None:
    db = _db()
    out = project_invoice_family(
        "subcontractor-invoices",
        {
            "id": 40,
            "number": 5,
            "invoice_number": 5,
            "status": "approved",
            "final": False,
            "commitment_id": 1,
            "vendor_id": 12,
            "vendor_name": "Acme Concrete LLC",
            "period_id": 7,
            "previous_requisition_id": 39,
            "requisition_start": "2026-05-01",
            "requisition_end": "2026-05-31",
            "currency_configuration": {"currency_iso_code": "USD"},
            "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
            "total_claimed_amount": "250000.00",
            "summary": {
                "current_payment_due": "100000.00",
                "total_retainage": "5000.00",
                "total_completed_and_stored_to_date": "260000.00",
            },
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True
    row = _rows(db, "procore_financial_subcontractor_invoices")[0]
    assert row["commitment_record_key"] == "tropical|commitment-contracts||1"
    assert row["billing_period_id"] == "7" and row["vendor_id"] == "12"
    assert row["period_start"] == "2026-05-01" and row["current_payment_due"] == "100000.00"
    assert row["raw_body_persisted"] == 0 and row["redaction_applied"] == 1
    # amount facts carry the requisition period for period+commitment aggregation
    facts = {f["amount_name"]: f for f in _rows(db, "procore_financial_amount_facts")}
    assert {"current_payment_due", "total_retainage", "total_claimed_amount"} <= set(facts)
    assert facts["current_payment_due"]["period_start"] == "2026-05-01"
    # edges: invoice -> commitment / billing period / previous invoice
    edges = _edges(db)
    assert ("invoice_of", "tropical|commitment-contracts||1") in edges
    assert ("billed_in_period", "tropical|billing-periods||7") in edges
    assert ("supersedes", "tropical|subcontractor-invoices||39") in edges
    # vendor label preserved, creator hashed
    cblob = "|".join(str(c) for r in _rows(db, "procore_company_entities") for c in r)
    assert "Acme Concrete LLC" in cblob
    pblob = "|".join(
        "" if c is None else str(c) for r in _rows(db, "procore_people_entities") for c in r
    )
    assert "pat@example.test" not in pblob and "Pat" not in pblob
    # approved + unpaid + retainage + payment-due signals
    assert {
        "invoice_approved_not_paid",
        "invoice_retainage_held",
        "invoice_payment_due",
    } <= _signals(db)


def test_subcontractor_invoice_pending_and_final_signals() -> None:
    db = _db()
    project_invoice_family(
        "subcontractor-invoices",
        {"id": 41, "status": "under_review", "final": True, "vendor_id": 12, "commitment_id": 1,
         "summary": {}},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    sigs = _signals(db)
    assert {"invoice_pending_approval", "invoice_final"} <= sigs
    assert "invoice_payment_due" not in sigs and "invoice_retainage_held" not in sigs


def test_invoice_contract_item_rows_facts_and_materials_signal() -> None:
    db = _db()
    out = project_invoice_family(
        "subcontractor-invoice-contract-items",
        {
            "id": 99,
            "item_type": "standard",
            "line_item_id": 9,
            "cost_code_id": 4,
            "status": "approved",
            "scheduled_value": "100000.00",
            "work_completed_this_period": "25000.00",
            "materials_presently_stored": "1000.00",
            "total_completed_and_stored_to_date": "0.000000000001",
            "subcontractor_claimed_amount": "26000.00",
            "work_completed_retainage_retained_this_period": "2600.00",
            "wbs_code": {"id": 3, "flat_code": "01-100"},
            "description_of_work": "pour slab contact super@example.test",
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="40",
    )
    assert out["projected"] is True
    item = _rows(db, "procore_financial_invoice_items")[0]
    assert item["invoice_record_key"] == "tropical|subcontractor-invoices||40"
    assert item["item_type"] == "standard" and item["scheduled_value"] == "100000.00"
    assert item["retainage_held"] == "2600.00" and item["wbs_flat_code"] == "01-100"
    assert item["total_completed_and_stored_to_date"] == "0.000000000001"  # precision
    # description reduced to hash+len+masked-excerpt JSON; contact info masked out
    blob = "|".join("" if c is None else str(c) for c in item)
    assert "super@example.test" not in blob
    # amount facts carry WBS/cost for cost aggregation
    facts = {f["amount_name"]: f for f in _rows(db, "procore_financial_amount_facts")}
    assert facts["scheduled_value"]["wbs_code_id"] == "3"
    assert facts["scheduled_value"]["cost_code_id"] == "4"
    # materials-stored signal anchored on the parent invoice
    msig = [s for s in _rows(db, "procore_action_signals") if s["signal_type"] == "invoice_materials_stored"]
    assert msig and msig[0]["record_key"] == "tropical|subcontractor-invoices||40"


def test_invoice_query_filters_by_status_period_vendor() -> None:
    db = _db()
    invoices = [
        {"id": 1, "status": "approved", "period_id": 7, "vendor_id": 12, "summary": {}},
        {"id": 2, "status": "under_review", "period_id": 7, "vendor_id": 99, "summary": {}},
        {"id": 3, "status": "approved", "period_id": 8, "vendor_id": 12, "summary": {}},
    ]
    for inv in invoices:
        project_invoice_family(
            "subcontractor-invoices", inv, project_key="tropical", now_utc=_NOW, db_path=db
        )
    by_status = read_financial_subcontractor_invoices(
        project_key="tropical", status="approved", db_path=db
    )
    assert {r["invoice_id"] for r in by_status} == {"1", "3"}
    by_period = read_financial_subcontractor_invoices(
        project_key="tropical", billing_period_id="7", db_path=db
    )
    assert {r["invoice_id"] for r in by_period} == {"1", "2"}
    by_vendor = read_financial_subcontractor_invoices(
        project_key="tropical", vendor_id="12", db_path=db
    )
    assert {r["invoice_id"] for r in by_vendor} == {"1", "3"}
    combined = read_financial_subcontractor_invoices(
        project_key="tropical", status="approved", billing_period_id="7", vendor_id="12", db_path=db
    )
    assert {r["invoice_id"] for r in combined} == {"1"}


def test_subcontractor_invoice_idempotent() -> None:
    db = _db()
    raw = {"id": 40, "status": "approved", "vendor_id": 12, "commitment_id": 1, "summary": {}}
    project_invoice_family("subcontractor-invoices", raw, project_key="tropical", now_utc=_NOW, db_path=db)
    project_invoice_family("subcontractor-invoices", raw, project_key="tropical", now_utc=_NOW, db_path=db)
    assert len(_rows(db, "procore_financial_subcontractor_invoices")) == 1
