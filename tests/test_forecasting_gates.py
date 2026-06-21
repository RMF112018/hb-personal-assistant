"""Tests for forecasting data-quality gates."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.forecasting.gates import (
    run_actuals_reconciliation_gate,
    run_all_forecasting_gates,
    run_budget_dynamic_columns_gate,
    run_double_count_gate,
    run_projection_parity_gate,
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
          project_key TEXT, budget_code TEXT, budget_code_id TEXT, record_key TEXT,
          actual_cost TEXT, job_to_date_costs TEXT, direct_costs TEXT,
          erp_job_to_date_costs TEXT
        );
        CREATE TABLE forecast_monthly_actuals_by_budget_code (
          project_key TEXT, budget_code_key TEXT, month TEXT, amount TEXT
        );
        CREATE TABLE procore_ep_subcontractor_invoices (
          record_id TEXT, project_key TEXT, payment_date TEXT, total_claimed_amount TEXT
        );
        INSERT INTO procore_ep_budget_detail_rows
          VALUES ('testproj', '01-100', '100', 'bdr:1', '10000.00', '10000.00', '5000.00', '15000.00');
        INSERT INTO forecast_monthly_actuals_by_budget_code
          VALUES ('testproj', '01-100', '2026-05', '500.00');
        INSERT INTO procore_ep_subcontractor_invoices
          VALUES ('1', 'testproj', NULL, '1000.00');
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
    assert any(f["basis"] == "monthly_periodized_actual" for f in report["findings"])


def test_actuals_reconciliation_erp_sidecar_warning_not_hard_fail(tmp_path: Path) -> None:
    db = tmp_path / "erp.sqlite"
    _create_actuals_fixture(db)
    report = run_actuals_reconciliation_gate(db_path=db, absolute_threshold="100.00")
    assert report["ok"] is True
    erp_findings = [f for f in report["findings"] if f.get("basis") == "erp_actual_sidecar"]
    assert erp_findings
    assert all(f["severity"] in ("info", "warning") for f in erp_findings)


def test_actuals_reconciliation_null_erp_no_false_error(tmp_path: Path) -> None:
    db = tmp_path / "null_erp.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_rows (
          project_key TEXT, budget_code TEXT, job_to_date_costs TEXT, erp_job_to_date_costs TEXT
        );
        INSERT INTO procore_ep_budget_detail_rows VALUES ('testproj', '01-100', '1000.00', NULL);
        """
    )
    conn.commit()
    conn.close()
    report = run_actuals_reconciliation_gate(db_path=db)
    assert report["ok"] is True
    assert not any(f.get("severity") == "error" for f in report["findings"])


def test_actuals_payment_cash_flow_classified_separately(tmp_path: Path) -> None:
    db = tmp_path / "payment.sqlite"
    _create_actuals_fixture(db)
    report = run_actuals_reconciliation_gate(db_path=db)
    assert any(f.get("basis") == "payment_cash_flow_fact" for f in report["findings"])


def test_all_gates_runs_without_error(tmp_path: Path) -> None:
    db = tmp_path / "all.sqlite"
    _create_double_count_fixture(db)
    report = run_all_forecasting_gates(db_path=db)
    assert "gates" in report
    assert len(report["gates"]) == 5
    assert "summary" in report
    assert report["summary"]["gate_count"] == 5
    assert all("finding_count" in g for g in report["gates"])
    gate_names = {g["gate"] for g in report["gates"]}
    assert "forecast_budget_dynamic_columns" in gate_names


def test_double_count_budget_column_role_overlap(tmp_path: Path) -> None:
    db = tmp_path / "budget_overlap.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_rows (
          project_key TEXT, budget_code TEXT,
          revised_budget TEXT, approved_budget_changes TEXT, pending_budget_changes TEXT,
          projected_budget TEXT, projected_costs TEXT, committed_costs TEXT, direct_costs TEXT,
          pending_cost_changes TEXT, estimated_cost_at_completion TEXT, forecast_to_complete TEXT
        );
        INSERT INTO procore_ep_budget_detail_rows
          VALUES ('testproj', '01-100', '50000.00', '1000.00', '2500.00', '52000.00',
                  '40000.00', '10000.00', '5000.00', '500.00', '45000.00', '5000.00');
        """
    )
    conn.commit()
    conn.close()
    report = run_double_count_gate(db_path=db, mode="warn")
    bases = {f.get("basis") for f in report["findings"]}
    assert "proven_projected_costs_includes_components" in bases
    assert "proven_eac_includes_projected_costs_and_ftc" in bases
    proven = [f for f in report["findings"] if f.get("procore_formula_status") == "proven"]
    assert proven
    assert all(f.get("severity") == "info" for f in proven)


def test_double_count_unresolved_formula_stays_warning_not_error(tmp_path: Path) -> None:
    db = tmp_path / "unresolved.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_rows (
          project_key TEXT, budget_code TEXT,
          revised_budget TEXT, pending_budget_changes TEXT
        );
        INSERT INTO procore_ep_budget_detail_rows
          VALUES ('testproj', '01-100', '50000.00', '2500.00');
        """
    )
    conn.commit()
    conn.close()
    warn_report = run_double_count_gate(db_path=db, mode="warn")
    pending_findings = [
        f
        for f in warn_report["findings"]
        if f.get("basis") == "pending_not_in_revised_budget_may_still_coexist"
    ]
    assert pending_findings
    assert all(f["severity"] == "warning" for f in pending_findings)
    assert pending_findings[0].get("procore_formula_status") == "partially_proven"


def test_budget_dynamic_column_standard_maps_known_role(tmp_path: Path) -> None:
    db = tmp_path / "dynamic.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_columns (
          budget_view_id TEXT, column_id TEXT, column_key TEXT, name TEXT, label TEXT,
          data_type TEXT, is_current INTEGER
        );
        CREATE TABLE procore_ep_budget_detail_row_cells (
          column_key TEXT, column_name TEXT, value_decimal_text TEXT, is_current INTEGER
        );
        INSERT INTO procore_ep_budget_detail_columns
          VALUES ('1', 'c1', 'Original Budget Amount', 'Original Budget Amount', 'Original Budget Amount', 'standard', 1);
        INSERT INTO procore_ep_budget_detail_row_cells
          VALUES ('Original Budget Amount', 'Original Budget Amount', '50000.00', 1);
        """
    )
    conn.commit()
    conn.close()
    report = run_budget_dynamic_columns_gate(db_path=db)
    assert report["classification_counts"].get("standard_known_column", 0) >= 1
    assert not any(f.get("classification") == "custom_numeric_candidate" for f in report["findings"])


def test_budget_dynamic_custom_numeric_is_review_required(tmp_path: Path) -> None:
    db = tmp_path / "custom_numeric.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_columns (
          budget_view_id TEXT, column_id TEXT, column_key TEXT, name TEXT, label TEXT,
          data_type TEXT, is_current INTEGER
        );
        CREATE TABLE procore_ep_budget_detail_row_cells (
          column_key TEXT, column_name TEXT, value_decimal_text TEXT, is_current INTEGER
        );
        INSERT INTO procore_ep_budget_detail_columns
          VALUES ('1', 'c9', 'Custom Forecast Buffer', 'Custom Forecast Buffer', 'Custom Forecast Buffer', 'source', 1);
        INSERT INTO procore_ep_budget_detail_row_cells
          VALUES ('Custom Forecast Buffer', 'Custom Forecast Buffer', '1200.00', 1);
        """
    )
    conn.commit()
    conn.close()
    report = run_budget_dynamic_columns_gate(db_path=db, mode="warn")
    assert any(
        f.get("classification") in ("custom_numeric_candidate", "review_required")
        for f in report["findings"]
    )


def test_budget_dynamic_text_column_not_parsed_as_money(tmp_path: Path) -> None:
    db = tmp_path / "notes.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_budget_detail_columns (
          budget_view_id TEXT, column_id TEXT, column_key TEXT, name TEXT, label TEXT,
          data_type TEXT, is_current INTEGER
        );
        INSERT INTO procore_ep_budget_detail_columns
          VALUES ('1', 'n1', 'Notes', 'Notes', 'Notes', 'standard', 1);
        """
    )
    conn.commit()
    conn.close()
    report = run_budget_dynamic_columns_gate(db_path=db)
    assert any(f.get("classification") == "custom_text_or_note" for f in report["findings"])


def test_projection_parity_prime_matching_record(tmp_path: Path) -> None:
    db = tmp_path / "prime.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_prime_contracts (
          record_id TEXT, project_key TEXT, status TEXT, grand_total TEXT, updated_at TEXT
        );
        CREATE TABLE procore_financial_contracts (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          contract_id TEXT, contract_family TEXT, status TEXT, grand_total TEXT, updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_prime_contracts VALUES ('10', 'testproj', 'Approved', '500000.00', '2026-06-01');
        INSERT INTO procore_financial_contracts
          (record_key, project_key, endpoint_id, contract_id, contract_family, status, grand_total, updated_at_utc)
        VALUES ('pc:10', 'testproj', 'prime-contracts', '10', 'owner', 'Approved', '500000.00', '2026-06-01');
        """
    )
    conn.commit()
    conn.close()
    report = run_projection_parity_gate(db_path=db)
    assert report["pairs_checked"] >= 1
    assert not any(
        f.get("family") == "prime" and f.get("check") == "missing_target_keys" for f in report["findings"]
    )


def test_projection_parity_change_event_target_only(tmp_path: Path) -> None:
    db = tmp_path / "ce.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_change_events (
          record_id TEXT, project_key TEXT, status_name TEXT, updated_at TEXT
        );
        CREATE TABLE procore_financial_change_events (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          change_event_id TEXT, status TEXT, updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_financial_change_events
          (record_key, project_key, endpoint_id, change_event_id, status, updated_at_utc)
        VALUES ('ce:99', 'testproj', 'change-events', '99', 'open', '2026-06-01');
        """
    )
    conn.commit()
    conn.close()
    report = run_projection_parity_gate(db_path=db, mode="warn")
    assert any(
        f.get("family") == "change_event" and f.get("check") == "missing_source_keys"
        for f in report["findings"]
    )


def test_projection_parity_invoice_status_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "invoice.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_subcontractor_invoices (
          record_id TEXT, project_key TEXT, status TEXT, total_claimed_amount TEXT, updated_at TEXT
        );
        CREATE TABLE procore_financial_subcontractor_invoices (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          invoice_id TEXT, status TEXT, total_claimed_amount TEXT, updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_subcontractor_invoices VALUES ('50', 'testproj', 'approved', '1000.00', '2026-06-01');
        INSERT INTO procore_financial_subcontractor_invoices
          (record_key, project_key, endpoint_id, invoice_id, status, total_claimed_amount, updated_at_utc)
        VALUES ('inv:50', 'testproj', 'subcontractor-invoices', '50', 'draft', '1000.00', '2026-06-01');
        """
    )
    conn.commit()
    conn.close()
    report = run_projection_parity_gate(db_path=db, mode="warn")
    assert any(
        f.get("family") == "subcontractor_invoice" and f.get("check") == "status_field_mismatch"
        for f in report["findings"]
    )


def test_projection_parity_rfq_unsupported_reported(tmp_path: Path) -> None:
    db = tmp_path / "rfq.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_rfqs (record_id TEXT, project_key TEXT, updated_at TEXT);
        CREATE TABLE procore_financial_rfqs (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT, rfq_id TEXT,
          updated_at_utc TEXT, raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_rfqs VALUES ('1', 'testproj', '2026-06-01');
        INSERT INTO procore_financial_rfqs
          (record_key, project_key, endpoint_id, rfq_id, updated_at_utc)
        VALUES ('rfq:1', 'testproj', 'rfqs', '1', '2026-06-01'),
               ('rfq:2', 'testproj', 'rfqs', '2', '2026-06-02');
        """
    )
    conn.commit()
    conn.close()
    report = run_projection_parity_gate(db_path=db)
    assert report["pairs_unsupported"] >= 1
    assert any(f.get("basis") == "parity_unsupported" and f.get("family") == "rfq" for f in report["findings"])