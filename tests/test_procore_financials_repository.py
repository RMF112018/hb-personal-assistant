"""Phase 05 financial repository tests.

Proves upserts are idempotent/deterministic, decimal amount strings survive
unchanged (no binary-float corruption), the primary key prevents duplicate rows,
amount-fact emission is idempotent, and the redaction guards persist as 0/1.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_financials import (
    emit_financial_amount_fact,
    read_financial_amount_facts,
    read_financial_contract_summary,
    read_financial_risk_view,
    upsert_financial_change_order,
    upsert_financial_contract,
    upsert_financial_line_item,
)

_NOW = "2026-05-29T00:00:00Z"
# High-precision + negative decimal strings that a binary float would corrupt.
_DECIMALS = ["-1234567.89012345", "0.000000000001", "999999999999.99", "0.10", "-0.30"]


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


def test_upsert_contract_idempotent_and_pk_dedups() -> None:
    db = _db()
    rk = "tropical|prime-contracts||1"
    k1 = upsert_financial_contract(
        record_key=rk,
        project_key="tropical",
        endpoint_id="prime-contracts",
        contract_id="1",
        contract_family="owner",
        fields={"number": "PC-001", "status": "draft", "original_contract_sum": "1000.00"},
        db_path=db,
    )
    # Re-upsert same PK with an updated field -> still one row, value updated.
    k2 = upsert_financial_contract(
        record_key=rk,
        project_key="tropical",
        endpoint_id="prime-contracts",
        contract_id="1",
        contract_family="owner",
        fields={"number": "PC-001", "status": "approved", "original_contract_sum": "1000.00"},
        db_path=db,
    )
    assert k1 == k2 == rk
    rows = _rows(db, "procore_financial_contracts")
    assert len(rows) == 1
    assert rows[0]["status"] == "approved"
    assert rows[0]["raw_body_persisted"] == 0
    assert rows[0]["redaction_applied"] == 1


def test_decimal_amount_strings_survive_unchanged() -> None:
    db = _db()
    for i, dec in enumerate(_DECIMALS):
        upsert_financial_line_item(
            line_item_key=f"li{i}",
            project_key="tropical",
            parent_record_key="tropical|prime-contracts||1",
            endpoint_id="prime-contract-line-items",
            line_item_id=str(i),
            line_item_kind="prime_contract",
            fields={"amount": dec, "unit_cost": dec, "scheduled_value": dec},
            db_path=db,
        )
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        for i, dec in enumerate(_DECIMALS):
            row = conn.execute(
                "SELECT amount, unit_cost, scheduled_value FROM procore_financial_line_items WHERE line_item_key=?",
                (f"li{i}",),
            ).fetchone()
            # Stored verbatim as TEXT — exact string, correct storage class.
            assert row["amount"] == dec
            assert row["unit_cost"] == dec
            assert row["scheduled_value"] == dec
            assert isinstance(row["amount"], str)
    finally:
        conn.close()


def test_emit_amount_fact_idempotent_and_preserves_decimal() -> None:
    db = _db()
    f1 = emit_financial_amount_fact(
        project_key="tropical",
        record_key="tropical|prime-contracts||1",
        endpoint_id="prime-contracts",
        amount_name="original_contract_sum",
        amount_value="-1234567.89012345",
        source_field_path="procore_financial_contracts.original_contract_sum",
        created_at_utc=_NOW,
        db_path=db,
    )
    f2 = emit_financial_amount_fact(
        project_key="tropical",
        record_key="tropical|prime-contracts||1",
        endpoint_id="prime-contracts",
        amount_name="original_contract_sum",
        amount_value="-1234567.89012345",
        source_field_path="procore_financial_contracts.original_contract_sum",
        created_at_utc=_NOW,
        db_path=db,
    )
    assert f1 == f2  # deterministic id
    rows = read_financial_amount_facts(
        project_key="tropical", amount_name="original_contract_sum", db_path=db
    )
    assert len(rows) == 1
    assert rows[0]["amount_value"] == "-1234567.89012345"


def test_title_is_redacted_at_repository_boundary() -> None:
    db = _db()
    upsert_financial_contract(
        record_key="rk",
        project_key="tropical",
        endpoint_id="prime-contracts",
        contract_id="9",
        contract_family="owner",
        fields={"title_redacted": "Call bob@example.test or 555-123-4567 re: contract"},
        db_path=db,
    )
    row = _rows(db, "procore_financial_contracts")[0]
    title = row["title_redacted"]
    assert "bob@example.test" not in title
    assert "[email]" in title and "[phone]" in title


def test_read_views_are_deterministic() -> None:
    db = _db()
    upsert_financial_contract(
        record_key="c1",
        project_key="tropical",
        endpoint_id="prime-contracts",
        contract_id="1",
        contract_family="owner",
        fields={"number": "PC-001", "executed": 0, "grand_total": "100.00"},
        db_path=db,
    )
    upsert_financial_change_order(
        record_key="co1",
        project_key="tropical",
        endpoint_id="prime-change-orders",
        change_order_id="1",
        change_order_family="prime",
        fields={"number": "CO-001", "executed": 1, "paid": 0, "grand_total": "50.00"},
        db_path=db,
    )
    summary = read_financial_contract_summary(project_key="tropical", db_path=db)
    assert [r["record_key"] for r in summary] == ["c1"]
    risk = read_financial_risk_view(project_key="tropical", db_path=db)
    risk_types = {r["risk_type"] for r in risk}
    assert risk_types == {"contract_unexecuted", "change_order_unpaid"}
