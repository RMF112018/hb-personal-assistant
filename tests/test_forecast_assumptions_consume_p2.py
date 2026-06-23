"""P2 — operator-assumption consumption in the decision-support engine.

Proves: the v66 reader returns only project-scoped (run_id IS NULL) rows; pre-hydrated
operator assumptions add confidence-modifier factors (raises->booster, lowers->penalty) on
the matching scorecard; unsatisfied required assumptions add a project penalty factor + a
warning; with the flag OFF (default) the planned output is byte-identical to before and a
flag-ON run against a DB with no assumptions is identical too; the project_decision_support
bridge reads assumptions read-only from an explicit (non-live) DB and the result is
redaction-safe. No network, no CFR import, no live-DB write.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.analytics.forecast_runtime_config import (
    ENV_ASSUMPTION_CONSUMPTION_ENABLED,
)
from hb_assistant.construction.forecast import assumptions_repository as assume
from hb_assistant.construction.forecast import decision_support_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT_KEY = "tropical"


def _seed_db(db: Path) -> None:
    """A minimal v59/v63 fixture (M4, two per-code scorecards) — mirrors phase2b."""
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            ("r1", PROJECT_KEY, "t"),
        )
        for i in range(5):
            key = f"01-{100 + i}"
            conn.execute(
                "INSERT INTO forecast_budget_details "
                "(project_key, budget_code_key, source_package, raw_json, created_utc) "
                "VALUES (?,?,?,?,?)",
                (PROJECT_KEY, key, "pkg", json.dumps({"budget_code_key": key}), "t"),
            )
        for m in range(1, 7):
            month = f"2026-{m:02d}"
            conn.execute(
                "INSERT INTO forecast_monthly_actuals_by_budget_code "
                "(project_key, budget_code_key, month, type, source_package, amount, raw_json, created_utc) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (PROJECT_KEY, "01-100", month, "actual", "pkg", 1000.0,
                 json.dumps({"month": month}), "t"),
            )
        conn.execute(
            "INSERT INTO forecast_outputs "
            "(output_id, project_key, source_package, raw_json, created_utc) VALUES (?,?,?,?,?)",
            ("out1", PROJECT_KEY, "pkg", json.dumps({}), "t"),
        )
        for i, conf in enumerate(("high", "low")):
            key = f"01-{100 + i}"
            conn.execute(
                "INSERT INTO forecast_output_budget_codes "
                "(id, output_id, project_key, budget_code_key, forecast_action, confidence, "
                " source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"bc{i}", "out1", PROJECT_KEY, key, "hold", conf, i + 1,
                 json.dumps({"budget_code_key": key, "confidence": conf}), "t"),
            )
        conn.commit()
    finally:
        conn.close()


def _make_analysis_package(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_20260622_120000"
    pkg.mkdir(parents=True)
    (pkg / "confidence_rollup.json").write_text(
        json.dumps({"count_by_confidence": {"high": 1, "low": 1}}), encoding="utf-8"
    )
    return pkg


def _insert_operator_assumption(
    conn: sqlite3.Connection, *, aid: str, run_id, atype: str, impact, code=None, value=None
) -> None:
    conn.execute(
        "INSERT INTO forecast_operator_assumptions "
        "(assumption_id, run_id, project_key, assumption_type, budget_code_key, value, "
        " confidence_impact, is_required, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (aid, run_id, PROJECT_KEY, atype, code, value, impact, 0,
         json.dumps({"assumption_type": atype}), "t"),
    )


def _insert_required_assumption(
    conn: sqlite3.Connection, *, rid: str, run_id, atype: str, satisfied: int
) -> None:
    conn.execute(
        "INSERT INTO forecast_required_assumptions "
        "(id, run_id, project_key, assumption_type, reason, satisfied, raw_json, created_utc) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (rid, run_id, PROJECT_KEY, atype, "needs sign-off", satisfied,
         json.dumps({"reason": "needs sign-off"}), "t"),
    )


# --- reader -----------------------------------------------------------------------------


def test_reader_returns_only_project_scoped_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "a.db"
        _seed_db(db)
        conn = sqlite3.connect(str(db))
        _insert_operator_assumption(conn, aid="op-null", run_id=None, atype="labor_rate", impact="raises")
        _insert_operator_assumption(conn, aid="op-run", run_id="r1", atype="labor_rate", impact="raises")
        _insert_required_assumption(conn, rid="rq-null", run_id=None, atype="escalation", satisfied=0)
        _insert_required_assumption(conn, rid="rq-run", run_id="r1", atype="escalation", satisfied=0)
        conn.commit()
        ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            ops = assume.read_operator_assumptions_from_db(ro, project_key=PROJECT_KEY)
            reqs = assume.read_required_assumptions_from_db(ro, project_key=PROJECT_KEY)
            unsat = assume.unsatisfied_required_assumptions(ro, project_key=PROJECT_KEY)
        finally:
            ro.close()
            conn.close()
        assert [o["assumption_id"] for o in ops] == ["op-null"]
        assert [r["id"] for r in reqs] == ["rq-null"]
        assert [r["id"] for r in unsat] == ["rq-null"]


# --- confidence modifiers + required gate (pre-hydrated planner) -------------------------


def _plan(td: str, *, operator=None, required=None, now_utc="2026-01-01T00:00:00+00:00"):
    db = Path(td) / "ds.db"
    _seed_db(db)
    pkg = _make_analysis_package(Path(td))
    return eng.plan_decision_support(
        db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1", now_utc=now_utc,
        operator_assumptions=operator, required_assumptions=required,
    )


def test_confidence_modifier_factors_emitted() -> None:
    with tempfile.TemporaryDirectory() as td:
        plan = _plan(
            td,
            operator=[
                {"assumption_type": "labor_rate", "confidence_impact": "raises",
                 "budget_code_key": "01-100"},
                {"assumption_type": "scope_risk", "confidence_impact": "lowers"},
                {"assumption_type": "noop", "confidence_impact": None},
            ],
        )
        factors = {f["factor_key"]: f for f in plan["planned"]["factors"]}
        assert factors["operator_assumption:labor_rate"]["direction"] == "booster"
        assert factors["operator_assumption:scope_risk"]["direction"] == "penalty"
        # the per-code modifier attaches to that code's scorecard
        code_sid = f"fcs-{eng._hash('r1|budget_code|01-100')[:32]}"
        assert factors["operator_assumption:labor_rate"]["scorecard_id"] == code_sid
        # the no-impact assumption emits no factor
        assert "operator_assumption:noop" not in factors


def test_required_gate_emits_penalty_and_warning() -> None:
    with tempfile.TemporaryDirectory() as td:
        plan = _plan(
            td,
            required=[
                {"id": "rq1", "assumption_type": "escalation", "satisfied": False,
                 "reason": "needs sign-off"},
                {"id": "rq2", "assumption_type": "done", "satisfied": True},
            ],
        )
        factors = {f["factor_key"]: f for f in plan["planned"]["factors"]}
        gate = factors["required_assumption_unsatisfied:escalation"]
        assert gate["direction"] == "penalty"
        project_sid = f"fcs-{eng._hash('r1|project|project')[:32]}"
        assert gate["scorecard_id"] == project_sid
        assert any("escalation" in w and "unsatisfied" in w for w in plan["warnings"])
        # a satisfied required assumption produces no gate factor
        assert "required_assumption_unsatisfied:done" not in factors


def test_flag_off_byte_identical_baseline() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = _plan(td)  # no assumption params
    with tempfile.TemporaryDirectory() as td:
        empty = _plan(td, operator=[], required=[])  # empty lists = no-op
    assert json.dumps(base["planned"], sort_keys=True) == json.dumps(empty["planned"], sort_keys=True)


# --- bridge (project_decision_support reads assumptions read-only) -----------------------


def test_flag_on_zero_assumptions_identical(monkeypatch) -> None:
    fixed = "2026-01-01T00:00:00+00:00"
    monkeypatch.setenv(ENV_ASSUMPTION_CONSUMPTION_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db)
        pkg = _make_analysis_package(Path(td))
        on = eng.project_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, run_id="r1", now_utc=fixed,
            assumptions_db_path=db,  # seeded DB has the v66 tables but no assumption rows
        )
    monkeypatch.delenv(ENV_ASSUMPTION_CONSUMPTION_ENABLED, raising=False)
    with tempfile.TemporaryDirectory() as td:
        off = _plan(td, now_utc=fixed)
    assert json.dumps(on["planned"], sort_keys=True) == json.dumps(off["planned"], sort_keys=True)


def test_project_decision_support_consumes_and_persists(monkeypatch) -> None:
    monkeypatch.setenv(ENV_ASSUMPTION_CONSUMPTION_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ds.db"
        _seed_db(db)
        conn = sqlite3.connect(str(db))
        _insert_operator_assumption(conn, aid="op1", run_id=None, atype="labor_rate", impact="raises")
        _insert_required_assumption(conn, rid="rq1", run_id=None, atype="escalation", satisfied=0)
        conn.commit()
        conn.close()
        pkg = _make_analysis_package(Path(td))
        plan = eng.project_decision_support(
            db_path=db, analysis_package=pkg, project_key=PROJECT_KEY, apply=True, parity=True,
            run_id="r1", assumptions_db_path=db,
        )
        assert plan["ok"] is True
        assert plan["parity"]["proven"] is True
        rdb = sqlite3.connect(str(db))
        keys = {
            r[0]
            for r in rdb.execute("SELECT factor_key FROM forecast_confidence_factors").fetchall()
        }
        rdb.close()
        assert "operator_assumption:labor_rate" in keys
        assert "required_assumption_unsatisfied:escalation" in keys
