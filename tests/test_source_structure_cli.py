"""CLI (`hb-assistant source-structure`) — dry-run/apply semantics + read commands + refusals."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.source_structure import _temp_env, app
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()

TREE = """/Work/NAS - HB
├── 21-801-01 NORA
│   ├── Submittals
│   └── RFIs
└── @eaDir
"""


def _db(tmp_path) -> str:
    dbp = str(tmp_path / "pa.db")
    SQLiteMigrator(dbp).apply()
    return dbp


def _tree_file(tmp_path) -> str:
    p = tmp_path / "tree.txt"
    p.write_text(TREE, encoding="utf-8")
    return str(p)


def test_ingest_tree_dry_run_writes_nothing(tmp_path):
    dbp = _db(tmp_path)
    r = runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp])
    assert r.exit_code == 0
    body = json.loads(r.stdout)
    assert body["applied"] is False
    assert SourceStructureRepository(dbp).status()["folder_count"] == 0


def test_ingest_tree_apply_persists(tmp_path):
    dbp = _db(tmp_path)
    r = runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    assert r.exit_code == 0
    body = json.loads(r.stdout)
    assert body["applied"] is True
    assert body["counts"]["folders"] > 0
    assert SourceStructureRepository(dbp).status()["folder_count"] > 0


def test_scan_roots_refuses_unconfigured(tmp_path):
    dbp = _db(tmp_path)
    # No scan roots configured in the default config → exit code 2 refusal.
    r = runner.invoke(app, ["scan-roots", "--roots", "nope", "--db", dbp])
    assert r.exit_code == 2
    assert json.loads(r.stdout)["ok"] is False


def test_quality_dry_run_vs_apply(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    dry = runner.invoke(app, ["quality", "--db", dbp])
    assert json.loads(dry.stdout)["applied"] is False
    applied = runner.invoke(app, ["quality", "--db", dbp, "--apply"])
    assert json.loads(applied.stdout)["applied"] is True


def test_inspect_root_and_project_map(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    ir = runner.invoke(app, ["inspect-root", "--root", "nas-hb", "--db", dbp])
    assert json.loads(ir.stdout)["root"]["root_class"] == "construction_work"
    pm = runner.invoke(app, ["project-map", "--project", "21-801-01", "--db", dbp])
    assert "submittal" in json.loads(pm.stdout)["doc_family_coverage"]


def test_export_evidence_writes_files(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    out = tmp_path / "ev"
    r = runner.invoke(app, ["export-evidence", "--output-dir", str(out), "--db", dbp])
    assert r.exit_code == 0
    files = {f.split("/")[-1] for f in json.loads(r.stdout)["files"]}
    assert "source_structure_counts.json" in files
    assert (out / "quality_findings.json").exists()


def test_export_evidence_emits_gate_off_and_on_snapshots(tmp_path, monkeypatch):
    """The bundle proves the three-state invariant: 78 exposed default (7 disabled), 85 when enabled.
    The transient toggle must NOT leak into the process environment afterwards."""
    monkeypatch.delenv("HB_MCP_ASSISTANT_SOURCE_STRUCTURE", raising=False)
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    out = tmp_path / "ev"
    r = runner.invoke(app, ["export-evidence", "--output-dir", str(out), "--db", dbp])
    assert r.exit_code == 0

    gate_off = json.loads((out / "mcp_status_gate_off.json").read_text())
    gate_on = json.loads((out / "mcp_status_gate_on.json").read_text())
    assert gate_off["summary"]["expected_exposed"] == 78
    assert gate_off["summary"]["client_manifest_exposed"] == 78
    assert len(gate_off["summary"]["installed_but_disabled"]) == 7
    assert gate_on["summary"]["expected_exposed"] == 85
    # export-evidence restored the environment — the gate is not left enabled.
    assert "HB_MCP_ASSISTANT_SOURCE_STRUCTURE" not in os.environ


def test_readiness_command_never_overstates(tmp_path):
    dbp = _db(tmp_path)
    # Empty index → not ready (no indexed roots).
    empty = runner.invoke(app, ["readiness", "--db", dbp])
    body = json.loads(empty.stdout)
    assert body["gate_on_recommended"] is False
    assert body["roots_indexed"] == 0
    # After a clean ingest → ready.
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    ready = json.loads(runner.invoke(app, ["readiness", "--db", dbp]).stdout)
    assert ready["roots_indexed"] >= 1
    assert ready["open_error_findings"] == 0
    assert ready["gate_on_recommended"] is True


# --- refresh cycle ----------------------------------------------------------------------------
def test_refresh_dry_run_writes_no_evidence(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    out = tmp_path / "ev"
    r = runner.invoke(app, ["refresh", "--output-root", str(out), "--db", dbp])
    assert r.exit_code == 0
    body = json.loads(r.stdout)
    assert body["applied"] is False
    # No scan roots configured by default → the scan step is a clear no-op, not a failure.
    scan = next(s for s in body["steps"] if s["step"] == "scan_roots")
    assert scan["status"] == "skipped"
    assert not out.exists()  # preview writes nothing


def test_refresh_apply_runs_cycle_and_exports_evidence(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    out = tmp_path / "ev"
    r = runner.invoke(app, ["refresh", "--output-root", str(out), "--db", dbp, "--apply"])
    assert r.exit_code == 0
    body = json.loads(r.stdout)
    assert body["applied"] is True
    export = next(s for s in body["steps"] if s["step"] == "export_evidence")
    assert export["status"] == "applied"
    written_dir = Path(export["output_dir"])
    assert written_dir.exists()
    assert (written_dir / "index_readiness.json").exists()
    assert (written_dir / "mcp_status_gate_off.json").exists()


# --- operator overrides (V116) ----------------------------------------------------------------
def test_apply_override_requires_reason_and_created_by(tmp_path):
    dbp = _db(tmp_path)
    # Missing --reason / --created-by → typer required-option refusal (non-zero exit).
    r = runner.invoke(app, ["apply-override", "--target", "root", "--root", "nas-hb",
                            "--set-root-class", "backup_mirror", "--db", dbp, "--apply"])
    assert r.exit_code != 0


def test_apply_override_dry_run_writes_nothing_then_apply_persists(tmp_path):
    dbp = _db(tmp_path)
    base = ["apply-override", "--target", "root", "--root", "nas-hb",
            "--set-root-class", "backup_mirror", "--reason", "backup copy",
            "--created-by", "bobby", "--db", dbp]
    dry = runner.invoke(app, base)
    assert dry.exit_code == 0
    assert json.loads(dry.stdout)["applied"] is False
    assert SourceStructureRepository(dbp).list_overrides() == []

    applied = runner.invoke(app, [*base, "--apply"])
    assert applied.exit_code == 0
    assert json.loads(applied.stdout)["applied"] is True
    overrides = SourceStructureRepository(dbp).list_overrides()
    assert len(overrides) == 1
    assert overrides[0]["root_class"] == "backup_mirror"

    listed = runner.invoke(app, ["list-overrides", "--db", dbp])
    assert json.loads(listed.stdout)["count"] == 1


def test_apply_override_refuses_when_no_fields_set(tmp_path):
    dbp = _db(tmp_path)
    r = runner.invoke(app, ["apply-override", "--target", "root", "--root", "nas-hb",
                            "--reason", "x", "--created-by", "bobby", "--db", dbp, "--apply"])
    assert r.exit_code == 2


# --- _temp_env context manager ----------------------------------------------------------------
def test_temp_env_restores_prior_value_on_success(monkeypatch):
    monkeypatch.setenv("HB_TEST_TEMP_ENV", "original")
    with _temp_env("HB_TEST_TEMP_ENV", "temp"):
        assert os.environ["HB_TEST_TEMP_ENV"] == "temp"
    assert os.environ["HB_TEST_TEMP_ENV"] == "original"


def test_temp_env_restores_absence_on_success(monkeypatch):
    monkeypatch.delenv("HB_TEST_TEMP_ENV", raising=False)
    with _temp_env("HB_TEST_TEMP_ENV", "temp"):
        assert os.environ["HB_TEST_TEMP_ENV"] == "temp"
    assert "HB_TEST_TEMP_ENV" not in os.environ


def test_temp_env_restores_on_exception(monkeypatch):
    monkeypatch.setenv("HB_TEST_TEMP_ENV", "original")
    with pytest.raises(RuntimeError):
        with _temp_env("HB_TEST_TEMP_ENV", "temp"):
            assert os.environ["HB_TEST_TEMP_ENV"] == "temp"
            raise RuntimeError("boom")
    assert os.environ["HB_TEST_TEMP_ENV"] == "original"
