"""Phase 2c — decision-support coverage tests (method eligibility / model selection).

Proves the forecast_accuracy package projects per-method run rollups into the v66 tables:
eligibility status from applicable-count + reliability, and model-selection mean effective
weight. Fail-closed on the live DB; idempotent.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.forecast import decision_support_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT_KEY = "tropical"


def _migrated_db(root: Path) -> Path:
    db = root / "ds_cov.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES ('r1','tropical','t')")
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


def _accuracy_pkg(root: Path) -> Path:
    pkg = root / "forecast_accuracy_package_tropical_s"
    pkg.mkdir(parents=True)
    est = [
        {"budget_code_key": "01-100", "estimates": [
            {"method": "burn_rate", "applicable": True, "reliability": "medium"},
            {"method": "cpi_proxy", "applicable": False},
        ]},
        {"budget_code_key": "02-200", "estimates": [
            {"method": "burn_rate", "applicable": True, "reliability": "low"},
            {"method": "cpi_proxy", "applicable": False},
        ]},
    ]
    pkg.joinpath("eac_estimates_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in est) + "\n", encoding="utf-8"
    )
    rec = [
        {"budget_code_key": "01-100", "contributions": [{"method": "burn_rate", "effective_weight": "0.6300"}]},
        {"budget_code_key": "02-200", "contributions": [{"method": "burn_rate", "effective_weight": "0.7700"}]},
    ]
    pkg.joinpath("forecast_reconciliation_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rec) + "\n", encoding="utf-8"
    )
    return pkg


def test_apply_projects_method_rollups_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        apkg, accpkg = _analysis_pkg(root), _accuracy_pkg(root)
        plan = eng.project_decision_support(
            db_path=db, analysis_package=apkg, project_key=PROJECT_KEY, run_id="r1",
            apply=True, parity=True, accuracy_package=accpkg,
        )
        assert plan["ok"] is True
        assert plan["written"]["method_eligibility"] == 2  # burn_rate, cpi_proxy
        assert plan["written"]["model_selection"] == 1  # burn_rate only
        assert plan["parity"]["proven"] is True

        conn = sqlite3.connect(str(db))
        elig = dict(conn.execute(
            "SELECT method, status FROM forecast_method_eligibility WHERE run_id='r1'"
        ).fetchall())
        weight = conn.execute(
            "SELECT weight FROM forecast_model_selection_decisions WHERE run_id='r1' AND method='burn_rate'"
        ).fetchone()[0]
        conn.close()
        assert elig["burn_rate"] == "eligible_weighted"  # has a medium-reliability code
        assert elig["cpi_proxy"] == "rejected_missing_data"  # applicable for 0 codes
        assert weight == "0.7000"  # mean of 0.6300 and 0.7700

        # idempotent
        eng.project_decision_support(
            db_path=db, analysis_package=apkg, project_key=PROJECT_KEY, run_id="r1",
            apply=True, accuracy_package=accpkg,
        )
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_method_eligibility").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM forecast_model_selection_decisions").fetchone()[0] == 1
        conn.close()


def test_apply_refuses_live_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        apkg, accpkg = _analysis_pkg(root), _accuracy_pkg(root)
        plan = eng.project_decision_support(
            db_path=PathPolicy().get_db_path(), analysis_package=apkg, project_key=PROJECT_KEY,
            run_id="r1", apply=True, accuracy_package=accpkg,
        )
        assert plan["ok"] is False and plan["reason"] == "refuses_live_db"


def test_without_accuracy_package_no_method_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        apkg = _analysis_pkg(root)
        plan = eng.project_decision_support(
            db_path=db, analysis_package=apkg, project_key=PROJECT_KEY, run_id="r1", apply=True,
        )
        assert plan["written"]["method_eligibility"] == 0
        assert plan["written"]["model_selection"] == 0
