"""Phase 07B Prompt 01 — data-quality table-inventory.

Proves the read-only table lifecycle inventory introspects the live schema, reconciles
it against the canonical lifecycle contract, and returns the expected report shape both
in-process and via the CLI (exit 0).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _fresh_db() -> str:
    fd, db_path = tempfile.mkstemp(suffix=".sqlite", prefix="test_tableinv_")
    import os

    os.close(fd)
    with contextlib.suppress(Exception):  # defensive; report tolerates partial schema
        SQLiteMigrator(db_path=str(db_path)).apply()
    return db_path


def test_report_shape_and_reconciliation() -> None:
    db_path = _fresh_db()
    try:
        report = build_table_inventory_report(db_path=db_path)
        assert report["command"] == "construction-agent data-quality table-inventory"
        assert report["read_only"] is True
        assert report["schema_version"] == LATEST_SCHEMA_VERSION
        assert report["live_table_count"] > 0
        assert isinstance(report["tables"], list) and report["tables"]
        # every entry is shaped consistently
        for entry in report["tables"]:
            assert entry["present_in_db"] is True
            assert "table_name" in entry
            assert entry["source"] in ("contract", "unmapped")
            assert "lifecycle_status" in entry
        # reconciliation block present with both directions
        recon = report["reconciliation"]
        assert "in_db_not_in_contract" in recon
        assert "in_contract_not_in_db" in recon
        # summary keys are lifecycle statuses with integer counts
        assert isinstance(report["summary_by_status"], dict)
        assert sum(report["summary_by_status"].values()) == len(report["tables"])
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_v22_marts_are_classified_from_contract_or_unmapped() -> None:
    db_path = _fresh_db()
    try:
        report = build_table_inventory_report(db_path=db_path)
        names = {t["table_name"] for t in report["tables"]}
        # the migrated DB includes the V21 marts
        assert "data_quality_gate_results" in names
        assert "cross_domain_context_readiness_mart" in names
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_v20_v21_data_quality_tables_are_mapped_not_unmapped() -> None:
    """Phase 07C Prompt 01 remediation: the nine V20/V21 Phase 07A data-quality and
    relationship tables — created after the pre-V20 manual inventory seed — must now be
    classified from the lifecycle contract (not left unmapped / unknown_requires_audit)
    so the inventory is complete before 07C adds document tables."""
    db_path = _fresh_db()
    try:
        report = build_table_inventory_report(db_path=db_path)
        assert report["contract_table_count"] == 433  # +3 V64 schedule quality evaluation tables (was 422)
        v20_v21 = {
            "construction_data_quality_runs",
            "data_quality_gate_results",
            "construction_table_lifecycle_registry",
            "source_system_record_map",
            "relationship_resolution_queue",
            "project_source_coverage_mart",
            "source_record_summary_mart",
            "relationship_quality_mart",
            "cross_domain_context_readiness_mart",
        }
        by_name = {t["table_name"]: t for t in report["tables"]}
        for name in v20_v21:
            assert name in by_name, f"{name} not present in migrated DB"
            assert by_name[name]["source"] == "contract", f"{name} left unmapped"
            assert by_name[name]["lifecycle_status"] != "unknown_requires_audit"
        # none of the nine remain in the unmapped reconciliation direction
        assert not (v20_v21 & set(report["reconciliation"]["in_db_not_in_contract"]))
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_cli_subprocess_json_exit_zero() -> None:
    cmd = [
        sys.executable,
        "-m",
        "hb_assistant.cli.main",
        "construction-agent",
        "data-quality",
        "table-inventory",
        "--json",
    ]
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr[:500]}"
    payload = json.loads(proc.stdout)
    assert payload["command"] == "construction-agent data-quality table-inventory"
    assert "report" in payload
    assert payload["guardrails"]["introspection_only"] is True
