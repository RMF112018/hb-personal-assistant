"""Tests for forecasting data-quality gates."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.forecasting.gates import (
    run_actuals_reconciliation_gate,
    run_all_forecasting_gates,
    run_double_count_gate,
)


def _create_double_count_fixture(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_change_events (
          record_id TEXT, record_key TEXT, project_key TEXT
        );
        CREATE TABLE procore_ep_change_events_change_items (
          project_key TEXT, budget_code_id TEXT, latest_cost_values_amount TEXT, primary_record_key TEXT
        );
        CREATE TABLE procore_ep_rfqs (
          record_id TEXT, record_key TEXT, change_event_id TEXT
        );
        CREATE TABLE procore_ep_rfqs_change_event_change_event_line_items (
          primary_record_key TEXT, cost_code_id TEXT
        );
        INSERT INTO procore_ep_change_events VALUES ('1', 'ce:1', 'testproj');
        INSERT INTO procore_ep_change_events_change_items
          VALUES ('testproj', '100', '5000.00', 'ce:1');
        INSERT INTO procore_ep_rfqs VALUES ('1', 'rfq:1', '1');
        INSERT INTO procore_ep_rfqs_change_event_change_event_line_items
          VALUES ('rfq:1', '100');
        """
    )
    conn.commit()
    conn.close()


def _create_actuals_fixture(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_rows (
          project_key TEXT, budget_code TEXT, budget_code_id TEXT,
          actual_cost TEXT, erp_job_to_date_costs TEXT
        );
        CREATE TABLE forecast_monthly_actuals_by_budget_code (
          project_key TEXT, budget_code_key TEXT, month TEXT, amount TEXT
        );
        INSERT INTO procore_ep_budget_detail_rows
          VALUES ('testproj', '01-100', '100', '10000.00', '15000.00');
        INSERT INTO forecast_monthly_actuals_by_budget_code
          VALUES ('testproj', '01-100', '2026-05', '500.00');
        """
    )
    conn.commit()
    conn.close()


def test_double_count_gate_detects_ce_rfq_overlap(tmp_path: Path) -> None:
    db = tmp_path / "gate.sqlite"
    _create_double_count_fixture(db)
    report = run_double_count_gate(db_path=db, mode="warn")
    assert report["gate"] == "forecast_double_count_prevention"
    assert report["finding_count"] >= 1
    assert any(f["basis"] == "change_event_and_rfq_same_budget_code" for f in report["findings"])


def test_actuals_reconciliation_warns_on_material_variance(tmp_path: Path) -> None:
    db = tmp_path / "actuals.sqlite"
    _create_actuals_fixture(db)
    report = run_actuals_reconciliation_gate(
        db_path=db,
        absolute_threshold="100.00",
        percent_threshold="0.005",
        mode="warn",
    )
    assert report["finding_count"] >= 1
    assert any(f["basis"] == "budget_actual_vs_monthly_actuals" for f in report["findings"])


def test_actuals_reconciliation_erp_sidecar_info(tmp_path: Path) -> None:
    db = tmp_path / "erp.sqlite"
    _create_actuals_fixture(db)
    report = run_actuals_reconciliation_gate(db_path=db)
    assert any(f["basis"] == "procore_actual_vs_erp_job_to_date" for f in report["findings"])


def test_all_gates_runs_without_error(tmp_path: Path) -> None:
    db = tmp_path / "all.sqlite"
    _create_double_count_fixture(db)
    report = run_all_forecasting_gates(db_path=db)
    assert "gates" in report
    assert len(report["gates"]) == 4