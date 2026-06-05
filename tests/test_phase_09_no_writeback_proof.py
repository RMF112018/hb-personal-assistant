"""Phase 09 Prompt 37 — Phase 09 no writeback proof tests.

Covers the normal path, missing-policy fail-closed, stale-schema fail-closed, unsafe-source scanner
detection (value never echoed), the no-raw/no-writeback proof, and guard-clean artifact writing.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from hb_assistant.construction.second_brain import phase_09_no_writeback_proof as nw
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated_db(tmp_path) -> str:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_normal_clean_proof(tmp_path):
    result = nw.build_phase_09_no_writeback_proof(
        _migrated_db(tmp_path), evidence_dir=str(tmp_path / "ev"), write_evidence=False
    )

    assert result["proof_passed"] is True
    assert result["overall_status"] == "clean"
    g = result["gates"]
    assert g["modules_no_writeback"] is True
    assert g["modules_no_dangerous_imports"] is True
    assert g["db_writeback_guards_clean"] is True
    assert g["db_all_guards_clean"] is True
    assert g["mcp_wrappers_no_writeback"] is True
    assert g["scanner_detects_planted"] is True
    assert result["modules_scanned"] >= 40
    assert result["writeback_guard_sum"] == 0
    assert result["makes_determination"] is False


def test_missing_policy_fail_closed(tmp_path, monkeypatch):
    def _boom() -> dict:
        raise nw.Phase09NoWritebackProofError("contract missing")

    monkeypatch.setattr(nw, "load_phase_09_no_writeback_proof_contract", _boom)
    with pytest.raises(nw.Phase09NoWritebackProofError):
        nw.build_phase_09_no_writeback_proof(_migrated_db(tmp_path))


def test_stale_schema_fail_closed(tmp_path):
    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no schema_migrations
    with pytest.raises(nw.Phase09NoWritebackProofError):
        nw.build_phase_09_no_writeback_proof(empty)


def test_unsafe_source_scanner_flags_planted():
    # the scanner is non-vacuous: a synthetic writeback source is flagged (value never echoed)
    assert nw._non_vacuity_check() is True

    from hb_assistant.construction.data_quality.safety import (
        _scan_module_for_mutation_and_imports,
    )

    verb = "po" + "st"
    pkg = "req" + "uests"
    synthetic = "import " + pkg + "\nclient." + verb + "(url)\n"
    res = _scan_module_for_mutation_and_imports(synthetic, "synthetic")
    assert res["writeback"] and res["bad_imports"]


def test_no_raw_no_writeback_clean(tmp_path):
    result = nw.build_phase_09_no_writeback_proof(
        _migrated_db(tmp_path), evidence_dir=str(tmp_path / "ev"), write_evidence=False
    )
    assert result["writeback_findings"] == []
    assert result["bad_import_findings"] == []
    assert result["all_guard_sum"] == 0
    serialized = json.dumps(result, default=str)
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret"):
        assert token not in serialized


def test_proof_writes_guard_clean_artifacts(tmp_path):
    out_dir = tmp_path / "evidence"
    result = nw.build_phase_09_no_writeback_proof(
        _migrated_db(tmp_path), evidence_dir=str(out_dir), write_evidence=True
    )

    json_path = out_dir / "phase-09-no-writeback-proof.json"
    md_path = out_dir / "phase-09-no-writeback-proof.md"
    assert json_path.exists() and md_path.exists()
    assert result["proof_passed"] is True

    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret"):
        assert token not in text
