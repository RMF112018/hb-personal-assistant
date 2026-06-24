"""Phase 20 — live-DB stability hardening for the forecast_comprehensive DB-config proof.

Inherits the Phase 18a/19 hardening: a fail-closed quiescence preflight (physical main/-wal/-shm fingerprints
+ logical schema/data_version/db_inventory counts), a measured before/after ``live_db_integrity`` block driving
the safety claim, a pinned mode=ro connection that prevents the reused materialize from inducing a checkpoint,
and ``audit/db_inventory.json`` kept byte-exact. Uses the reduced comprehensive fixture (with cost-frequency).
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
from construction_financial_review.forecast_comprehensive import (  # noqa: E402
    generate_comprehensive_forecast_package as gen,
)
from construction_financial_review.forecast_intelligence import db_inventory  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_comprehensive_db_config_proof as p20,
)

STAMP = "20260101_000000"
CODE = "1000.03-01-025.MAT"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _w(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(rows, list):
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    else:
        path.write_text(json.dumps(rows), encoding="utf-8")


def _build_config_root(root: Path) -> Path:
    proj = {
        "project_key": "tropical",
        # project_name + project_display_name MUST mirror the real config/projects/tropical.json so
        # file-backed (real config) and db-backed (this synthetic snapshot) comprehensive
        # manifest.json/README.md match for byte-exact parity (job_reference/forecast_period already do).
        "project_name": "Tropical World Nursery Senior Living Facility",
        "project_display_name": "Tropical World Nursery",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
        "default_data_root": str(root / "unused"),
        "owner_sov_scope_crosswalk": "config/crosswalks/tropical/xwalk.jsonl",
        "forecast_controls": {
            "enabled": False,
            "control_file": "config/forecast_controls/tropical/c.jsonl",
        },
        "forecast_model_controls": {
            "enabled": False,
            "control_file": "config/forecast_model_controls/tropical/m.jsonl",
        },
        "forecast_comprehensive": {},
        "llm": {},
        "forecast_intelligence": {"db_path": str(root / "no_inv.sqlite")},
    }
    _w(root / "config" / "projects" / "tropical.json", proj)
    _w(
        root / "config" / "crosswalks" / "tropical" / "xwalk.jsonl",
        [
            {
                "owner_sov_code": "01-000",
                "owner_scope_description": "G",
                "covered_budget_code_keys": [CODE],
                "covered_budget_code_key_patterns": [],
                "covered_budget_code_exclusion_patterns": [],
            }
        ],
    )
    _w(
        root / "config" / "forecast_controls" / "tropical" / "c.jsonl",
        [{"project_key": "tropical", "control_id": "c1"}],
    )
    _w(
        root / "config" / "forecast_model_controls" / "tropical" / "m.jsonl",
        [{"project_key": "tropical", "control_id": "m1"}],
    )
    return root


def _manifest(name):
    return {"manifest_version": "1.0.0", "package_name": name, "output_files": []}


def _build_data_root(root: Path) -> Path:
    ctx = root / "forecast_context_package_tropical_20260101_000000"
    _w(
        ctx / "canonical" / "budget_codes.jsonl",
        [{"budget_code_key": CODE, "cost_code": "03-01-025", "category": "MAT"}],
    )
    _w(
        ctx / "summaries" / "budget_code_forecast_context.jsonl",
        [
            {
                "budget_code_key": CODE,
                "actuals": {"actual_cost_all_source_to_date": "500.00", "monthly_actuals": []},
                "budget_amounts": {
                    "projected_budget": "1000.00",
                    "revised_budget": "1000.00",
                    "current_projected_cost": "1000.00",
                    "committed_costs": "800.00",
                    "original_budget_amount": "1000.00",
                    "projected_costs": "1000.00",
                    "estimated_cost_at_completion": "1000.00",
                    "forecast_to_complete": "500.00",
                },
                "recommended_cost_to_complete": "500.00",
            }
        ],
    )
    _w(ctx / "manifest.json", _manifest(ctx.name))
    intel = root / "forecast_accuracy_next_package_tropical_20260101_000000"
    _w(
        intel / "forecast_recommendations_by_budget_code.jsonl",
        [
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
            }
        ],
    )
    for f in (
        "dormant_code_status_by_budget_code.jsonl",
        "trend_evidence_by_budget_code.jsonl",
        "schedule_forecast_evidence_by_budget_code.jsonl",
        "forecast_confidence_by_budget_code.jsonl",
    ):
        _w(intel / f, [])
    _w(intel / "manifest.json", _manifest(intel.name))
    mo = root / "forecast_monthly_package_tropical_20260101_000000"
    _w(
        mo / "monthly_forecast_confidence_by_budget_code.jsonl",
        [{"budget_code_key": CODE, "monthly_distribution_score": "0.6"}],
    )
    _w(
        mo / "remaining_work_monthly_distribution_by_budget_code.jsonl",
        [
            {
                "budget_code_key": CODE,
                "monthly_distribution_weights": [{"month": "2026-06", "weight": "1.0"}],
            }
        ],
    )
    _w(mo / "manifest.json", _manifest(mo.name))
    cf = root / "forecast_cost_frequency_package_tropical_20260101_000000"
    for f in (
        "cost_frequency_by_budget_code.jsonl",
        "frequency_adjusted_monthly_phasing_by_budget_code.jsonl",
        "internal_staffing_daily_rate_by_budget_code.jsonl",
    ):
        _w(cf / f, [{"budget_code_key": CODE}])
    _w(cf / "manifest.json", _manifest(cf.name))
    return root


def _setup(tmp_path: Path, monkeypatch):
    cfg_root = _build_config_root(tmp_path / "config_root")
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "reg.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    cr.import_forecast_config_to_db(
        config_root=cfg_root, db_path=db, project_key="tropical", import_run_id="p20a"
    )
    snap = cr.create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="p20a", snapshot_reason="proof"
    )
    _c = sqlite3.connect(str(db))
    _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    _c.close()
    data_root = _build_data_root(tmp_path / "data")
    monkeypatch.setattr(cli, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(gen, "SUBPROJECT_ROOT", cfg_root)
    monkeypatch.setattr(db_inventory, "resolve_db_path", lambda cfg: tmp_path / "no_inv.sqlite")
    return db, snap, data_root, cfg_root


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("require_item_count", None)
    kw.setdefault("preflight_stability_seconds", 0.0)
    return p20.run_forecast_comprehensive_db_config_proof(
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
    assert rep["decision"] == p20.DECISION_READY
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
    real = p20._live_db_state
    n = {"i": 0}

    def drifting(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        s["logical"]["data_version"] = n["i"]
        return s

    monkeypatch.setattr(p20, "_live_db_state", drifting)
    with pytest.raises(p20.ForecastComprehensiveDbConfigProofError, match="live_db_not_quiescent"):
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)


def test_during_run_drift_not_ready(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    real = p20._live_db_state
    n = {"i": 0}

    def drift_after(path, conn, *, db_inventory_tables):
        s = copy.deepcopy(real(path, conn, db_inventory_tables=db_inventory_tables))
        n["i"] += 1
        if n["i"] >= 3:
            s["logical"]["data_version"] += 1000
        return s

    monkeypatch.setattr(p20, "_live_db_state", drift_after)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert rep["decision"] == p20.DECISION_NOT_READY
    assert rep["not_ready_reason"] == p20.NOT_READY_REASON_LIVE_DB_MUTATED
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
