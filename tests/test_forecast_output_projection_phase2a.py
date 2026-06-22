"""Phase 2a — read-only run-output projector tests.

Proves: plan is built purely from an analysis-package fixture (no DB); a dry-run touches no
DB; ``apply`` requires an explicit temp db_path and refuses the live DB (fail closed); and an
``apply`` into a temp v63 DB writes the expected rows with canonical read-parity and is
idempotent. No network, no CFR import, no live-DB write.
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


def _make_analysis_package(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_20260622_120000"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": PROJECT_KEY, "stamp": "20260622_120000"}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": 2, "risk_count": 1}), encoding="utf-8"
    )
    recs = [
        {
            "project_key": PROJECT_KEY,
            "budget_code_key": "01-100",
            "cost_code": "01-100",
            "category": "GC",
            "forecast_action": "increase_forecast",
            "recommended_projected_cost": "125000.00",
            "recommended_cost_to_complete": "25000.00",
            "confidence": "high",
        },
        {
            "project_key": PROJECT_KEY,
            "budget_code_key": "02-200",
            "cost_code": "02-200",
            "category": "Concrete",
            "forecast_action": "hold",
            "recommended_projected_cost": "80000.00",
            "recommended_cost_to_complete": "0.00",
            "confidence": "moderate",
        },
    ]
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8"
    )
    risks = [
        {
            "risk_id": "R-0001",
            "severity": "high",
            "budget_code_key": "01-100",
            "cost_code": "01-100",
            "category": "GC",
            "risk_type": "owner_progress_ahead_of_actuals",
            "description": "x",
        }
    ]
    (pkg / "forecast_risk_register.jsonl").write_text(
        "\n".join(json.dumps(r) for r in risks) + "\n", encoding="utf-8"
    )
    return pkg


def test_plan_reads_package_without_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(analysis_package=pkg, project_key=PROJECT_KEY)
        assert plan["ok"] is True
        assert plan["counts"] == {"outputs": 1, "budget_codes": 2, "risks": 1}
        assert plan["output_id"].startswith("fout-")


def test_dry_run_touches_no_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.project_run_output(analysis_package=pkg, project_key=PROJECT_KEY, apply=False)
        assert plan["mode"] == "dry_run"
        assert "written" not in plan


def test_dry_run_parity_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=False, parity=True
        )
        assert plan["ok"] is False
        assert plan["parity"]["proven"] is False
        assert plan["parity"]["reason"] == "parity_requires_applied_db"


def test_apply_requires_explicit_db_path() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=None
        )
        assert plan["ok"] is False
        assert plan["reason"] == "apply_requires_explicit_db_path"


def test_apply_refuses_live_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        live = PathPolicy().get_db_path()
        plan = eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=live
        )
        assert plan["ok"] is False
        assert plan["reason"] == "apply_refuses_live_db"
        assert "written" not in plan


def test_apply_writes_with_parity_and_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        db = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(db)).apply()

        plan = eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=db, parity=True
        )
        assert plan["ok"] is True
        assert plan["written"] == {"outputs": 1, "budget_codes": 2, "risks": 1}
        assert plan["parity"]["proven"] is True

        # Re-apply is idempotent: no duplicate rows.
        eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=db
        )
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_outputs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_budget_codes").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM forecast_output_risks").fetchone()[0] == 1
        conn.close()
