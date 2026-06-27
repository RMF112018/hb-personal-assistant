"""Phase 6 — staffing flows into DB-native generation (merge + persist + certify + snapshot + gate)."""

from __future__ import annotations

import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

from hb_assistant.construction.analytics import forecast_db_native_engine_adapter as adapter
from hb_assistant.construction.analytics.forecast_db_native_generation_service import (
    DbNativeGenerationRequest,
    generate_db_native,
)
from hb_assistant.construction.forecast.staffing.repositories import StaffingConfigRepository
from hb_assistant.store.migrator import SQLiteMigrator

_P = "tropical"
_WINDOW = {
    "forecast_start_date": "2026-07-01", "forecast_cutoff_date": "2026-06-30",
    "actuals_start_month": "2026-05", "actuals_through_month": "2026-06",
    "forecast_start_month": "2026-07", "forecast_end_month": "2026-08",
}


def _budget_result(*_a, **_k) -> dict:
    """A reconciling budget-code engine result (stands in for the CFR engine)."""
    return {
        "schema_version": 1, "project_key": _P, "generator_kind": "comprehensive",
        "status": "generated", "result_code": "ok", "message": "", "generation_scope": "comprehensive",
        "forecast_window": dict(_WINDOW), "maturity": {"tier": "M4"},
        "confidence": {"forecast_basis": "cost_entries"}, "provenance": {"engine_version": "test"},
        "assumptions": [], "risks": [],
        "forecast_lines": [{
            "budget_code_key": "b1", "cost_code": "01", "category": "LAB",
            "actual_cost_to_date": "600.00", "forecast_final_cost": "1000.00",
            "forecast_cost_to_complete": "400.00", "variance_to_budget": "0.00",
            "confidence": "high", "method_code": "x", "row_status": "ok", "reason_codes": [],
        }],
        "summary": {"total_forecast_final_cost": "1000.00", "total_cost_to_complete": "400.00",
                    "total_revised_budget": "1000.00", "variance_to_budget": "0.00"},
        "monthly": [
            {"budget_code_key": "b1", "month": "2026-06", "value": "600.00", "is_actual": 1,
             "value_type": "actual", "source_status": "source_actual"},
            {"budget_code_key": "b1", "month": "2026-07", "value": "400.00", "is_actual": 0,
             "value_type": "forecast", "source_status": "calculated_forecast"},
        ],
        "monthly_table_rows": [{
            "budget_code_key": "b1", "budget_code": "01", "cost_code": "01", "cost_type": "LAB",
            "projected_budget_display": "1000.00", "projected_budget_display_source": "x",
            "projected_budget_calculation_basis": "1000.00", "projected_budget_calculation_source": "x",
            "projected_budget_source_warning": None, "completed_to_date": "600.00",
            "forecast_to_complete": "400.00", "estimated_at_completion": "1000.00",
            "variance_to_budget": "0.00", "confidence": "high", "method_code": "x",
            "reason_codes": [], "sort_key": "b1",
        }],
        "monthly_table_totals": {
            "month_values": {"2026-06": "600.00", "2026-07": "400.00"},
            "projected_budget_total": "1000.00", "completed_to_date_total": "600.00",
            "forecast_to_complete_total": "400.00", "estimated_at_completion_total": "1000.00",
            "variance_to_budget_total": "0.00",
        },
    }


def _db(td: str) -> str:
    path = Path(td) / "gen.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def _config(db: str, **over) -> None:
    row = {"project_key": _P, "role_title": "Super", "person_name": "Jane Doe",
           "employment_type": "Full Time", "cost_code": "01-100", "rate_unit": "weekly",
           "lab_rate": "2500.00", "start_date": "2026-07-01", "finish_date": "2026-08-31"}
    row.update(over)
    StaffingConfigRepository(db_path=db).create(row)


def _request(db: str) -> DbNativeGenerationRequest:
    return DbNativeGenerationRequest(
        project_key=_P, generator_kind="comprehensive", write_enabled=True, db_path=db,
        request_id="req-1", **dict(_WINDOW),
    )


def test_staffing_flows_into_generation_output(monkeypatch) -> None:
    monkeypatch.setattr(adapter, "compute_db_native_forecast", _budget_result)
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _config(db)
        result = generate_db_native(_request(db))
        assert result.db_persisted is True, result.failure_code
        with sqlite3.connect(db) as conn:
            staffing = conn.execute(
                "SELECT budget_code_key, cost_amount FROM forecast_output_staffing"
            ).fetchall()
            assert staffing and all(k.startswith("staffing") for k, _ in staffing)
            srows = conn.execute(
                "SELECT budget_code_key FROM forecast_output_monthly_table_rows "
                "WHERE row_type = 'staffing_labor'"
            ).fetchall()
            assert srows  # staffing matrix row persisted with metadata
            ftc = conn.execute(
                "SELECT forecast_to_complete_total FROM forecast_output_monthly_table_totals"
            ).fetchone()[0]
            assert Decimal(ftc) > Decimal("400.00")  # budget 400 + staffing
            snaps = conn.execute(
                "SELECT COUNT(*) FROM forecast_project_staffing_snapshots"
            ).fetchone()[0]
            assert snaps == 1
            snap_rows = conn.execute(
                "SELECT COUNT(*) FROM forecast_project_staffing_snapshot_rows"
            ).fetchone()[0]
            assert snap_rows >= 1


def test_invalid_staffing_blocks_generation(monkeypatch) -> None:
    monkeypatch.setattr(adapter, "compute_db_native_forecast", _budget_result)
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _config(db, employment_type="Bogus")
        result = generate_db_native(_request(db))
        assert result.db_persisted is False
        assert result.failure_code == "db_native_staffing_config_invalid"
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM forecast_outputs").fetchone()[0] == 0
