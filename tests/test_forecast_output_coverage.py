"""Phase 2c — output projector coverage tests (monthly / probability / changes / staffing).

Proves the optional downstream packages project into their v63 tables under the analysis-derived
output_id; dry-run writes nothing; apply refuses the live DB; idempotent with parity. The
existing analysis-only behavior (no extra packages) is unchanged and covered by phase2a tests.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.forecast import output_projection_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT_KEY = "tropical"


def _analysis_pkg(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_20260622_120000"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"project_key": PROJECT_KEY, "stamp": "s"}), encoding="utf-8")
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(json.dumps({}), encoding="utf-8")
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text("", encoding="utf-8")
    (pkg / "forecast_risk_register.jsonl").write_text("", encoding="utf-8")
    return pkg


def _monthly_pkg(root: Path) -> Path:
    pkg = root / "forecast_monthly_package_tropical_s"
    pkg.mkdir(parents=True)
    rows = [
        {"budget_code_key": "01-100", "forecast_month": "2026-07", "recommended_month_cost": "1000.00"},
        {"budget_code_key": "01-100", "forecast_month": "2026-08", "recommended_month_cost": "2000.00"},
    ]
    (pkg / "monthly_forecast_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return pkg


def _probability_pkg(root: Path) -> Path:
    pkg = root / "forecast_probability_package_tropical_s"
    pkg.mkdir(parents=True)
    rows = [{"budget_code_key": "01-100", "simulated_p10": "90.00", "simulated_p50": "100.00", "simulated_p90": "120.00"}]
    (pkg / "probabilistic_final_cost_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return pkg


def _comprehensive_pkg(root: Path) -> Path:
    pkg = root / "forecast_comprehensive_package_tropical_s"
    pkg.mkdir(parents=True)
    rows = [{"budget_code_key": "01-100", "change_amount": "500.00", "reason_codes": ["x"]}]
    (pkg / "integrated_change_explanation.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return pkg


def _staffing_pkg(root: Path) -> Path:
    pkg = root / "forecast_staffing_plan_package_tropical_s"
    pkg.mkdir(parents=True)
    rows = [{
        "budget_code_key": "01-100.LAB",
        "staffing_plan_implied_monthly_forecast": [
            {"forecast_month": "2026-07", "amount": "5000.00"},
            {"forecast_month": "2026-08", "amount": "5000.00"},
        ],
    }]
    (pkg / "staffing_plan_monthly_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return pkg


def _migrated_db(root: Path) -> Path:
    db = root / "cov.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES ('r1','tropical','t')")
    conn.commit()
    conn.close()
    return db


def _all_pkgs(root: Path):
    return dict(
        analysis_package=_analysis_pkg(root),
        monthly_package=_monthly_pkg(root),
        probability_package=_probability_pkg(root),
        comprehensive_package=_comprehensive_pkg(root),
        staffing_package=_staffing_pkg(root),
    )


def test_plan_projects_all_coverage_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        pkgs = _all_pkgs(root)
        plan = eng.plan_run_output_projection(project_key=PROJECT_KEY, run_id="r1", **pkgs)
        assert plan["counts"]["monthly"] == 2
        assert plan["counts"]["probability"] == 1
        assert plan["counts"]["changes"] == 1
        assert plan["counts"]["staffing"] == 2  # unrolled from one row's monthly list
        # all child rows share the analysis-derived output_id
        oid = plan["output_id"]
        assert all(r["output_id"] == oid for r in plan["planned"]["monthly"])


def test_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        pkgs = _all_pkgs(root)
        plan = eng.project_run_output(project_key=PROJECT_KEY, run_id="r1", db_path=db, apply=False, **pkgs)
        assert plan["mode"] == "dry_run" and "written" not in plan
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_monthly").fetchone()[0] == 0
        conn.close()


def test_apply_refuses_live_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkgs = _all_pkgs(root)
        plan = eng.project_run_output(
            project_key=PROJECT_KEY, run_id="r1", db_path=PathPolicy().get_db_path(), apply=True, **pkgs
        )
        assert plan["ok"] is False and plan["reason"] == "apply_refuses_live_db"


def test_apply_writes_with_parity_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _migrated_db(root)
        pkgs = _all_pkgs(root)
        plan = eng.project_run_output(
            project_key=PROJECT_KEY, run_id="r1", db_path=db, apply=True, parity=True, **pkgs
        )
        assert plan["ok"] is True
        assert plan["written"]["monthly"] == 2
        assert plan["written"]["probability"] == 1
        assert plan["written"]["changes"] == 1
        assert plan["written"]["staffing"] == 2
        assert plan["parity"]["proven"] is True

        eng.project_run_output(project_key=PROJECT_KEY, run_id="r1", db_path=db, apply=True, **pkgs)
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_monthly").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_staffing").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_probability").fetchone()[0] == 1
        # commitment_exposure / schedule_phasing remain empty (no source this phase)
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_commitment_exposure").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_schedule_phasing").fetchone()[0] == 0
        conn.close()
