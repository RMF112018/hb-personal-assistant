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
from hb_assistant.construction.analytics.forecast_run_readmodel import (
    ForecastRunReadModelService,
)
from hb_assistant.construction.forecast import output_projection_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT_KEY = "tropical"


def _default_recs() -> list[dict]:
    # EAC = 125000 + 80000 = 205000.00; CTC = 25000 + 0 = 25000.00;
    # budget = 100000 + 80000 = 180000.00; variance_to_budget = 205000 - 180000 = 25000.00
    return [
        {
            "project_key": PROJECT_KEY,
            "budget_code_key": "01-100",
            "cost_code": "01-100",
            "category": "GC",
            "forecast_action": "increase_forecast",
            "budget_amount": "100000.00",
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
            "budget_amount": "80000.00",
            "recommended_projected_cost": "80000.00",
            "recommended_cost_to_complete": "0.00",
            "confidence": "moderate",
        },
    ]


def _make_analysis_package(
    root: Path, *, stamp: str = "20260622_120000", recs: list[dict] | None = None
) -> Path:
    pkg = root / f"forecast_analysis_package_tropical_{stamp}"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": PROJECT_KEY, "stamp": stamp}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": 2, "risk_count": 1}), encoding="utf-8"
    )
    if recs is None:
        recs = _default_recs()
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
        # analysis-only run: the coverage tables (monthly/probability/changes/staffing) stay 0
        assert {k: plan["counts"][k] for k in ("outputs", "budget_codes", "risks")} == {
            "outputs": 1,
            "budget_codes": 2,
            "risks": 1,
        }
        assert all(
            plan["counts"][k] == 0 for k in ("monthly", "probability", "changes", "staffing")
        )
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
        assert {k: plan["written"][k] for k in ("outputs", "budget_codes", "risks")} == {
            "outputs": 1,
            "budget_codes": 2,
            "risks": 1,
        }
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


# -- P1: header totals + prior-run deltas ------------------------------------------------


def test_header_aggregates_per_code_costs_in_plan() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(analysis_package=pkg, project_key=PROJECT_KEY)
        header = plan["planned"]["outputs"][0]
        assert header["estimated_final_cost"] == "205000.00"
        assert header["forecast_at_completion"] == "205000.00"
        assert header["cost_to_complete"] == "25000.00"
        assert header["variance_to_budget"] == "25000.00"
        # prior delta is DB-derived; a package-only plan leaves it null
        assert header["variance_to_prior_forecast"] is None
        # totals live in dedicated columns only — header raw_json stays a manifest+summary echo
        assert "estimated_final_cost" not in json.loads(header["raw_json"])


def test_header_aggregation_skips_missing_values_and_warns() -> None:
    recs = _default_recs()
    recs[1]["recommended_projected_cost"] = None  # one code missing the projected cost
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td), recs=recs)
        plan = eng.plan_run_output_projection(analysis_package=pkg, project_key=PROJECT_KEY)
        header = plan["planned"]["outputs"][0]
        # EAC aggregates only the parseable code (125000); CTC unaffected (25000 + 0)
        assert header["estimated_final_cost"] == "125000.00"
        assert header["cost_to_complete"] == "25000.00"
        assert any("missing recommended_projected_cost" in w for w in plan["warnings"])


def test_apply_persists_header_totals() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        db = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(db)).apply()
        plan = eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=db, parity=True
        )
        assert plan["ok"] is True
        assert plan["parity"]["proven"] is True
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT estimated_final_cost, forecast_at_completion, cost_to_complete, "
            "variance_to_budget, variance_to_prior_forecast FROM forecast_outputs"
        ).fetchone()
        conn.close()
        # EAC == FAC == sum(recommended_projected_cost); CTC == sum(recommended_cost_to_complete);
        # variance_to_budget == EAC - sum(budget_amount); no prior run -> prior delta null.
        assert row == ("205000.00", "205000.00", "25000.00", "25000.00", None)


def test_prior_run_delta_and_current_vs_prior_change_row() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(db)).apply()
        seed = sqlite3.connect(str(db))
        seed.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            ("run-A", PROJECT_KEY, "2026-01-01T00:00:00+00:00"),
        )
        seed.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            ("run-B", PROJECT_KEY, "2026-02-01T00:00:00+00:00"),
        )
        seed.commit()
        seed.close()

        pkg_a = _make_analysis_package(Path(td), stamp="20260101_000000")
        eng.project_run_output(
            analysis_package=pkg_a,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=db,
            run_id="run-A",
            now_utc="2026-01-01T00:00:00+00:00",
        )
        # Run B: same project, different package -> different output_id, higher EAC (210000).
        recs_b = _default_recs()
        recs_b[0]["recommended_projected_cost"] = "130000.00"  # 130000 + 80000 = 210000
        pkg_b = _make_analysis_package(Path(td), stamp="20260201_000000", recs=recs_b)
        plan_b = eng.project_run_output(
            analysis_package=pkg_b,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=db,
            run_id="run-B",
            now_utc="2026-02-01T00:00:00+00:00",
            parity=True,
        )
        assert plan_b["ok"] is True
        assert plan_b["parity"]["proven"] is True

        conn = sqlite3.connect(str(db))
        # header prior delta = B.EAC - A.EAC = 210000 - 205000 = 5000.00
        prior_delta = conn.execute(
            "SELECT variance_to_prior_forecast FROM forecast_outputs WHERE output_id = ?",
            (plan_b["output_id"],),
        ).fetchone()[0]
        # a project-level current_vs_prior change row links to the prior run
        change = conn.execute(
            "SELECT budget_code_key, delta_amount, prior_run_id FROM forecast_output_changes "
            "WHERE output_id = ? AND change_type = 'current_vs_prior'",
            (plan_b["output_id"],),
        ).fetchall()
        conn.close()
        assert prior_delta == "5000.00"
        assert change == [(None, "5000.00", "run-A")]


def test_first_run_has_no_prior_delta() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        db = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(db)).apply()
        eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=db
        )
        conn = sqlite3.connect(str(db))
        delta = conn.execute("SELECT variance_to_prior_forecast FROM forecast_outputs").fetchone()[
            0
        ]
        eac = conn.execute("SELECT estimated_final_cost FROM forecast_outputs").fetchone()[0]
        n_prior = conn.execute(
            "SELECT COUNT(*) FROM forecast_output_changes WHERE change_type = 'current_vs_prior'"
        ).fetchone()[0]
        conn.close()
        # first run: prior delta null, no current_vs_prior row, but EAC still populated
        assert delta is None
        assert n_prior == 0
        assert eac == "205000.00"


def test_readmodel_surfaces_header_totals() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        db = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(db)).apply()
        eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=db
        )
        svc = ForecastRunReadModelService(db_path=str(db))
        outputs = svc.list_outputs(PROJECT_KEY)["outputs"]
        assert len(outputs) == 1
        o = outputs[0]
        assert o["estimated_final_cost"] == "205000.00"
        assert o["cost_to_complete"] == "25000.00"
        assert o["variance_to_budget"] == "25000.00"


def test_apply_writes_no_output_package() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        db = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(db)).apply()

        def _files() -> set[str]:
            return {
                str(p)
                for p in Path(td).rglob("*")
                if p.is_file() and not p.name.startswith(db.name)
            }

        before = _files()
        eng.project_run_output(
            analysis_package=pkg, project_key=PROJECT_KEY, apply=True, db_path=db
        )
        # Forecast generation persists to the DB only — no output/export package files.
        assert _files() == before
