"""Phase 19 — live-DB stability hardening for the forecast_probability DB-config proof.

Inherits the Phase 18a hardening: a fail-closed quiescence preflight (physical main/-wal/-shm fingerprints
+ logical schema/data_version/db_inventory counts), a measured before/after ``live_db_integrity`` block
driving the safety claim, a pinned mode=ro connection that prevents the reused materialize from inducing a
checkpoint, and ``audit/db_inventory.json`` kept byte-exact. Uses the same reduced probability fixture.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review import config_registry as cr  # noqa: E402
from construction_financial_review.common import config_root as crootmod  # noqa: E402
from construction_financial_review.forecast_intelligence import db_inventory  # noqa: E402
from construction_financial_review.forecast_probability import simulation_inputs as si  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_probability_db_config_proof as p19,
)

STAMP = "20260101_000000"
CODE = "1000.03-01-025.MAT"
RUNS = 64
SEED = 20260614


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _build_config_root(root: Path) -> Path:
    proj = {
        "project_key": "tropical",
        "project_name": "T",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
        "default_data_root": str(root / "unused"),
        "owner_sov_scope_crosswalk": "config/crosswalks/tropical/xwalk.jsonl",
        "llm": {},
        "forecast_intelligence": {"db_path": str(root / "no_inv.sqlite")},
    }
    (root / "config" / "projects").mkdir(parents=True, exist_ok=True)
    (root / "config" / "projects" / "tropical.json").write_text(
        json.dumps(proj, indent=2), encoding="utf-8"
    )
    xw = root / "config" / "crosswalks" / "tropical" / "xwalk.jsonl"
    xw.parent.mkdir(parents=True, exist_ok=True)
    xw.write_text(
        json.dumps(
            {
                "owner_sov_code": "01-000",
                "owner_scope_description": "General",
                "covered_budget_code_keys": [CODE],
                "covered_budget_code_key_patterns": [],
                "covered_budget_code_exclusion_patterns": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _build_data_root(root: Path) -> Path:
    ac = root / "forecast_accuracy_next_package_tropical_20260101_000000"
    ac.mkdir(parents=True, exist_ok=True)
    (ac / "forecast_recommendations_by_budget_code.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "budget_code_description": "Test",
                "actual_cost_all_source_to_date": "500.00",
                "recommended_cost_to_complete": "500.00",
                "worst_credible_cost_to_complete": "700.00",
                "recommended_final_cost": "1000.00",
                "worst_credible_final_cost": "1200.00",
                "current_projected_cost": "1000.00",
                "revised_budget": "1000.00",
                "committed_cost": "800.00",
                "confidence_score": "0.7",
                "overrun_confidence": "0.3",
                "model_divergence": "0.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ac / "forecast_confidence_by_budget_code.jsonl").write_text("", encoding="utf-8")
    (ac / "trend_evidence_by_budget_code.jsonl").write_text("", encoding="utf-8")
    (ac / "model_backtest_results.json").write_text(
        json.dumps({"summary_by_method": []}), encoding="utf-8"
    )
    mo = root / "forecast_monthly_package_tropical_20260101_000000"
    (mo / "audit").mkdir(parents=True, exist_ok=True)
    (mo / "remaining_work_monthly_distribution_by_budget_code.jsonl").write_text(
        json.dumps(
            {
                "budget_code_key": CODE,
                "monthly_distribution_weights": [{"month": "2026-06", "weight": "1.0"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (mo / "monthly_forecast_confidence_by_budget_code.jsonl").write_text(
        json.dumps({"budget_code_key": CODE, "monthly_distribution_score": "0.6"}) + "\n",
        encoding="utf-8",
    )
    (mo / "project_monthly_cashflow_summary.json").write_text(
        json.dumps(
            {
                "forecast_months": ["2026-06"],
                "total_actual_to_date": "500.00",
                "total_current_projected_cost": "1000.00",
                "total_recommended_final_cost": "1000.00",
                "total_worst_credible_final_cost": "1200.00",
            }
        ),
        encoding="utf-8",
    )
    (mo / "audit" / "forecast_model_controls_applied.json").write_text(
        json.dumps({"applied_model_controls": []}), encoding="utf-8"
    )
    return root


def _setup(tmp_path: Path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=cfg_root, db_path=db, project_key="tropical", import_run_id="p19a"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p19a", snapshot_reason="proof"
    )
    _c = sqlite3.connect(str(db))
    _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _c.close()
    data_root = _build_data_root(tmp_path / "data")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(si, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(db_inventory, "resolve_db_path", lambda cfg: tmp_path / "no_inv.sqlite")
    return db, snap, data_root, cfg_root


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("require_item_count", None)
    kw.setdefault("preflight_stability_seconds", 0.0)
    kw.setdefault("runs", RUNS)
    kw.setdefault("seed", SEED)
    return p19.run_forecast_probability_db_config_proof(
        live_db_path=db,
        config_snapshot_id=snap_id,
        work_root=tmp_path / "work",
        run_stamp=STAMP,
        require_live_snapshot=False,
        data_root=data_root,
        source_config_root=cfg_root,
        **kw,
    )


def test_stable_db_preflight_passes(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p19.DECISION_READY
    integ = rep["live_db_integrity"]
    assert integ["preflight_stable"] is True and integ["unchanged"] is True and integ["drift"] == []


def test_wal_shm_and_data_version_fingerprints(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    integ = rep["live_db_integrity"]
    before = integ["before"]["physical"]
    for f in ("main", "wal", "shm"):
        assert set(before[f]) == {"exists", "path", "size_bytes", "mtime_ns", "sha256"}
    for snap_state in (*integ["preflight_samples"], integ["before"], integ["after"]):
        assert isinstance(snap_state["logical"]["data_version"], int)
        assert snap_state["logical"]["db_inventory_digest"]


def test_pin_prevents_proof_induced_change(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    assert sqlite3.connect(str(db)).execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    integ = rep["live_db_integrity"]
    assert (
        integ["before"]["physical"]["main"]["sha256"]
        == integ["after"]["physical"]["main"]["sha256"]
    )
    assert integ["unchanged"] is True


def test_unstable_preflight_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = p19._live_db_state
    n = {"i": 0}

    def drifting(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        s["logical"]["data_version"] = n["i"]
        return s

    monkeypatch.setattr(p19, "_live_db_state", drifting)
    with pytest.raises(p19.ForecastProbabilityDbConfigProofError, match="live_db_not_quiescent"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_during_run_drift_not_ready(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = p19._live_db_state
    n = {"i": 0}

    def drift_after(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        if n["i"] >= 3:
            s["logical"]["data_version"] += 1000
        return s

    monkeypatch.setattr(p19, "_live_db_state", drift_after)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p19.DECISION_NOT_READY
    assert rep["not_ready_reason"] == p19.NOT_READY_REASON_LIVE_DB_MUTATED
    assert rep["live_db_integrity"]["unchanged"] is False


def test_safety_block_from_measured_evidence(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    s = rep["safety"]
    assert s["live_db_unchanged_during_run"] == rep["live_db_integrity"]["unchanged"] is True
    assert s["live_db_preflight_stable"] is True
    assert (
        s["live_db_written"] is False
        and s["live_db_migrated"] is False
        and s["live_db_imported"] is False
    )


def test_no_live_db_write(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    before = db.read_bytes()
    _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert db.read_bytes() == before
