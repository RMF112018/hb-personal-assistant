"""Phase 05 budget projection tests (rows / facts / edges / signals / queries)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_budget_projection import project_budget_family
from hb_assistant.store.procore_financials import (
    read_financial_amount_facts,
    read_financial_budget_changes,
    read_financial_budget_rows,
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


def _signals(db: Path) -> set[str]:
    return {r["signal_type"] for r in _rows(db, "procore_action_signals")}


def _edges(db: Path) -> set[tuple]:
    return {(e["edge_type"], e["to_record_key"]) for e in _rows(db, "procore_record_edges")}


def test_budget_view_row() -> None:
    db = _db()
    out = project_budget_family(
        "budget-views",
        {"id": 1, "name": "Detailed Budget", "description": "note"},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    assert out["projected"] is True
    row = _rows(db, "procore_financial_budget_views")[0]
    assert row["budget_view_id"] == "1" and row["name_redacted"] == "Detailed Budget"
    assert row["raw_body_persisted"] == 0 and row["redaction_applied"] == 1


def test_budget_detail_column_edge_to_view() -> None:
    db = _db()
    project_budget_family(
        "budget-detail-columns",
        {"id": "col_1", "name": "Projected", "type": "currency"},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )
    assert ("column_of", "tropical|budget-views||1") in _edges(db)


def test_budget_detail_row_values_facts_and_signals() -> None:
    db = _db()
    project_budget_family(
        "budget-detail-rows",
        {
            "id": 9,
            "wbs_code_id": 3,
            "cost_code_id": 4,
            "original_budget_amount": "1000000.00",
            "projected_costs": "1200000.00",  # actual > budget
            "projected_over_under": "-50000.00",  # negative variance
            "budget_forecast": {"amount": "1100000.00"},  # forecast > budget
            "unbudgeted_reason": "n/a",
            "currency_configuration": {"currency_iso_code": "USD"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )
    row = _rows(db, "procore_financial_budget_rows")[0]
    assert row["budget_view_key"] == "tropical|budget-views||1"
    assert row["wbs_code_id"] == "3" and row["cost_code_id"] == "4"
    # structured column values preserved (not hashed), free text excluded
    cv = json.loads(row["column_values_json_redacted"])
    assert cv["original_budget_amount"] == "1000000.00"
    assert cv["budget_forecast.amount"] == "1100000.00"
    assert "unbudgeted_reason" not in row["column_values_json_redacted"]
    # amount facts carry WBS/cost for cost aggregation
    facts = {f["amount_name"]: f for f in _rows(db, "procore_financial_amount_facts")}
    assert facts["original_budget_amount"]["wbs_code_id"] == "3"
    assert facts["original_budget_amount"]["cost_code_id"] == "4"
    assert {
        "budget_forecast_exceeds_budget",
        "budget_actual_exceeds_budget",
        "budget_variance_negative",
    } <= _signals(db)


def test_budget_detail_row_under_budget_no_signal() -> None:
    db = _db()
    project_budget_family(
        "budget-detail-rows",
        {"id": 10, "original_budget_amount": "1000.00", "budget_forecast": {"amount": "900.00"}},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )
    sigs = _signals(db)
    assert "budget_forecast_exceeds_budget" not in sigs and "budget_variance_negative" not in sigs


def test_budget_change_history_facts_and_signal() -> None:
    db = _db()
    project_budget_family(
        "budget-change-history",
        {
            "budget_code": "01-100",
            "column": "Revised Budget",
            "type": "adjustment",
            "old_value": "100.00",
            "new_value": "150.50",
            "created_at": "2026-05-20",
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = _rows(db, "procore_financial_budget_changes")[0]
    assert row["budget_change_kind"] == "change_history"
    assert row["from_amount"] == "100.00" and row["to_amount"] == "150.50"
    assert row["wbs_flat_code"] == "01-100"
    facts = {f["amount_name"] for f in _rows(db, "procore_financial_amount_facts")}
    assert {"from_amount", "to_amount"} <= facts
    assert "budget_change_posted" in _signals(db)


def test_budget_change_line_item_parent_edge_and_query() -> None:
    db = _db()
    project_budget_family(
        "budget-change-line-items",
        {
            "id": 7,
            "budget_change_id": "bc1",
            "budget_change_number": "BC-1",
            "budget_change_status": "approved",
            "amount": "5000.00",
            "wbs_code_id": "3",
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = _rows(db, "procore_financial_budget_changes")[0]
    assert row["budget_change_kind"] == "line_item" and row["status"] == "approved"
    assert ("change_line_item_of", "tropical|budget-change-history||bc1") in _edges(db)
    assert "budget_change_posted" in _signals(db)
    by_kind = read_financial_budget_changes(
        project_key="tropical", budget_change_kind="line_item", db_path=db
    )
    assert {r["budget_change_id"] for r in by_kind} == {"7"}


def test_budget_modification_signal_and_edges() -> None:
    db = _db()
    project_budget_family(
        "budget-modifications",
        {
            "id": 11,
            "from_budget_line_item_id": 100,
            "to_budget_line_item_id": 200,
            "transfer_amount": "2500.00",
            "created_at": "2026-05-21",
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    row = _rows(db, "procore_financial_budget_changes")[0]
    assert row["budget_change_kind"] == "modification" and row["adjustment_amount"] == "2500.00"
    edges = _edges(db)
    assert ("modifies_budget_row", "tropical|budget-detail-rows||100") in edges
    assert ("modifies_budget_row", "tropical|budget-detail-rows||200") in edges
    assert "budget_modification_posted" in _signals(db)


def test_budget_rows_query_by_view_and_wbs() -> None:
    db = _db()
    for rid, wbs in ((1, 3), (2, 3), (3, 9)):
        project_budget_family(
            "budget-detail-rows",
            {"id": rid, "wbs_code_id": wbs, "original_budget_amount": "1.00"},
            project_key="tropical",
            now_utc=_NOW,
            db_path=db,
            parent_procore_id="1",
        )
    by_view = read_financial_budget_rows(
        project_key="tropical", budget_view_key="tropical|budget-views||1", db_path=db
    )
    assert {r["row_id"] for r in by_view} == {"1", "2", "3"}
    by_wbs = read_financial_budget_rows(project_key="tropical", wbs_code_id="3", db_path=db)
    assert {r["row_id"] for r in by_wbs} == {"1", "2"}
    # amount facts queryable by column (amount_name)
    facts = read_financial_amount_facts(
        project_key="tropical", amount_name="original_budget_amount", db_path=db
    )
    assert len(facts) == 3


def test_budget_view_idempotent() -> None:
    db = _db()
    raw = {"id": 1, "name": "Budget"}
    project_budget_family("budget-views", raw, project_key="tropical", now_utc=_NOW, db_path=db)
    project_budget_family("budget-views", raw, project_key="tropical", now_utc=_NOW, db_path=db)
    assert len(_rows(db, "procore_financial_budget_views")) == 1
