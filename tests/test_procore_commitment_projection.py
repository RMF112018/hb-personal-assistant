"""Phase 05 vendor-side financial projection tests (commitments / PO / compliance)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_commitment_projection import project_commitment_family

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


def test_commitment_contract_projection_rows_facts_signals() -> None:
    db = _db()
    out = project_commitment_family(
        "commitment-contracts",
        {
            "id": 1,
            "number": "SC-001",
            "status": "Pending",
            "executed": False,
            "grand_total": "500000.00",
            "retainage_percent": "5.00",
            "currency_configuration": {"currency_iso_code": "USD"},
            "vendor": {"id": 12, "name": "Acme Concrete LLC"},
            "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True
    row = _rows(db, "procore_financial_contracts")[0]
    assert row["contract_family"] == "commitment" and row["grand_total"] == "500000.00"
    facts = {r["amount_name"] for r in _rows(db, "procore_financial_amount_facts")}
    assert {"grand_total", "retainage_percent"} <= facts
    assert "vendor" in {r["edge_type"] for r in _rows(db, "procore_record_edges")}
    cblob = "|".join(str(c) for r in _rows(db, "procore_company_entities") for c in r)
    assert "Acme Concrete LLC" in cblob  # label preserved
    pblob = "|".join(
        "" if c is None else str(c) for r in _rows(db, "procore_people_entities") for c in r
    )
    assert "pat@example.test" not in pblob and "Pat" not in pblob  # hashed
    assert "commitment_unexecuted" in _signals(db)


def test_commitment_compliance_signals_and_hashed_notes() -> None:
    db = _db()
    raw = {
        "contract_id": 1,
        "compliance_status": "non_compliant",
        "insurance_status": "expired",
        "compliance_documents": [
            {
                "id": 11,
                "type": "W9",
                "status": "active",
                "expires_at": "2026-06-10",
                "notes": "renew soon vendor@example.test",
                "attachments": [{"url": "https://x.test/w9.pdf?sig=SECRET"}],
            },
        ],
        "insurance_documents": [
            {"id": 21, "insurance_type": "GL", "status": "active", "expires_at": "2030-01-01"},
        ],
    }
    out = project_commitment_family(
        "commitment-compliance",
        raw,
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )
    assert out["projected"] is True
    docs = _rows(db, "procore_financial_compliance_documents")
    assert len(docs) == 2
    w9 = next(d for d in docs if d["compliance_id"] == "11")
    assert w9["contract_record_key"] == "tropical|commitment-contracts||1"
    assert w9["status"] == "active" and w9["expiration_date"] == "2026-06-10"
    # notes hash-only (no raw / no contact PII); attachment path-only (no signed query)
    blob = "|".join("" if c is None else str(c) for d in docs for c in d)
    assert "renew soon" not in blob and "vendor@example.test" not in blob
    assert "SECRET" not in blob and "?" not in (w9["attachment_path_redacted"] or "")
    sigs = _signals(db)
    assert {
        "commitment_non_compliant",
        "commitment_insurance_not_compliant",
        "commitment_compliance_document_expiring",
    } <= sigs  # W9 expires within 30d


def test_purchase_order_signals_processing_and_delivery() -> None:
    db = _db()
    out = project_commitment_family(
        "purchase-order-contracts",
        {
            "id": 50,
            "number": "PO-9",
            "status": "draft",
            "grand_total": "12345.67",
            "delivery_date": "2026-06-05",
            "vendor": {"id": 12, "company": "Acme"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True and out["duplicate_of_commitment"] is False
    assert _rows(db, "procore_financial_contracts")[0]["contract_family"] == "purchase_order"
    sigs = _signals(db)
    assert {"purchase_order_processing", "purchase_order_delivery_due"} <= sigs


def test_purchase_order_dedup_against_commitment() -> None:
    db = _db()
    # Commitment id=99 projected first (emits its amount facts).
    project_commitment_family(
        "commitment-contracts",
        {"id": 99, "status": "Active", "executed": True, "grand_total": "1000.00"},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    facts_before = len(_rows(db, "procore_financial_amount_facts"))
    # PO with the SAME id=99 (v2 coverage duplicate): row stored, NO new amount facts.
    out = project_commitment_family(
        "purchase-order-contracts",
        {"id": 99, "status": "active", "grand_total": "1000.00"},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["duplicate_of_commitment"] is True
    assert len(_rows(db, "procore_financial_contracts")) == 2  # both rows stored
    assert len(_rows(db, "procore_financial_amount_facts")) == facts_before  # not double-counted


def test_commitment_contract_idempotent() -> None:
    db = _db()
    raw = {"id": 1, "status": "Active", "executed": True, "grand_total": "1.00"}
    project_commitment_family(
        "commitment-contracts", raw, project_key="tropical", now_utc=_NOW, db_path=db
    )
    project_commitment_family(
        "commitment-contracts", raw, project_key="tropical", now_utc=_NOW, db_path=db
    )
    assert len(_rows(db, "procore_financial_contracts")) == 1
