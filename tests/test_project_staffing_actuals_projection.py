"""Phase 2b normalized staffing-actuals projection tests (flat cost-entry shape)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.forecast.staffing.actuals_projection import project_staffing_actuals
from hb_assistant.construction.forecast.staffing.repositories import StaffingActualsRepository
from hb_assistant.store.migrator import SQLiteMigrator

_PROJECT = "tropical"


def _db(td: str) -> str:
    path = Path(td) / "actuals.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def _seed(db: str, rows: list[dict]) -> None:
    """Seed evidence-shaped FLAT cost-entry rows into forecast_cost_entries."""
    with sqlite3.connect(db) as conn:
        for i, r in enumerate(rows, start=1):
            raw = {
                "source_sheet": "CostEntries",
                "source_row": i,
                "cost_code": r["cost_code"],
                "category": r["category"],
                "tran_type": r.get("tran_type", "AP cost"),  # must be ignored
                "accounting_date": f"{r['month']}-15",
                "accounting_month": r["month"],
                "amount": r["amount"],
                "description": r.get("description"),
                "application_of_origin": r.get("aoo", "AP"),  # must be ignored
                "budget_code_key": f"0000.{r['cost_code']}.{r['category']}",
            }
            conn.execute(
                "INSERT INTO forecast_cost_entries (cost_entry_id, project_key, source_package, "
                "source_row_number, budget_code_key, accounting_month, raw_json, created_utc) "
                "VALUES (?, ?, 'pkg', ?, ?, ?, ?, '2026-06-27T00:00:00+00:00')",
                (f"ce-{i}", _PROJECT, i, raw["budget_code_key"], r["month"], json.dumps(raw)),
            )
        conn.commit()


_ROWS = [
    {"cost_code": "15-01-530", "category": "LAB", "amount": 1000.0, "month": "2026-06",
     "description": "TWN-CONSTR.TEMPORARY LABOR.Labor"},
    {"cost_code": "15-01-530", "category": "LAB", "amount": 250.5, "month": "2026-07",
     "description": None, "tran_type": "JC cost", "aoo": "JC"},  # null desc, diff tran/aoo
    {"cost_code": "16-02-100", "category": "LBN", "amount": 80.0, "month": "2026-06",
     "description": "Burden"},
    {"cost_code": "03-01-025", "category": "MAT", "amount": 300.0, "month": "2026-06",
     "description": "PLAN COPY EXPENSE.Materials"},
    {"cost_code": "09-09-999", "category": "SUB", "amount": 9999.0, "month": "2026-06",
     "description": "Sub"},
]


def test_projection_classification() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        assert project_staffing_actuals(db, _PROJECT) == {"projected": 5}
        actuals = {(a["cost_code"], a["category"], a["accounting_month"]): a
                   for a in StaffingActualsRepository(db_path=db).list(_PROJECT)}
        lab = actuals[("15-01-530", "LAB", "2026-06")]
        assert lab["is_employee_attributable"] == 1
        assert lab["attribution_status"] == "unmatched"
        assert lab["amount"] == "1000.00"
        assert lab["description"] == "TWN-CONSTR.TEMPORARY LABOR.Labor"
        assert "raw_json" not in lab  # redaction-safe DTO
        assert actuals[("16-02-100", "LBN", "2026-06")]["is_employee_attributable"] == 1
        mat = actuals[("03-01-025", "MAT", "2026-06")]
        assert mat["is_employee_attributable"] == 0
        assert mat["attribution_status"] == "not_applicable_materials"
        sub = actuals[("09-09-999", "SUB", "2026-06")]
        assert sub["attribution_status"] == "not_applicable_non_staffing"
        # null description tolerated
        assert actuals[("15-01-530", "LAB", "2026-07")]["description"] is None


def test_projection_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        project_staffing_actuals(db, _PROJECT)
        with sqlite3.connect(db) as conn:
            before = conn.execute(
                "SELECT staffing_actual_id, created_utc FROM forecast_cost_entry_staffing_actuals "
                "ORDER BY staffing_actual_id"
            ).fetchall()
        project_staffing_actuals(db, _PROJECT)  # re-run
        with sqlite3.connect(db) as conn:
            after = conn.execute(
                "SELECT staffing_actual_id, created_utc FROM forecast_cost_entry_staffing_actuals "
                "ORDER BY staffing_actual_id"
            ).fetchall()
        assert before == after  # no new rows, created_utc immutable


def test_tran_type_and_origin_do_not_affect_grouping() -> None:
    # Two LAB entries on the same cost_code differing only in tran_type/application_of_origin
    # must both classify identically and group together (3 LAB rows in _ROWS share 15-01-530).
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        project_staffing_actuals(db, _PROJECT)
        lab = StaffingActualsRepository(db_path=db).list(_PROJECT, category="LAB")
        assert len(lab) == 2
        assert all(a["cost_code"] == "15-01-530" and a["is_employee_attributable"] == 1
                   for a in lab)
