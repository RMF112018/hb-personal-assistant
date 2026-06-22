"""Phase 2b — read-only decision-support engine tests.

Proves: maturity tier is derived from completed-month count (M0/M1/M2/M4 cases); absent
domains are recorded "unavailable" (a penalty, not a block); the project confidence scorecard
is projected from confidence_rollup.json with persisted factors; per-code scorecards reuse the
v63 per-code confidence; dry-run writes nothing; apply requires a temp db_path and refuses the
live DB; apply is idempotent with parity. No network, no CFR import, no live-DB write.
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


def _seed_db(db: Path, *, months: int, budget_codes: int, with_outputs: bool) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        # The decision-support rows FK to forecast_runs(run_id); seed the run first.
        conn.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            ("r1", PROJECT_KEY, "t"),
        )
        for i in range(budget_codes):
            key = f"01-{100 + i}"
            conn.execute(
                "INSERT INTO forecast_budget_details "
                "(project_key, budget_code_key, source_package, raw_json, created_utc) "
                "VALUES (?,?,?,?,?)",
                (PROJECT_KEY, key, "pkg", json.dumps({"budget_code_key": key}), "t"),
            )
        for m in range(1, months + 1):
            month = f"2026-{m:02d}"
            conn.execute(
                "INSERT INTO forecast_monthly_actuals_by_budget_code "
                "(project_key, budget_code_key, month, type, source_package, amount, raw_json, created_utc) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (PROJECT_KEY, "01-100", month, "actual", "pkg", 1000.0,
                 json.dumps({"month": month}), "t"),
            )
        if with_outputs:
            conn.execute(
                "INSERT INTO forecast_outputs "
                "(output_id, project_key, source_package, raw_json, created_utc) "
                "VALUES (?,?,?,?,?)",
                ("out1", PROJECT_KEY, "pkg", json.dumps({}), "t"),
            )
            for i, conf in enumerate(("high", "low")):
                key = f"01-{100 + i}"
                conn.execute(
                    "INSERT INTO forecast_output_budget_codes "
                    "(id, output_id, project_key, budget_code_key, forecast_action, confidence, "
                    " source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"bc{i}", "out1", PROJECT_KEY, key, "hold", conf, i + 1,
                     json.dumps({"budget_code_key": key, "confidence": conf,
                                 "confidence_reason": f"reason-{conf}"}), "t"),
                )
        conn.commit()
    finally:
        conn.close()


def _make_analysis_package(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_20260622_120000"
    pkg.mkdir(parents=True)
    (pkg / "confidence_rollup.json").write_text(
        json.dumps(
            {
                "total_budget_codes": 2,
                "count_by_confidence": {"high": 1, "low": 1},
                "count_by_evidence_depth": {"actuals_only": 2},
                "count_with_neither_owner_nor_procore": 1,
            }
        ),
        encoding="utf-8",
    )
    return pkg


def test_maturity_tier_m0_when_no_actuals_no_budget() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db, months=0, budget_codes=0, with_outputs=False)
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1"
        )
        assert plan["planned"]["maturity"][0]["maturity_tier"] == "M0"


def test_maturity_tier_m1_when_budget_no_actuals() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db, months=0, budget_codes=5, with_outputs=False)
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1"
        )
        assert plan["planned"]["maturity"][0]["maturity_tier"] == "M1"


def test_maturity_tier_m2_then_m4() -> None:
    with tempfile.TemporaryDirectory() as td:
        db2 = Path(td) / "m2.db"
        _seed_db(db2, months=2, budget_codes=5, with_outputs=False)
        db4 = Path(td) / "m4.db"
        _seed_db(db4, months=6, budget_codes=5, with_outputs=False)
        pkg = _make_analysis_package(Path(td))
        m2 = eng.plan_decision_support(db_path=db2, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1")
        m4 = eng.plan_decision_support(db_path=db4, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1")
        assert m2["planned"]["maturity"][0]["maturity_tier"] == "M2"
        assert m4["planned"]["maturity"][0]["maturity_tier"] == "M4"


def test_absent_domains_marked_unavailable() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db, months=6, budget_codes=5, with_outputs=False)
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_decision_support(db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1")
        avail = {r["domain"]: r["availability"] for r in plan["planned"]["availability"]}
        assert avail["monthly_actuals"] == "available"
        assert avail["budget"] == "available"
        for absent in ("owner", "commitment", "schedule", "staffing"):
            assert avail[absent] == "unavailable"


def test_project_scorecard_has_factors() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db, months=6, budget_codes=5, with_outputs=True)
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_decision_support(db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1")
        project_cards = [s for s in plan["planned"]["scorecards"] if s["scope"] == "project"]
        assert len(project_cards) == 1
        assert project_cards[0]["label"] in ("high", "low")  # modal band
        # every scorecard must have >=1 factor (the persisted explanation)
        card_ids = {s["scorecard_id"] for s in plan["planned"]["scorecards"]}
        factor_card_ids = {f["scorecard_id"] for f in plan["planned"]["factors"]}
        assert card_ids <= factor_card_ids
        # per-code scorecards reuse v63 confidence
        code_cards = [s for s in plan["planned"]["scorecards"] if s["scope"] == "budget_code"]
        assert {c["label"] for c in code_cards} == {"high", "low"}


def test_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db, months=6, budget_codes=5, with_outputs=True)
        pkg = _make_analysis_package(Path(td))
        plan = eng.project_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, apply=False, run_id="r1"
        )
        assert plan["mode"] == "dry_run"
        assert "written" not in plan
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_project_maturity_snapshots").fetchone()[0] == 0
        conn.close()


def test_apply_refuses_live_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        live = PathPolicy().get_db_path()
        plan = eng.project_decision_support(
            db_path=live, analysis_package=pkg, project_key=PROJECT_KEY, apply=True, run_id="r1"
        )
        assert plan["ok"] is False
        assert plan["reason"] == "refuses_live_db"
        assert "written" not in plan


def test_apply_writes_with_parity_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db, months=6, budget_codes=5, with_outputs=True)
        pkg = _make_analysis_package(Path(td))
        plan = eng.project_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, apply=True, parity=True, run_id="r1"
        )
        assert plan["ok"] is True
        assert plan["written"]["maturity"] == 1
        assert plan["written"]["availability"] == 7  # 3 db domains + 4 absent
        assert plan["parity"]["proven"] is True

        eng.project_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, apply=True, run_id="r1"
        )
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM forecast_project_maturity_snapshots").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM forecast_data_availability_profiles").fetchone()[0] == 7
        assert conn.execute("SELECT maturity_tier FROM forecast_project_maturity_snapshots").fetchone()[0] == "M4"
        conn.close()
