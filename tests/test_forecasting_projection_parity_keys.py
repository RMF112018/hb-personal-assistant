"""Key-level projection parity gate tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.forecasting.gates import run_projection_parity_gate


def _create_parity_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE procore_ep_commitment_contracts (
          record_id TEXT, record_key TEXT, project_key TEXT, status TEXT
        );
        CREATE TABLE procore_financial_contracts (
          record_key TEXT PRIMARY KEY, project_key TEXT, endpoint_id TEXT,
          contract_id TEXT, contract_family TEXT, status TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0,
          redaction_applied INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO procore_ep_commitment_contracts VALUES
          ('100', 'cc:100', 'testproj', 'approved'),
          ('101', 'cc:101', 'testproj', 'draft'),
          ('102', 'cc:102', 'testproj', 'approved');
        INSERT INTO procore_financial_contracts
          (record_key, project_key, endpoint_id, contract_id, contract_family, status)
        VALUES
          ('cc:100', 'testproj', 'commitment-contracts', '100', 'commitment', 'approved'),
          ('cc:103', 'testproj', 'commitment-contracts', '103', 'commitment', 'approved');
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
    for finding in report["findings"]:
        if "sample_key_hashes" in finding:
            assert all(len(h) == 16 for h in finding["sample_key_hashes"])