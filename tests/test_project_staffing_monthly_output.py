"""Phase 6 staffing monthly-output calc + merge tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

from hb_assistant.construction.forecast.staffing import monthly_output as mo
from hb_assistant.construction.forecast.staffing.repositories import (
    AttributionRuleRepository,
    StaffingConfigRepository,
)
from hb_assistant.store.migrator import SQLiteMigrator

_P = "tropical"
_WINDOW = {
    "actuals_start_month": "2026-05", "actuals_through_month": "2026-06",
    "forecast_start_month": "2026-07", "forecast_end_month": "2026-08",
}


def _db(td: str) -> str:
    path = Path(td) / "staffing.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def _config(db: str, **over) -> str:
    row = {"project_key": _P, "role_title": "Super", "person_name": "Jane Doe",
           "employment_type": "Full Time", "cost_code": "01-100", "rate_unit": "weekly",
           "lab_rate": "2500.00", "start_date": "2026-07-01", "finish_date": "2026-08-31"}
    row.update(over)
    return StaffingConfigRepository(db_path=db).create(row)["staffing_config_id"]


def _cost_entry(db: str, n: int, cost_code: str, category: str, amount: float, month: str) -> None:
    raw = {"cost_code": cost_code, "category": category, "accounting_month": month,
           "amount": amount, "description": "x", "budget_code_key": f"0000.{cost_code}.{category}"}
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO forecast_cost_entries (cost_entry_id, project_key, source_package, "
            "source_row_number, budget_code_key, accounting_month, raw_json, created_utc) "
            "VALUES (?, ?, 'pkg', ?, ?, ?, ?, 't')",
            (f"ce-{n}", _P, n, raw["budget_code_key"], month, json.dumps(raw)),
        )
        conn.commit()


def test_forecast_cells_reconcile_to_line_ctc() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _config(db)
        out = mo.build_staffing_output(db, _P, _WINDOW)
        assert out["status"] == "ok"
        lab = next(ln for ln in out["lines"] if ln["category"] == "LAB")
        key = lab["budget_code_key"]
        assert key.startswith("staffing:")
        fcells = [c for c in out["monthly"] if c["budget_code_key"] == key and c["is_actual"] == 0]
        # forecast cells in the forecast window only
        assert all(_WINDOW["forecast_start_month"] <= c["month"] <= _WINDOW["forecast_end_month"]
                   for c in fcells)
        # per-row reconciliation: forecast cells sum to the line CTC
        assert sum(Decimal(c["value"]) for c in fcells) == Decimal(lab["forecast_cost_to_complete"])
        # matrix row ftc == sum forecast cells
        mrow = next(r for r in out["matrix_rows"] if r["budget_code_key"] == key)
        assert Decimal(mrow["forecast_to_complete"]) == sum(Decimal(c["value"]) for c in fcells)
        assert mrow["row_type"] == "staffing_labor"
        assert mrow["staffing_config_id"]


def test_attributed_actuals_and_mat_summary() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        cid = _config(db)
        # an attributed LAB actual (rule maps 01-100/LAB -> the config) + a MAT actual
        AttributionRuleRepository(db_path=db).upsert_rule(
            project_key=_P, cost_code="01-100", category="LAB", staffing_config_id=cid)
        _cost_entry(db, 1, "01-100", "LAB", 1000.0, "2026-06")
        _cost_entry(db, 2, "03-01-025", "MAT", 300.0, "2026-06")
        out = mo.build_staffing_output(db, _P, _WINDOW)
        labkey = f"staffing:{cid}:LAB"
        actual_cells = [c for c in out["monthly"]
                        if c["budget_code_key"] == labkey and c["is_actual"] == 1]
        assert sum(Decimal(c["value"]) for c in actual_cells) == Decimal("1000.00")
        # MAT materials row, never person-attributed
        mat = next(ln for ln in out["lines"] if ln["category"] == "MAT")
        assert mat["budget_code_key"] == "staffing-materials:03-01-025:MAT"
        mat_row = next(r for r in out["matrix_rows"] if r["row_type"] == "staffing_materials")
        assert mat_row["staffing_config_id"] is None
        assert Decimal(mat_row["completed_to_date"]) == Decimal("300.00")


def test_invalid_config_blocks() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _config(db, employment_type="Bogus")
        out = mo.build_staffing_output(db, _P, _WINDOW)
        assert out["status"] == "invalid"
        assert any(e["code"] == "employment_type_invalid" for e in out["errors"])


def test_merge_recomputes_totals_and_summary() -> None:
    result = {
        "forecast_lines": [{"budget_code_key": "b1", "cost_code": "01", "category": "LAB",
                            "forecast_final_cost": "1000.00", "forecast_cost_to_complete": "400.00"}],
        "monthly": [{"budget_code_key": "b1", "month": "2026-07", "value": "400.00",
                     "is_actual": 0, "value_type": "forecast", "source_status": "calculated_forecast"}],
        "monthly_table_rows": [{"budget_code_key": "b1", "completed_to_date": "0.00",
                                "forecast_to_complete": "400.00", "estimated_at_completion": "400.00",
                                "projected_budget_display": "1000.00", "variance_to_budget": "600.00"}],
        "monthly_table_totals": {"month_values": {"2026-07": "400.00"}},
        "summary": {"total_forecast_final_cost": "1000.00", "total_cost_to_complete": "400.00",
                    "total_revised_budget": "1000.00", "variance_to_budget": "0.00"},
    }
    staffing = {
        "status": "ok",
        "lines": [{"budget_code_key": "staffing:c1:LAB", "forecast_final_cost": "250.00",
                   "forecast_cost_to_complete": "250.00"}],
        "monthly": [{"budget_code_key": "staffing:c1:LAB", "month": "2026-07", "value": "250.00",
                     "is_actual": 0, "value_type": "forecast", "source_status": "calculated_forecast"}],
        "matrix_rows": [{"budget_code_key": "staffing:c1:LAB", "projected_budget_display": "0.00",
                         "completed_to_date": "0.00", "forecast_to_complete": "250.00",
                         "estimated_at_completion": "250.00", "variance_to_budget": "-250.00"}],
        "staffing": [{"budget_code_key": "staffing:c1:LAB", "cost_amount": "250.00"}],
    }
    merged = mo.merge_staffing_into_result(result, staffing)
    # summary CTC includes staffing
    assert merged["summary"]["total_cost_to_complete"] == "650.00"
    assert merged["summary"]["total_forecast_final_cost"] == "1250.00"
    assert merged["summary"]["variance_to_budget"] == "250.00"
    # totals recomputed over both rows + cells
    t = merged["monthly_table_totals"]
    assert t["forecast_to_complete_total"] == "650.00"
    assert t["month_values"]["2026-07"] == "650.00"
    assert len(merged["monthly_table_rows"]) == 2
    assert len(merged["forecast_lines"]) == 2
    assert merged["staffing"] == staffing["staffing"]
