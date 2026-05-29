"""Phase 05 owner-side financial projection tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_financials import read_financial_amount_facts
from hb_assistant.store.procore_owner_projection import project_owner_contract_family

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


_CONTRACT = {
    "id": 1,
    "number": "PC-001",
    "title": "Prime — bob@example.test",
    "status": "Draft",
    "executed": False,
    "private": True,
    "grand_total": "1000000.00",
    "original_contract_amount": "950000.00",
    "approved_change_orders": "50000.00",
    "retainage_percent": "10.00",
    "currency_configuration": {"currency_iso_code": "USD"},
    "architect": {"id": 5, "name": "Archie", "login": "archie@example.test"},
    "contractor": {"id": 12, "name": "Acme Concrete LLC"},
    "attachments": [{"id": 9, "filename": "c.pdf", "url": "https://x.test/f.pdf?sig=SECRET"}],
}


def test_prime_contract_projection_rows_facts_edges_signals() -> None:
    db = _db()
    out = project_owner_contract_family(
        "prime-contracts", _CONTRACT, project_key="tropical", now_utc=_NOW, db_path=db
    )
    assert out["projected"] is True
    contracts = _rows(db, "procore_financial_contracts")
    assert len(contracts) == 1
    row = contracts[0]
    assert row["contract_family"] == "owner" and row["grand_total"] == "1000000.00"
    assert row["raw_body_persisted"] == 0 and row["redaction_applied"] == 1
    assert "bob@example.test" not in (row["title_redacted"] or "")  # excerpt-masked
    # amount facts queryable
    facts = {
        f["amount_name"]: f["amount_value"]
        for f in read_financial_amount_facts(project_key="tropical", db_path=db)
    }
    assert facts["grand_total"] == "1000000.00" and facts["original_contract_sum"] == "950000.00"
    assert facts["retainage_percent"] == "10.00"
    # edges: architect/created_by people + contractor/vendor companies
    edges = {r["edge_type"] for r in _rows(db, "procore_record_edges")}
    assert {"architect", "contractor"} <= edges
    # company label preserved, person hashed
    cblob = "|".join(str(c) for r in _rows(db, "procore_company_entities") for c in r)
    assert "Acme Concrete LLC" in cblob
    pblob = "|".join(
        "" if c is None else str(c) for r in _rows(db, "procore_people_entities") for c in r
    )
    assert "archie@example.test" not in pblob and "Archie" not in pblob
    # attachment path-only (no signed query)
    att = _rows(db, "procore_attachment_refs")
    assert att and all("SECRET" not in (a["url_path_redacted"] or "") for a in att)
    # signals
    assert {"prime_contract_unexecuted", "prime_contract_private"} <= _signals(db)


def test_prime_contract_projection_idempotent() -> None:
    db = _db()
    project_owner_contract_family(
        "prime-contracts", _CONTRACT, project_key="tropical", now_utc=_NOW, db_path=db
    )
    project_owner_contract_family(
        "prime-contracts", _CONTRACT, project_key="tropical", now_utc=_NOW, db_path=db
    )
    assert len(_rows(db, "procore_financial_contracts")) == 1
    # grand_total, original_contract_sum, approved_change_orders_amount,
    # retainage_percent present in the fixture (revised_contract_sum absent).
    assert len(_rows(db, "procore_financial_amount_facts")) == 4


def test_change_order_projection_signals() -> None:
    db = _db()
    co = {
        "id": 70,
        "number": "CO-1",
        "contract_id": 1,
        "status": "approved",
        "executed": False,
        "paid": False,
        "signature_required": True,
        "grand_total": "5000.00",
        "schedule_impact_amount": "7",
    }
    out = project_owner_contract_family(
        "prime-change-orders", co, project_key="tropical", now_utc=_NOW, db_path=db
    )
    assert out["projected"] is True
    rows = _rows(db, "procore_financial_change_orders")
    assert len(rows) == 1 and rows[0]["grand_total"] == "5000.00"
    sigs = _signals(db)
    assert {
        "prime_change_order_unexecuted",
        "prime_change_order_unpaid",
        "prime_change_order_schedule_impact",
    } <= sigs
    # edge change_order_of -> contract
    assert "change_order_of" in {r["edge_type"] for r in _rows(db, "procore_record_edges")}


def test_payment_application_projection_facts_and_signals() -> None:
    db = _db()
    pa = {
        "id": 80,
        "number": 3,
        "status": "pending",
        "percent_complete": "45.5",
        "total_amount_paid": "100000.00",
        "g702": {
            "current_payment_due": "25000.00",
            "total_retainage": "2500.00",
            "balance_to_finish_including_retainage": "874999.99",
        },
        "contract": {"id": 1},
    }
    out = project_owner_contract_family(
        "payment-applications", pa, project_key="tropical", now_utc=_NOW, db_path=db
    )
    assert out["projected"] is True
    row = _rows(db, "procore_financial_payment_applications")[0]
    assert row["current_payment_due"] == "25000.00" and row["total_retainage"] == "2500.00"
    facts = {
        f["amount_name"]: f["amount_value"]
        for f in read_financial_amount_facts(project_key="tropical", db_path=db)
    }
    assert facts["total_retainage"] == "2500.00"
    assert facts["balance_to_finish_including_retainage"] == "874999.99"
    sigs = _signals(db)
    assert {"payment_application_pending_or_unpaid", "payment_application_retainage_held"} <= sigs
    assert "payment_application_of" in {r["edge_type"] for r in _rows(db, "procore_record_edges")}


def test_line_items_project_with_parent_and_decimal_precision() -> None:
    db = _db()
    project_owner_contract_family(
        "prime-contract-line-items",
        {"id": 50, "amount": "-1234.5678", "prime_contract_id": 1, "wbs_code": {"id": 7}},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )
    li = _rows(db, "procore_financial_line_items")
    assert len(li) == 1 and li[0]["amount"] == "-1234.5678"
    assert li[0]["parent_record_key"] == "tropical|prime-contracts||1"
    project_owner_contract_family(
        "prime-change-order-line-items",
        {"id": 71, "amount": "0.30", "change_order_id": 70},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="70",
    )
    coli = _rows(db, "procore_financial_change_order_line_items")
    assert len(coli) == 1 and coli[0]["amount"] == "0.30"
