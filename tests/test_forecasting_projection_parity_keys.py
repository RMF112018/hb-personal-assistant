"""Key-level and per-record projection parity gate tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.forecasting.gates import run_projection_parity_gate


def _create_parity_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE procore_ep_commitment_contracts (
          record_id TEXT, record_key TEXT, project_key TEXT, status TEXT, grand_total TEXT, updated_at TEXT
        );
        CREATE TABLE procore_financial_contracts (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          contract_id TEXT, contract_family TEXT, status TEXT, grand_total TEXT, updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_commitment_contracts VALUES
          ('100', 'cc:100', 'testproj', 'approved', '1000.00', '2026-06-01'),
          ('101', 'cc:101', 'testproj', 'draft', '2000.00', '2026-06-02'),
          ('102', 'cc:102', 'testproj', 'approved', '3000.00', '2026-06-03');
        INSERT INTO procore_financial_contracts
          (record_key, project_key, endpoint_id, contract_id, contract_family, status, grand_total, updated_at_utc)
        VALUES
          ('cc:100', 'testproj', 'commitment-contracts', '100', 'commitment', 'approved', '1000.00', '2026-06-01'),
          ('cc:103', 'testproj', 'commitment-contracts', '103', 'commitment', 'approved', '500.00', '2026-06-04');
        """
    )
    conn.commit()
    conn.close()


def _create_po_commitment_backed_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE procore_ep_purchase_order_contracts (
          record_id TEXT, record_key TEXT, project_key TEXT, status TEXT, grand_total TEXT, updated_at TEXT
        );
        CREATE TABLE procore_ep_commitment_contracts (
          record_id TEXT, record_key TEXT, project_key TEXT, status TEXT
        );
        CREATE TABLE procore_financial_contracts (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          contract_id TEXT, contract_family TEXT, status TEXT, grand_total TEXT, updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_purchase_order_contracts VALUES ('200', 'po:200', 'testproj', 'Approved', '900.00', '2026-06-01');
        INSERT INTO procore_ep_commitment_contracts VALUES ('300', 'cc:300', 'testproj', 'Approved');
        INSERT INTO procore_financial_contracts
          (record_key, project_key, endpoint_id, contract_id, contract_family, status, grand_total, updated_at_utc)
        VALUES
          ('po:200', 'testproj', 'purchase-order-contracts', '200', 'purchase_order', 'Approved', '900.00', '2026-06-01'),
          ('cc:300', 'testproj', 'commitment-contracts', '300', 'commitment', 'Approved', '900.00', '2026-06-01'),
          ('po:300', 'testproj', 'purchase-order-contracts', '300', 'purchase_order', 'Approved', '900.00', '2026-06-01');
        """
    )
    conn.commit()
    conn.close()


def test_projection_parity_key_level_findings(tmp_path: Path) -> None:
    db = tmp_path / "parity.sqlite"
    _create_parity_db(db)
    report = run_projection_parity_gate(db_path=db)
    checks = {f.get("check") for f in report["findings"] if "check" in f}
    assert "missing_target_keys" in checks
    assert "missing_source_keys" in checks
    assert any(f.get("basis") == "row_count_mismatch" for f in report["findings"])
    assert report["pairs_checked"] >= 1


def test_projection_parity_commitment_backed_po_is_expected_info(tmp_path: Path) -> None:
    db = tmp_path / "po-backed.sqlite"
    _create_po_commitment_backed_db(db)
    report = run_projection_parity_gate(db_path=db)
    expected = [f for f in report["findings"] if f.get("check") == "expected_financial_only_keys"]
    assert expected
    assert expected[0]["classification"] == "commitment_backed_po"
    assert expected[0]["severity"] == "info"
    unexpected = [f for f in report["findings"] if f.get("check") == "missing_source_keys"]
    assert not unexpected


def test_projection_parity_amount_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "amount.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE procore_ep_commitment_contracts (
          record_id TEXT, project_key TEXT, status TEXT, grand_total TEXT, updated_at TEXT
        );
        CREATE TABLE procore_financial_contracts (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          contract_id TEXT, contract_family TEXT, status TEXT, grand_total TEXT, updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_commitment_contracts VALUES ('100', 'testproj', 'approved', '1000.00', '2026-06-01');
        INSERT INTO procore_financial_contracts
          (record_key, project_key, endpoint_id, contract_id, contract_family, status, grand_total, updated_at_utc)
        VALUES ('cc:100', 'testproj', 'commitment-contracts', '100', 'commitment', 'approved', '2000.00', '2026-06-01');
        """
    )
    conn.commit()
    conn.close()
    report = run_projection_parity_gate(db_path=db, mode="warn")
    assert any(f.get("check") == "amount_field_mismatch" for f in report["findings"])