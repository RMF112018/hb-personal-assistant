"""P5 — maturity / data-availability / confidence completion.

Proves the decision-support engine now derives (instead of stubbing to None):
- maturity lifecycle staging M0..M5, including an output-evidence-driven M5 closeout;
- output-aware data availability (commitment/schedule/etc. flip to "available" when the run's
  v63 output tables have rows; owner/procore stay "unavailable" — no forecast backing table);
- the per-domain completeness / mapping_quality / maturity / score fields.

All reads are against a NON-LIVE temp DB; the engine writes nothing here (dry-run plan).
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.forecast import decision_support_engine as eng
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT = "tropical"
RUN = "r1"
TS = "2026-01-01T00:00:00+00:00"
SRC = "fads"


def _analysis_pkg(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_s"
    pkg.mkdir(parents=True)
    pkg.joinpath("confidence_rollup.json").write_text(
        json.dumps({"count_by_confidence": {"high": 1}}), encoding="utf-8"
    )
    return pkg


def _db(root: Path, *, months: int = 0, budget_codes: int = 0, with_outputs: bool = False,
        eac: str | None = None, ctc: str | None = None,
        commitment_codes: tuple[str, ...] = (), schedule_codes: tuple[str, ...] = ()) -> Path:
    db = root / "p5.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
                 (RUN, PROJECT, TS))
    codes = [f"00-{i:03d}" for i in range(budget_codes)]
    for code in codes:
        conn.execute(
            "INSERT INTO forecast_budget_details (project_key, budget_code_key, source_package, "
            "raw_json, created_utc) VALUES (?,?,?,?,?)", (PROJECT, code, SRC, "{}", TS))
    for m in range(months):
        code = codes[0] if codes else "00-000"
        conn.execute(
            "INSERT INTO forecast_monthly_actuals_by_budget_code (project_key, budget_code_key, "
            "month, type, source_package, amount, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?)",
            (PROJECT, code, f"2026-{m + 1:02d}", "actual", SRC, "100.00", "{}", TS))
    if with_outputs:
        oid = "o1"
        conn.execute(
            "INSERT INTO forecast_outputs (output_id, run_id, project_key, source_package, "
            "estimated_final_cost, cost_to_complete, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?)",
            (oid, RUN, PROJECT, SRC, eac, ctc, "{}", TS))
        conn.execute(
            "INSERT INTO forecast_output_budget_codes (id, output_id, project_key, budget_code_key, "
            "confidence, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?,?)",
            ("bc1", oid, PROJECT, codes[0] if codes else "00-000", "high", 1, "{}", TS))
        for i, code in enumerate(commitment_codes):
            conn.execute(
                "INSERT INTO forecast_output_commitment_exposure (id, output_id, project_key, "
                "budget_code_key, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?)",
                (f"ce{i}", oid, PROJECT, code, i, "{}", TS))
        for i, code in enumerate(schedule_codes):
            conn.execute(
                "INSERT INTO forecast_output_schedule_phasing (id, output_id, project_key, "
                "budget_code_key, source_row_number, raw_json, created_utc) VALUES (?,?,?,?,?,?,?)",
                (f"sp{i}", oid, PROJECT, code, i, "{}", TS))
    conn.commit()
    conn.close()
    return db


def _plan(root: Path, db: Path) -> dict:
    return eng.plan_decision_support(
        db_path=db, analysis_package=_analysis_pkg(root), project_key=PROJECT, run_id=RUN,
    )


def _avail_by_domain(plan: dict) -> dict[str, dict]:
    return {r["domain"]: r for r in plan["planned"]["availability"]}


def _tier(plan: dict) -> tuple[str, str]:
    snap = plan["planned"]["maturity"][0]
    return snap["maturity_tier"], snap["lifecycle_signal"]


def test_maturity_stages_m0_to_m4() -> None:
    cases = [
        (0, 0, "M0", "pre_start"),
        (0, 3, "M1", "mobilizing"),
        (2, 3, "M2", "in_progress"),
        (4, 3, "M3", "in_progress"),
        (6, 3, "M4", "mature"),
    ]
    for months, codes, want_tier, want_signal in cases:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = _db(root, months=months, budget_codes=codes)
            tier, signal = _tier(_plan(root, db))
            assert (tier, signal) == (want_tier, want_signal), (months, codes)


def test_m5_closeout_when_ctc_near_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # 6 completed months would be M4, but CTC/EAC = 1/1000 = 0.001 <= 0.005 -> M5 closeout
        db = _db(root, months=6, budget_codes=3, with_outputs=True, eac="1000.00", ctc="1.00")
        tier, signal = _tier(_plan(root, db))
        assert tier == "M5" and signal == "closeout"


def test_not_closeout_when_ctc_material() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # CTC/EAC = 500/1000 = 0.5 -> not closeout; 6 months -> M4
        db = _db(root, months=6, budget_codes=3, with_outputs=True, eac="1000.00", ctc="500.00")
        tier, _ = _tier(_plan(root, db))
        assert tier == "M4"


def test_output_aware_availability_flips_commitment_and_schedule() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _db(root, months=2, budget_codes=3, with_outputs=True, eac="1000.00", ctc="900.00",
                 commitment_codes=("00-000", "00-001"), schedule_codes=("00-000",))
        avail = _avail_by_domain(_plan(root, db))
        # the headline acceptance: commitment/schedule no longer mislabeled "unavailable"
        assert avail["commitment"]["availability"] == "available"
        assert avail["schedule"]["availability"] == "available"
        # domains with no seeded output rows stay unavailable
        assert avail["risk"]["availability"] == "unavailable"
        assert avail["probability"]["availability"] == "unavailable"
        # domains with no forecast backing table at all
        assert avail["owner"]["availability"] == "unavailable"
        assert avail["procore"]["availability"] == "unavailable"


def test_per_code_completeness_and_mapping_values() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # commitment covers 2 of 3 budget codes, both mapped -> completeness 2/3, mapping 2/2
        db = _db(root, months=2, budget_codes=3, with_outputs=True, eac="1000.00", ctc="900.00",
                 commitment_codes=("00-000", "00-001"))
        c = _avail_by_domain(_plan(root, db))["commitment"]
        assert c["completeness"] == "0.6667"   # 2 / 3 budget-code universe
        assert c["mapping_quality"] == "1.0000"  # 2 / 2 domain codes resolve
        assert c["score"] == "0.6667"           # availability-gated completeness
        assert c["coverage"] == "2"


def test_all_availability_rows_carry_maturity_and_score() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _db(root, months=6, budget_codes=3)
        plan = _plan(root, db)
        tier, _ = _tier(plan)
        for row in plan["planned"]["availability"]:
            assert row["maturity"] == tier            # project tier layered onto every domain
            assert row["score"] is not None           # populated, never None
            assert row["score"] in {"0.0000", "1.0000"} or "." in row["score"]


def test_unavailable_domain_score_is_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db = _db(root, months=0, budget_codes=0)
        avail = _avail_by_domain(_plan(root, db))
        assert avail["procore"]["availability"] == "unavailable"
        assert avail["procore"]["score"] == "0.0000"
