"""Tests for forecast semantic-gate readiness adapter."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.forecasting.readiness import evaluate_forecast_semantic_gates


def _minimal_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_rows (
          project_key TEXT, budget_code TEXT, budget_code_id TEXT,
          actual_cost TEXT, erp_job_to_date_costs TEXT,
          cost_type TEXT, category TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def test_evaluate_forecast_semantic_gates_shape(tmp_path: Path) -> None:
    db = tmp_path / "readiness.sqlite"
    _minimal_db(db)
    report = evaluate_forecast_semantic_gates(db_path=db, mode="warn")
    assert report["ok"] is True
    assert report["mode"] == "warn"
    assert "summary" in report
    assert report["summary"]["gate_count"] == 5
    assert len(report["gates"]) == 5
    assert all("gate" in g and "ok" in g for g in report["gates"])
    assert report["gate_status"] in ("pass", "warning", "fail_blocking")