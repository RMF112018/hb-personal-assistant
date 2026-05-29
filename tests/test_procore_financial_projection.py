"""Phase 05 shared financial-projection primitive tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_financial_projection import (
    emit_amount_facts,
    link_record_entities,
)

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


def test_emit_amount_facts_idempotent_and_decimal_preserved() -> None:
    db = _db()
    facts = [
        {
            "amount_name": "original_contract_sum",
            "amount_value": "-1234567.89012345",
            "source_field_path": "procore_financial_contracts.original_contract_sum",
        },
        {
            "amount_name": "grand_total",
            "amount_value": "1000.00",
            "source_field_path": "procore_financial_contracts.grand_total",
        },
        {"amount_name": "skip_me", "amount_value": None},  # skipped (None)
    ]
    ids1 = emit_amount_facts(
        project_key="tropical",
        record_key="tropical|prime-contracts||1",
        endpoint_id="prime-contracts",
        facts=facts,
        created_at_utc=_NOW,
        currency_iso_code="USD",
        db_path=db,
    )
    ids2 = emit_amount_facts(
        project_key="tropical",
        record_key="tropical|prime-contracts||1",
        endpoint_id="prime-contracts",
        facts=facts,
        created_at_utc=_NOW,
        currency_iso_code="USD",
        db_path=db,
    )
    assert len(ids1) == 2 and ids1 == ids2  # deterministic + None skipped
    rows = _rows(db, "procore_financial_amount_facts")
    assert len(rows) == 2  # idempotent — no duplicates
    by_name = {r["amount_name"]: r for r in rows}
    assert by_name["original_contract_sum"]["amount_value"] == "-1234567.89012345"
    assert by_name["original_contract_sum"]["currency_iso_code"] == "USD"
    assert all(r["raw_body_persisted"] == 0 for r in rows)


def test_link_record_entities_hashes_people_preserves_company_labels() -> None:
    db = _db()
    linked = link_record_entities(
        project_key="tropical",
        record_key="tropical|prime-contracts||1",
        endpoint_id="prime-contracts",
        people={"created_by": {"id": 555, "name": "Synthetic Carl", "login": "carl@example.test"}},
        companies={"vendor": {"id": 12, "name": "Acme Concrete LLC"}},
        now_utc=_NOW,
        db_path=db,
    )
    assert "created_by" in linked and "vendor" in linked

    people = _rows(db, "procore_people_entities")
    assert len(people) == 1
    pblob = "|".join("" if v is None else str(v) for v in people[0])
    assert "Synthetic Carl" not in pblob and "carl@example.test" not in pblob

    companies = _rows(db, "procore_company_entities")
    assert len(companies) == 1
    cblob = "|".join("" if v is None else str(v) for v in companies[0])
    assert "Acme Concrete LLC" in cblob  # org label preserved (not PII)

    edges = {r["edge_type"] for r in _rows(db, "procore_record_edges")}
    assert {"created_by", "vendor"} <= edges
