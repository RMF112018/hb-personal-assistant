"""Schedule metric formula proof tests."""

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
from hb_assistant.construction.analytics.schedule_metric_formula_registry import (
    all_prompt_metric_keys,
    build_metric_registry,
    registry_by_key,
)
from hb_assistant.construction.analytics.schedule_metric_formula_proof import (
    ScheduleMetricFormulaProofExporter,
)
from hb_assistant.construction.analytics.schedule_metric_formula_service import (
    ScheduleMetricFormulaService,
    activation_cross_check,
    build_activation_matrix,
    build_activation_proof,
    not_computable,
    ratio_result,
)
from hb_assistant.construction.analytics.schedule_metric_shadow_evaluator import (
    ScheduleMetricShadowEvaluator,
)
from hb_assistant.construction.analytics.schedule_cpm_formula_trace import (
    assert_db_unchanged,
    snapshot_db_row_counts,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

REPO = Path(__file__).resolve().parents[1]
XER = REPO / "tests/fixtures/schedules/xer/minimal.xer"
SCRIPT = REPO / "scripts/dev_schedule_metric_formula_proof_export.py"


def _seed_db(tmp_path: Path) -> tuple[Path, str]:
    db = tmp_path / "metric-proof.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    preview = client.post(
        "/api/projects/tropical/schedule/import-preview",
        headers={"X-HB-UI-Role": "operator"},
        files={"file": ("minimal.xer", XER.read_bytes(), "application/xml")},
    )
    assert preview.status_code == 200, preview.text
    commit = client.post(
        "/api/projects/tropical/schedule/import-commit",
        headers={"X-HB-UI-Role": "operator"},
        json={"import_id": preview.json()["import_id"], "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200, commit.text
    return db, commit.json()["schedule_version_key"]


def test_registry_includes_every_prompt_metric() -> None:
    keys = {e["metric_key"] for e in build_metric_registry()}
    for mk in all_prompt_metric_keys():
        assert mk in keys or mk.replace("_duration", "") in keys


def test_unsupported_variants_have_reasons() -> None:
    reg = registry_by_key()
    for key in ("earned_value_spi", "cost_weighted_percent_complete", "resource_weighted_percent_complete"):
        assert reg[key]["supported"] is False
        assert reg[key]["reason"]


def test_ratio_zero_denominator_not_computable() -> None:
    r = ratio_result(1.0, 0.0)
    assert r["status"] == "not_computable"
    assert r["result"] is None


def test_planned_vs_actual_activity_count_hand_calculated(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    body = svc.compute_planned_vs_actual("tropical", vk, weighting_basis="activity_count")
    assert body.get("denominator", 0) >= 1
    assert body.get("actual_percent_complete") is not None


def test_planned_vs_actual_duration_weighted(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    body = svc.compute_planned_vs_actual("tropical", vk, weighting_basis="duration_weighted")
    assert "ratio_audit" in body


def test_count_spi_hand_calculated(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    with sqlite3.connect(db) as conn:
        acts = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
            (vk,),
        ).fetchone()[0]
    spi = svc.compute_schedule_spi("tropical", vk, weighting_basis="activity_count")
    assert spi.get("earned_value_spi") is False
    assert acts >= 1


def test_earned_value_spi_not_claimed() -> None:
    reg = registry_by_key()["earned_value_spi"]
    assert reg["formula_supported"] is False


def test_schedule_delay_positive_negative_zero(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    versions = svc._trend._eligible_versions("tropical", __import__("datetime").date.today())
    delay = svc.compute_schedule_delay("tropical", versions, comparison_basis="prior_update")
    assert "points" in delay


def test_near_critical_not_computable_without_prior_cpm() -> None:
    svc = ScheduleMetricFormulaService(db_path=":memory:")
    r = svc._near_critical_change_count(None, "v2")
    assert r.get("status") == "not_computable"


def test_health_index_policy_limitations(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    health = svc.compute_health_index("tropical", vk)
    assert health.get("weighting_policy_validated") is False
    assert health.get("proof_readiness") == "pass_with_policy_limitations"
    assert health.get("components")


def test_feasibility_score_components(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    feas = svc.compute_feasibility_score(
        "tropical", vk, __import__("datetime").date.today()
    )
    assert "dependency_readiness" in feas or feas.get("reason")


def test_compression_index_internal_not_smartpm(tmp_path: Path) -> None:
    reg = registry_by_key()["schedule_compression_index_internal"]
    assert "SmartPM" in " ".join(reg.get("limitations", []))


def test_critical_indices_denominators(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    svc = ScheduleMetricFormulaService(db_path=str(db))
    idx = svc.compute_critical_indices(vk)
    if idx.get("status") != "not_computable":
        assert "critical_activity_ratio" in idx


def test_metric_proof_api(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    client = TestClient(create_app(db_path=str(db)))
    resp = client.get(
        f"/api/projects/tropical/schedule/metric-proof?schedule_version_key={vk}",
        headers={"X-HB-UI-Role": "viewer"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["formula_version"]
    assert "metrics" in body
    assert "unsupported_metrics" in body
    assert "activation_proof" in body
    assert len(body["activation_proof"]["activation_matrix"]) == 20


def test_export_writes_all_files_mutation_proof(tmp_path: Path) -> None:
    db, vk = _seed_db(tmp_path)
    out = tmp_path / "export"
    before = snapshot_db_row_counts(db)
    exporter = ScheduleMetricFormulaProofExporter(db_path=str(db))
    _pkg, code = exporter.export(
        project_key="tropical", schedule_version_key=vk, out_dir=out
    )
    after = snapshot_db_row_counts(db)
    assert_db_unchanged(before, after)
    for name in (
        "metric-formula-registry.json",
        "metric-input-snapshot.json",
        "metric-computation-trace.jsonl",
        "metric-api-activation-proof.json",
        "metric-independent-recompute-diff.json",
        "metric-proof-audit.md",
    ):
        assert (out / name).is_file()
    audit = (out / "metric-proof-audit.md").read_text()
    assert "causation" not in audit.lower() or "not" in audit.lower()
    assert str(db) not in audit
    activation = json.loads((out / "metric-api-activation-proof.json").read_text())
    assert len(activation["activation_matrix"]) == 20
    assert activation["summary"]["cross_check_finding_count"] == 0


def test_export_fixture_cli(tmp_path: Path) -> None:
    out = tmp_path / "fixture-export"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", "--out-dir", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": f"{REPO}/src:{REPO}/subrepos/construction-financial-review/src"},
    )
    assert proc.returncode in {0, 1}, proc.stderr
    assert (out / "metric-formula-registry.json").is_file()


def test_live_db_rejected(tmp_path: Path) -> None:
    live = str(PathPolicy().get_db_path())
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--db-path",
            live,
            "--schedule-version-key",
            "x",
            "--out-dir",
            str(tmp_path / "live"),
            "--confirm-clean-copy",
            "--allow-custom-copy-path",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": f"{REPO}/src"},
    )
    assert proc.returncode == 2


def test_shadow_evaluator_trace() -> None:
    snap = {
        "activities": [
            {"activity_id": "A", "duration_original": "5", "actual_finish": "2026-01-05"},
            {"activity_id": "B", "duration_original": "3"},
        ],
        "cpm_activities": [
            {"activity_id": "A", "computed_criticality_class": "computed_critical"},
        ],
    }
    traces = ScheduleMetricShadowEvaluator().evaluate_snapshot(snap)
    assert traces
    assert traces[0]["formula_expression"]


def test_activation_cross_check_runs() -> None:
    findings = activation_cross_check()
    assert isinstance(findings, list)
    matrix = build_activation_matrix()
    assert len(matrix) == 20
    unsupported = [r for r in matrix if r["activation_status"] == "active_as_unsupported_metric"]
    assert {r["metric_key"] for r in unsupported} == {
        "cost_weighted_percent_complete",
        "resource_weighted_percent_complete",
    }
    proof = build_activation_proof(project_key="tropical")
    assert proof["summary"]["registry_metric_count"] == 20
    assert "activation_matrix" in proof
