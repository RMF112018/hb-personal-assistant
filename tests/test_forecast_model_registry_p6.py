"""P6 — model-registry governance tests.

Proves that, behind ``HB_FORECAST_MODEL_GOVERNANCE_ENABLED``, the decision-support apply path
persists model-registry provenance from an accuracy package's model_methodology.json + calibration
snapshot: a deduped model-version row, the per-run linkage, and per-method calibration provenance
whose ``calibration_source`` correctly distinguishes backtested / not-backtested / reliability-only
methods. Flag-off is byte-identical (no model-registry rows). Fail-closed when the methodology is
absent. Writes only ever target a NON-LIVE temp DB.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.forecast import decision_support_engine as eng
from hb_assistant.construction.forecast import model_registry_repository as mrr
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT_KEY = "tropical"
FLAG = "HB_FORECAST_MODEL_GOVERNANCE_ENABLED"

_INDEPENDENT = ["burn_rate", "owner_percent_complete", "commitment_floor", "schedule_etc", "cpi_proxy"]
_ERP = ["baseline_projected", "baseline_erp_eac"]
_ORDER = _ERP + _INDEPENDENT
_BACKTEST = ["burn_rate", "owner_percent_complete", "commitment_floor", "cpi_proxy"]


def _migrated_db(root: Path) -> Path:
    db = root / "mr.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES ('r1','tropical','t')")
    conn.execute("INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES ('r2','tropical','t')")
    conn.commit()
    conn.close()
    return db


def _analysis_pkg(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_s"
    pkg.mkdir(parents=True)
    pkg.joinpath("confidence_rollup.json").write_text(
        json.dumps({"count_by_confidence": {"high": 1}}), encoding="utf-8"
    )
    return pkg


def _methodology() -> dict:
    body = {
        "schema_version": 1,
        "independent_methods": _INDEPENDENT,
        "erp_methods": _ERP,
        "estimator_order": _ORDER,
        "reliability_weights": {"high": "1.0", "medium": "0.6", "low": "0.3"},
        "thresholds": {"owner_pct_floor": "0.05"},
        "cohort": {"gold_owner_pct": "0.95", "backtest_methods": _BACKTEST},
    }
    body["methodology_sha256"] = "a" * 64
    body["version_label"] = "methodology-aaaaaaaaaaaa"
    return body


def _accuracy_pkg(root: Path, name: str = "forecast_accuracy_package_tropical_20260101_000000") -> Path:
    pkg = root / name
    (pkg / "audit").mkdir(parents=True)
    # method-rollup inputs (reuses the existing decision-support coverage shape)
    est = [
        {"budget_code_key": "01-100", "estimates": [
            {"method": "burn_rate", "applicable": True, "reliability": "medium"},
        ]},
    ]
    pkg.joinpath("eac_estimates_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in est) + "\n", encoding="utf-8"
    )
    rec = [
        {"budget_code_key": "01-100", "contributions": [{"method": "burn_rate", "effective_weight": "0.6000"}]},
    ]
    pkg.joinpath("forecast_reconciliation_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rec) + "\n", encoding="utf-8"
    )
    # P6 model methodology + calibration snapshot
    pkg.joinpath("model_methodology.json").write_text(json.dumps(_methodology()), encoding="utf-8")
    pkg.joinpath("audit", "calibration_snapshot.json").write_text(
        json.dumps({
            "cohort_size": 5,
            "summary_by_method": [
                {"method": m, "n": 5, "mape": "0.1200", "mean_bias": "0.0100"} for m in _BACKTEST
            ],
            "calibration_weights": dict.fromkeys(_BACKTEST, "1.0500"),
        }),
        encoding="utf-8",
    )
    return pkg


def test_governance_on_persists_registry_provenance(monkeypatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        apkg, accpkg = _analysis_pkg(root), _accuracy_pkg(root)
        plan = eng.project_decision_support(
            db_path=db, analysis_package=apkg, project_key=PROJECT_KEY, run_id="r1",
            apply=True, accuracy_package=accpkg,
        )
        assert plan["ok"] is True
        prov = plan["model_provenance"]
        assert prov["methodology_sha256"] == "a" * 64
        assert prov["version_label"] == "methodology-aaaaaaaaaaaa"
        assert prov["calibration_methods"] == 7

        conn = sqlite3.connect(str(db))
        # registry header: one row, deduped by sha
        assert conn.execute("SELECT COUNT(*) FROM forecast_model_versions").fetchone()[0] == 1
        # per-run linkage records the methodology + the accuracy-package stamp (separate provenance)
        rmv = conn.execute(
            "SELECT model_version_id, version_label, accuracy_package_stamp "
            "FROM forecast_run_model_versions WHERE run_id='r1'"
        ).fetchone()
        assert rmv[0] == "a" * 64 and rmv[1] == "methodology-aaaaaaaaaaaa"
        assert rmv[2] == "20260101_000000"
        # per-method calibration provenance: source mapping
        src = dict(conn.execute(
            "SELECT method, calibration_source FROM forecast_calibration_weights WHERE run_id='r1'"
        ).fetchall())
        conn.close()
        assert src["burn_rate"] == "backtest"
        assert src["schedule_etc"] == "not_backtested"
        assert src["baseline_projected"] == "reliability_only"
        assert src["baseline_erp_eac"] == "reliability_only"
        # the method-rollup tables still populate (existing behavior, unaffected)
        assert plan["written"]["method_eligibility"] >= 1


def test_governance_off_writes_no_registry_rows(monkeypatch) -> None:
    monkeypatch.delenv(FLAG, raising=False)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        apkg, accpkg = _analysis_pkg(root), _accuracy_pkg(root)
        plan = eng.project_decision_support(
            db_path=db, analysis_package=apkg, project_key=PROJECT_KEY, run_id="r1",
            apply=True, accuracy_package=accpkg,
        )
        assert plan["ok"] is True
        assert "model_provenance" not in plan  # byte-identical: no governance side effects
        conn = sqlite3.connect(str(db))
        for t in ("forecast_model_versions", "forecast_run_model_versions", "forecast_calibration_weights"):
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        # method rollups still populate regardless of governance
        assert conn.execute("SELECT COUNT(*) FROM forecast_method_eligibility").fetchone()[0] >= 1
        conn.close()


def test_governance_idempotent_and_dedup(monkeypatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        apkg, accpkg = _analysis_pkg(root), _accuracy_pkg(root)
        kw = {"db_path": db, "analysis_package": apkg, "project_key": PROJECT_KEY,
              "apply": True, "accuracy_package": accpkg}
        eng.project_decision_support(run_id="r1", **kw)
        eng.project_decision_support(run_id="r1", **kw)  # idempotent re-run
        eng.project_decision_support(run_id="r2", **kw)  # second run, same methodology
        conn = sqlite3.connect(str(db))
        # one methodology shared by both runs -> single registry row
        assert conn.execute("SELECT COUNT(*) FROM forecast_model_versions").fetchone()[0] == 1
        # two distinct run linkages
        assert conn.execute("SELECT COUNT(*) FROM forecast_run_model_versions").fetchone()[0] == 2
        # 7 calibration rows per run, idempotent for r1
        assert conn.execute(
            "SELECT COUNT(*) FROM forecast_calibration_weights WHERE run_id='r1'"
        ).fetchone()[0] == 7
        conn.close()


def test_governance_on_fail_closed_without_methodology(monkeypatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        apkg = _analysis_pkg(root)
        # accuracy package WITHOUT model_methodology.json
        bare = root / "forecast_accuracy_package_tropical_bare"
        bare.mkdir()
        bare.joinpath("eac_estimates_by_budget_code.jsonl").write_text("", encoding="utf-8")
        plan = eng.project_decision_support(
            db_path=db, analysis_package=apkg, project_key=PROJECT_KEY, run_id="r1",
            apply=True, accuracy_package=bare,
        )
        assert plan["ok"] is False
        assert plan["reason"] == "model_governance_requires_accuracy_methodology"
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_model_versions").fetchone()[0] == 0
        conn.close()


def test_build_provenance_rows_is_pure(tmp_path) -> None:
    accpkg = _accuracy_pkg(tmp_path)
    mv, rmv, cals = mrr.build_provenance_rows(
        run_id="rX", project_key=PROJECT_KEY, accuracy_package=accpkg, now_utc="now",
    )
    assert mv["model_version_id"] == "a" * 64
    assert rmv["run_id"] == "rX"
    assert len(cals) == 7
    backtest = [c for c in cals if c["calibration_source"] == "backtest"]
    assert {c["method"] for c in backtest} == set(_BACKTEST)
    assert all(c["calibration_weight"] == "1.0500" for c in backtest)


def test_missing_methodology_raises() -> None:
    with tempfile.TemporaryDirectory() as td:
        bare = Path(td) / "pkg"
        bare.mkdir()
        with pytest.raises(mrr.ModelMethodologyMissingError):
            mrr.build_provenance_rows(
                run_id="r", project_key=PROJECT_KEY, accuracy_package=bare, now_utc="now",
            )
