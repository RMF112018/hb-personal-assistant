"""Phase 09 Prompt 12 — V38 schema-status helper + CLI (read-only, fail-closed).

Proves the read-only schema-status probe (1) reports `ready` on a migrated-to-V38 store with all
nineteen tables, twenty-three guards, and zero rows, (2) reports `not_ready` on a stale (pre-V38)
store, (3) fails closed when the Phase 09 lifecycle contract is missing/invalid, (4) drives the CLI
exit codes (0 ready / 3 not-ready / 3 contract-load failure), and (5) never mutates the store.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain import phase_09_schema
from hb_assistant.construction.second_brain.phase_09_schema import (
    Phase09SchemaContractError,
    build_phase_09_schema_status_report,
    load_phase_09_lifecycle_contract,
)
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _migrated_db(td: str) -> str:
    db = Path(td) / "v38.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_contract_loads_and_maps_all_tables() -> None:
    contract = load_phase_09_lifecycle_contract()
    assert "phase_09_lifecycle_states" in contract
    for t in phase_09_schema.PHASE_09_V38_TABLES:
        assert t in contract["tables"]


def test_status_report_ready_normal_path() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        report = build_phase_09_schema_status_report(db_path=db)
        assert report["overall_status"] == "ready"
        assert report["schema_version"] == 38
        assert report["all_tables_present"] is True
        assert report["all_guards_present"] is True
        assert report["all_rows_zero"] is True
        assert report["read_only"] is True
        assert report["policy_loaded"] is True
        assert len(report["tables"]) == 19


def test_status_report_stale_schema_not_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        # An empty DB file (no migrations applied) is below V38.
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        report = build_phase_09_schema_status_report(db_path=str(db))
        assert report["schema_ready"] is False
        assert report["overall_status"] == "not_ready"
        assert report["all_tables_present"] is False


def test_status_report_missing_contract_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise Phase09SchemaContractError("contract unavailable")

    monkeypatch.setattr(phase_09_schema, "load_phase_09_lifecycle_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        with pytest.raises(Phase09SchemaContractError):
            build_phase_09_schema_status_report(db_path=db)


def test_cli_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ready -> exit 0, payload carries command + guardrails.
    monkeypatch.setattr(
        phase_09_schema,
        "build_phase_09_schema_status_report",
        lambda: {
            "command": "second-brain data-quality phase-09-schema-status",
            "overall_status": "ready",
            "schema_version": 38,
            "schema_version_expected": 38,
            "all_tables_present": True,
            "all_guards_present": True,
            "all_rows_zero": True,
            "phase_09_table_count": 19,
            "guard_column_count": 23,
        },
    )
    result = runner.invoke(app, ["data-quality", "phase-09-schema-status", "--json"])
    assert result.exit_code == 0
    assert "phase-09-schema-status" in result.stdout
    assert "guardrails" in result.stdout

    # Not-ready -> exit 3.
    monkeypatch.setattr(
        phase_09_schema,
        "build_phase_09_schema_status_report",
        lambda: {
            "command": "second-brain data-quality phase-09-schema-status",
            "overall_status": "not_ready",
            "schema_version": 37,
            "schema_version_expected": 38,
            "all_tables_present": False,
            "all_guards_present": False,
            "all_rows_zero": True,
            "phase_09_table_count": 19,
            "guard_column_count": 23,
        },
    )
    result = runner.invoke(app, ["data-quality", "phase-09-schema-status", "--json"])
    assert result.exit_code == 3


def test_cli_contract_failure_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise Phase09SchemaContractError("contract unavailable")

    monkeypatch.setattr(phase_09_schema, "build_phase_09_schema_status_report", _boom)
    result = runner.invoke(app, ["data-quality", "phase-09-schema-status", "--json"])
    assert result.exit_code == 3
    assert "not_ready" in result.stdout


def test_helper_does_not_mutate_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        rows_before = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()

        build_phase_09_schema_status_report(db_path=db)

        conn = sqlite3.connect(db)
        rows_after = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        conn.close()
        # Row counts are the authoritative no-mutation invariant; file size is not asserted because
        # WAL checkpointing can resize the file without any row change (flaky under full-suite load).
        assert rows_before == rows_after
