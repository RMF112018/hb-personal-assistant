"""CPM formula trace export CLI and integration tests."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.analytics.schedule_cpm_formula_trace import (
    CpmRunChainResolver,
    assert_db_unchanged,
    snapshot_db_row_counts,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import clear_schedule_cpm_runs, seed_procore_ep_project

XER = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"
REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "dev_schedule_cpm_formula_trace_export.py"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _seed_imported_db(tmp_path: Path) -> tuple[Path, str]:
    db = tmp_path / "formula-trace.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    preview = client.post(
        "/api/projects/tropical/schedule/import-preview",
        headers=_op(),
        files={"file": ("minimal.xer", XER.read_bytes(), "application/xml")},
    )
    assert preview.status_code == 200, preview.text
    commit = client.post(
        "/api/projects/tropical/schedule/import-commit",
        headers=_op(),
        json={
            "import_id": preview.json()["import_id"],
            "project_key": "tropical",
            "confirm": True,
        },
    )
    assert commit.status_code == 200, commit.text
    body = commit.json()
    assert body["cpm_recompute_triggered"] is True
    return db, body["schedule_version_key"]


def _run_cli(
    db: Path,
    version_key: str,
    out_dir: Path,
    *,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--db-path",
        str(db),
        "--schedule-version-key",
        version_key,
        "--latest",
        "--out-dir",
        str(out_dir),
        "--confirm-clean-copy",
        "--allow-custom-copy-path",
    ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)


def test_export_writes_five_files_and_is_mutation_proof(tmp_path: Path) -> None:
    db, version_key = _seed_imported_db(tmp_path)
    out_dir = tmp_path / "export"
    before = snapshot_db_row_counts(db)
    proc = _run_cli(db, version_key, out_dir)
    after = snapshot_db_row_counts(db)
    assert proc.returncode in {0, 1}, proc.stderr
    assert_db_unchanged(before, after)
    for name in (
        "cpm-run-summary.json",
        "cpm-activity-formula-trace.jsonl",
        "cpm-relationship-formula-trace.jsonl",
        "cpm-validation-recompute-diff.json",
        "cpm-formula-audit.md",
    ):
        assert (out_dir / name).is_file(), name

    summary = json.loads((out_dir / "cpm-run-summary.json").read_text())
    assert summary["mode"] == "schedule_cpm_formula_trace"
    assert summary["schedule_version_key"] == version_key
    assert summary["chain_resolution"]["lineage_valid"] is True

    diff = json.loads((out_dir / "cpm-validation-recompute-diff.json").read_text())
    assert diff["status"] in {"pass", "pass_with_exclusions", "fail"}
    assert diff["longest_path"]["diff_status"] == "not_evaluated"
    assert diff["source_field_exclusion"]["status"] == "pass"

    audit = (out_dir / "cpm-formula-audit.md").read_text()
    assert "Formula trace export completed" in audit
    assert "db_path" not in audit


def test_latest_resolves_lineage_not_per_stage_mix(tmp_path: Path) -> None:
    db, version_key = _seed_imported_db(tmp_path)
    resolver = CpmRunChainResolver(db_path=str(db))
    chain = resolver.resolve(version_key, latest=True)
    crit = chain.stages["criticality"]
    assert crit is not None
    lp = chain.stages["longest_path"]
    assert lp is not None
    float_run = chain.stages["float"]
    assert float_run is not None
    assert crit.get("source_run_id") == lp.get("cpm_run_id")
    assert lp.get("source_run_id") == float_run.get("cpm_run_id")


def test_incomplete_chain_exit_code_3(tmp_path: Path) -> None:
    db, version_key = _seed_imported_db(tmp_path)
    clear_schedule_cpm_runs(db, version_key)
    out_dir = tmp_path / "incomplete"
    proc = _run_cli(db, version_key, out_dir)
    assert proc.returncode == 3
    assert "incomplete" in proc.stderr.lower() or "criticality" in proc.stderr.lower()


def test_live_db_rejected_exit_code_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    live = str(PathPolicy().get_db_path())
    out_dir = tmp_path / "live"
    proc = _run_cli(Path(live), "tropical:v1", out_dir)
    assert proc.returncode == 2


def test_perturbed_persisted_value_reports_mismatch(tmp_path: Path) -> None:
    db, version_key = _seed_imported_db(tmp_path)
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    runs = [r for r in repo.list_runs(version_key) if r.get("calculation_type") == "criticality"]
    assert runs
    run_id = str(runs[0]["cpm_run_id"])
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT rowid FROM schedule_cpm_activity_results WHERE cpm_run_id = ? LIMIT 1",
            (run_id,),
        ).fetchone()
        assert row is not None
        conn.execute(
            "UPDATE schedule_cpm_activity_results SET computed_total_float = 9999 WHERE rowid = ?",
            (row[0],),
        )
        conn.commit()
    out_dir = tmp_path / "mismatch"
    proc = _run_cli(db, version_key, out_dir)
    assert proc.returncode == 1
    diff = json.loads((out_dir / "cpm-validation-recompute-diff.json").read_text())
    assert diff["status"] == "fail"
    assert diff["mismatched_activity_count"] >= 1


def test_allow_mismatches_returns_zero(tmp_path: Path) -> None:
    db, version_key = _seed_imported_db(tmp_path)
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    runs = [r for r in repo.list_runs(version_key) if r.get("calculation_type") == "criticality"]
    run_id = str(runs[0]["cpm_run_id"])
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT rowid FROM schedule_cpm_activity_results WHERE cpm_run_id = ? LIMIT 1",
            (run_id,),
        ).fetchone()
        assert row is not None
        conn.execute(
            "UPDATE schedule_cpm_activity_results SET computed_total_float = 9999 WHERE rowid = ?",
            (row[0],),
        )
        conn.commit()
    out_dir = tmp_path / "allowed"
    proc = _run_cli(db, version_key, out_dir, extra=["--allow-mismatches"])
    assert proc.returncode == 0


def test_technical_flag_adds_repo_head_only_in_summary(tmp_path: Path) -> None:
    db, version_key = _seed_imported_db(tmp_path)
    out_dir = tmp_path / "technical"
    proc = _run_cli(db, version_key, out_dir, extra=["--technical"])
    assert proc.returncode in {0, 1}
    summary = json.loads((out_dir / "cpm-run-summary.json").read_text())
    assert "db_path" in summary
    audit = (out_dir / "cpm-formula-audit.md").read_text()
    assert "repo head" in audit
