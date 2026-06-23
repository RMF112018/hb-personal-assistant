"""P2b — operator dollar value-overrides in the run-output projector.

Proves: reserved override assumption_types (projected_cost_override / cost_to_complete_override)
mutate the matching per-code TYPED column and re-aggregate the EAC/CTC/variance header, keeping
the per-code raw_json as the original source echo; an operator_value_override change row is
emitted per applied override; null-key / unmatched / unparseable overrides are skipped with a
warning; with no overrides (or flag off) the planned output is byte-identical to baseline; the
project_run_output bridge reads overrides read-only from an explicit (non-live) DB, persists the
overridden values, proves parity, and the prior-run delta uses the overridden EAC. No network,
no CFR import, no live-DB write.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.analytics.forecast_runtime_config import (
    ENV_ASSUMPTION_OVERRIDES_ENABLED,
)
from hb_assistant.construction.forecast import assumptions_repository as assume
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


def _make_analysis_package(root: Path, *, stamp: str = "20260622_120000") -> Path:
    pkg = root / f"forecast_analysis_package_tropical_{stamp}"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": PROJECT_KEY, "stamp": stamp}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": 2, "risk_count": 0}), encoding="utf-8"
    )
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _default_recs()) + "\n", encoding="utf-8"
    )
    (pkg / "forecast_risk_register.jsonl").write_text("", encoding="utf-8")
    return pkg


def _override(atype: str, *, code, value) -> dict:
    return {"assumption_type": atype, "budget_code_key": code, "value": value, "source": "op-test"}


# --- planner-level overrides ------------------------------------------------------------


def test_projected_cost_override_updates_code_and_header() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            operator_assumptions=[
                _override("projected_cost_override", code="01-100", value="150000")
            ],
        )
        codes = {c["budget_code_key"]: c for c in plan["planned"]["budget_codes"]}
        assert (
            codes["01-100"]["recommended_projected_cost"] == "150000.00"
        )  # typed column overridden
        # raw_json stays the ORIGINAL source recommendation (parity-safe)
        assert json.loads(codes["01-100"]["raw_json"])["recommended_projected_cost"] == "125000.00"
        header = plan["planned"]["outputs"][0]
        # EAC = 150000 + 80000 = 230000; variance_to_budget = 230000 - 180000 = 50000
        assert header["estimated_final_cost"] == "230000.00"
        assert header["forecast_at_completion"] == "230000.00"
        assert header["variance_to_budget"] == "50000.00"
        assert header["cost_to_complete"] == "25000.00"  # unchanged
        # one operator_value_override change row with the correct delta
        chg = [
            c for c in plan["planned"]["changes"] if c["change_type"] == "operator_value_override"
        ]
        assert len(chg) == 1
        assert chg[0]["budget_code_key"] == "01-100"
        assert chg[0]["delta_amount"] == "25000.00"  # 150000 - 125000


def test_cost_to_complete_override_updates_header() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            operator_assumptions=[
                _override("cost_to_complete_override", code="01-100", value="40000")
            ],
        )
        header = plan["planned"]["outputs"][0]
        # CTC = 40000 + 0 = 40000; EAC unchanged
        assert header["cost_to_complete"] == "40000.00"
        assert header["estimated_final_cost"] == "205000.00"


def test_invalid_overrides_skipped_with_warning() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        plan = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            operator_assumptions=[
                _override("projected_cost_override", code=None, value="999"),  # null key
                _override("projected_cost_override", code="99-999", value="999"),  # unknown code
                _override("projected_cost_override", code="01-100", value="abc"),  # unparseable
            ],
        )
        header = plan["planned"]["outputs"][0]
        assert header["estimated_final_cost"] == "205000.00"  # unchanged
        assert not [
            c for c in plan["planned"]["changes"] if c["change_type"] == "operator_value_override"
        ]
        w = " ".join(plan["warnings"])
        assert (
            "no budget_code_key" in w
            and "not in recommendations" in w
            and "not a parseable amount" in w
        )


def test_no_overrides_byte_identical() -> None:
    # Same package + same now_utc, so any diff is from the override param alone.
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        base = eng.plan_run_output_projection(
            analysis_package=pkg, project_key=PROJECT_KEY, now_utc="2026-01-01T00:00:00+00:00"
        )
        empty = eng.plan_run_output_projection(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            now_utc="2026-01-01T00:00:00+00:00",
            operator_assumptions=[],
        )
    assert json.dumps(base["planned"], sort_keys=True) == json.dumps(
        empty["planned"], sort_keys=True
    )


# --- bridge + apply/parity --------------------------------------------------------------


def _seed_assumptions_db(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO forecast_operator_assumptions "
        "(assumption_id, run_id, project_key, assumption_type, budget_code_key, value, "
        " is_required, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "op1",
            None,
            PROJECT_KEY,
            "projected_cost_override",
            "01-100",
            "150000",
            0,
            json.dumps({"assumption_type": "projected_cost_override"}),
            "t",
        ),
    )
    conn.commit()
    conn.close()


def test_bridge_applies_overrides_with_parity(monkeypatch) -> None:
    monkeypatch.setenv(ENV_ASSUMPTION_OVERRIDES_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        adb = Path(td) / "assumptions.db"
        _seed_assumptions_db(adb)
        out = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(out)).apply()
        plan = eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            parity=True,
            assumptions_db_path=adb,
        )
        assert plan["ok"] is True
        assert plan["parity"]["proven"] is True
        conn = sqlite3.connect(str(out))
        eac = conn.execute("SELECT estimated_final_cost FROM forecast_outputs").fetchone()[0]
        pc = conn.execute(
            "SELECT recommended_projected_cost FROM forecast_output_budget_codes "
            "WHERE budget_code_key='01-100'"
        ).fetchone()[0]
        chg = conn.execute(
            "SELECT COUNT(*) FROM forecast_output_changes WHERE change_type='operator_value_override'"
        ).fetchone()[0]
        conn.close()
        assert pc == "150000.00"  # overridden value persisted
        assert eac == "230000.00"  # header re-aggregated from the override
        assert chg == 1


def test_flag_off_bridge_reads_nothing(monkeypatch) -> None:
    monkeypatch.delenv(ENV_ASSUMPTION_OVERRIDES_ENABLED, raising=False)
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_analysis_package(Path(td))
        adb = Path(td) / "assumptions.db"
        _seed_assumptions_db(adb)  # has an override, but flag is off
        out = Path(td) / "v63_out.db"
        SQLiteMigrator(db_path=str(out)).apply()
        eng.project_run_output(
            analysis_package=pkg,
            project_key=PROJECT_KEY,
            apply=True,
            db_path=out,
            assumptions_db_path=adb,
        )
        conn = sqlite3.connect(str(out))
        eac = conn.execute("SELECT estimated_final_cost FROM forecast_outputs").fetchone()[0]
        conn.close()
        assert eac == "205000.00"  # flag off -> no override applied


def test_hydrator_reads_project_scoped(monkeypatch) -> None:
    monkeypatch.setenv(ENV_ASSUMPTION_OVERRIDES_ENABLED, "1")
    with tempfile.TemporaryDirectory() as td:
        adb = Path(td) / "assumptions.db"
        _seed_assumptions_db(adb)
        rows = eng._hydrate_operator_assumptions(project_key=PROJECT_KEY, assumptions_db_path=adb)
        assert [r["assumption_id"] for r in rows] == ["op1"]
        # the reader the hydrator wraps is the P2 project-scoped reader
        conn = sqlite3.connect(f"file:{adb}?mode=ro", uri=True)
        try:
            direct = assume.read_operator_assumptions_from_db(conn, project_key=PROJECT_KEY)
        finally:
            conn.close()
        assert [r["assumption_id"] for r in direct] == ["op1"]
