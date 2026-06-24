"""P10 PR2 — forecast-correctness VALUE tests (gap-only).

Covers the two value behaviors not already asserted elsewhere in the forecast suite:

1. **Probability band VALUE correctness.** ``p10/p50/p90`` round-trip exactly through the
   projection -> ``forecast_output_probability`` -> read layer, and the band ordering
   ``p10 <= p50 <= p90`` holds end to end. (``test_forecast_output_coverage.py`` and
   ``test_forecast_live_db_run_output_projection.py`` only *count*-assert these rows.)

2. **Second-project (non-tropical) VALUE isolation.** A distinct ``project_key`` in the
   same temp DB aggregates only its own per-code costs (no cross-sum), its prior-run delta
   is project-scoped, and the read model filters by ``project_key``. (Every other main-repo
   value test uses ``project_key="tropical"``; the only multi-project test merely checks
   pre-seeded rows survive a live write.)

Already-covered value behaviors are attested in ``docs/architecture/306-*`` and are NOT
re-tested here: header == per-code Decimal sum + prior-delta (``phase2a``), operator
dollar-override re-aggregation (``p2b``), assumption consumption (``assumptions_consume_p2``),
floor-to-actuals (CFR ``test_fp_simulate`` / ``test_reconcile`` / ``test_fp_distributions``).

No network, no CFR import, no live-DB write.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

from hb_assistant.construction.analytics.forecast_run_readmodel import (
    ForecastRunReadModelService,
)
from hb_assistant.construction.forecast import output_projection_engine as eng
from hb_assistant.construction.forecast import output_repository as repo
from hb_assistant.store.migrator import SQLiteMigrator

TROPICAL = "tropical"
HARBOR = "harbor"


def _recs(project_key: str, recs: list[dict]) -> list[dict]:
    """Stamp ``project_key`` onto a list of per-code recommendation dicts."""
    return [{**r, "project_key": project_key} for r in recs]


# tropical baseline: EAC = 125000 + 80000 = 205000; CTC = 25000; budget = 180000; variance = 25000
_TROPICAL_RECS = [
    {
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

# harbor (distinct project): EAC = 250000 + 100000 = 350000; CTC = 50000; budget = 300000; variance = 50000
_HARBOR_RECS = [
    {
        "budget_code_key": "10-500",
        "cost_code": "10-500",
        "category": "Steel",
        "forecast_action": "increase_forecast",
        "budget_amount": "200000.00",
        "recommended_projected_cost": "250000.00",
        "recommended_cost_to_complete": "50000.00",
        "confidence": "high",
    },
    {
        "budget_code_key": "11-600",
        "cost_code": "11-600",
        "category": "Glazing",
        "forecast_action": "hold",
        "budget_amount": "100000.00",
        "recommended_projected_cost": "100000.00",
        "recommended_cost_to_complete": "0.00",
        "confidence": "moderate",
    },
]


def _make_analysis_package(
    root: Path, *, project_key: str, stamp: str = "20260622_120000", recs: list[dict]
) -> Path:
    """Project-parameterized analysis-package fixture (mirrors phase2a)."""
    pkg = root / f"forecast_analysis_package_{project_key}_{stamp}"
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"project_key": project_key, "stamp": stamp}), encoding="utf-8"
    )
    (pkg / "summaries" / "project_forecast_analysis.json").write_text(
        json.dumps({"total_budget_codes": len(recs), "risk_count": 0}), encoding="utf-8"
    )
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _recs(project_key, recs)) + "\n", encoding="utf-8"
    )
    (pkg / "forecast_risk_register.jsonl").write_text("", encoding="utf-8")
    return pkg


def _make_probability_package(
    root: Path, *, project_key: str, rows: list[dict], stamp: str = "s"
) -> Path:
    """Probability-package fixture (mirrors test_forecast_output_coverage._probability_pkg)."""
    pkg = root / f"forecast_probability_package_{project_key}_{stamp}"
    pkg.mkdir(parents=True)
    (pkg / "probabilistic_final_cost_by_budget_code.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return pkg


def _migrated_db(root: Path, name: str = "v63_out.db") -> Path:
    db = root / name
    SQLiteMigrator(db_path=str(db)).apply()
    return db


# -- Gap 1: probability band VALUE correctness -------------------------------------------

_PROB_ROWS = [
    {"budget_code_key": "01-100", "simulated_p10": "90.00", "simulated_p50": "100.00",
     "simulated_p90": "120.00"},
    {"budget_code_key": "02-200", "simulated_p10": "300.00", "simulated_p50": "350.00",
     "simulated_p90": "500.00"},
]


def _apply_with_probability(root: Path) -> tuple[Path, str]:
    """Apply a tropical run that carries the probability package; return (db, output_id)."""
    db = _migrated_db(root)
    pkg = _make_analysis_package(root, project_key=TROPICAL, recs=_TROPICAL_RECS)
    prob = _make_probability_package(root, project_key=TROPICAL, rows=_PROB_ROWS)
    plan = eng.project_run_output(
        analysis_package=pkg,
        probability_package=prob,
        project_key=TROPICAL,
        apply=True,
        db_path=db,
        parity=True,
    )
    assert plan["ok"] is True
    assert plan["parity"]["proven"] is True
    assert plan["written"]["probability"] == len(_PROB_ROWS)
    return db, plan["output_id"]


def test_probability_bands_round_trip_values() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, oid = _apply_with_probability(Path(td))
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT budget_code_key, p10, p50, p90 FROM forecast_output_probability "
            "WHERE output_id = ? ORDER BY budget_code_key",
            (oid,),
        ).fetchall()
        conn.close()
        # The band values persist EXACTLY as supplied (string-Decimal), not just as N rows.
        assert rows == [
            ("01-100", "90.00", "100.00", "120.00"),
            ("02-200", "300.00", "350.00", "500.00"),
        ]


def test_probability_band_ordering_invariant() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, oid = _apply_with_probability(Path(td))
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT budget_code_key, p10, p50, p90 FROM forecast_output_probability "
            "WHERE output_id = ?",
            (oid,),
        ).fetchall()
        conn.close()
        assert rows, "expected probability rows to assert ordering over"
        for _key, p10, p50, p90 in rows:
            assert Decimal(p10) <= Decimal(p50) <= Decimal(p90)


def test_probability_bands_surface_via_read() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, oid = _apply_with_probability(Path(td))
        # repo read path (the function the engine itself registers) returns the raw-json echo
        # in source-file order, so the keys are the original package keys (simulated_*).
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            repo_rows = repo.read_output_probability_from_db(conn, output_id=oid)
        finally:
            conn.close()
        assert [(r["budget_code_key"], r["simulated_p50"]) for r in repo_rows] == [
            ("01-100", "100.00"),
            ("02-200", "350.00"),
        ]
        # business-safe read model surfaces the same band values
        svc = ForecastRunReadModelService(db_path=str(db))
        detail = svc.read_output(oid)
        bands = {r["budget_code_key"]: r for r in detail["probability"]}
        assert bands["01-100"]["p10"] == "90.00"
        assert bands["01-100"]["p90"] == "120.00"
        assert bands["02-200"]["p50"] == "350.00"


# -- Gap 2: second-project (non-tropical) VALUE isolation --------------------------------


T_RUN = "t-run-1"
H_RUN_1 = "h-run-1"


def _seed_runs(db: Path, runs: list[tuple[str, str, str]]) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.executemany(
            "INSERT INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            runs,
        )
        conn.commit()
    finally:
        conn.close()


def _apply_both_projects(root: Path) -> tuple[Path, str, str]:
    """Apply one tropical run and one harbor run into the SAME db; return (db, t_oid, h_oid).

    Both projects carry seeded run_ids so prior-run attribution is verifiable; tropical is
    created LATER than the first harbor run so a non-project-scoped prior lookup would wrongly
    surface tropical as harbor's prior.
    """
    db = _migrated_db(root)
    _seed_runs(
        db,
        [
            (H_RUN_1, HARBOR, "2026-01-02T00:00:00+00:00"),
            (T_RUN, TROPICAL, "2026-01-03T00:00:00+00:00"),
        ],
    )
    t_pkg = _make_analysis_package(
        root, project_key=TROPICAL, stamp="20260101_000000", recs=_TROPICAL_RECS
    )
    h_pkg = _make_analysis_package(
        root, project_key=HARBOR, stamp="20260101_000000", recs=_HARBOR_RECS
    )
    h_plan = eng.project_run_output(
        analysis_package=h_pkg, project_key=HARBOR, apply=True, db_path=db,
        run_id=H_RUN_1, now_utc="2026-01-02T00:00:00+00:00",
    )
    t_plan = eng.project_run_output(
        analysis_package=t_pkg, project_key=TROPICAL, apply=True, db_path=db,
        run_id=T_RUN, now_utc="2026-01-03T00:00:00+00:00",
    )
    assert t_plan["ok"] is True and h_plan["ok"] is True
    return db, t_plan["output_id"], h_plan["output_id"]


def test_two_projects_headers_isolated() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, t_oid, h_oid = _apply_both_projects(Path(td))
        conn = sqlite3.connect(str(db))
        t_row = conn.execute(
            "SELECT estimated_final_cost, cost_to_complete, variance_to_budget "
            "FROM forecast_outputs WHERE output_id = ?",
            (t_oid,),
        ).fetchone()
        h_row = conn.execute(
            "SELECT estimated_final_cost, cost_to_complete, variance_to_budget "
            "FROM forecast_outputs WHERE output_id = ?",
            (h_oid,),
        ).fetchone()
        conn.close()
        # Each header aggregates ONLY its own per-code rows — no cross-project contamination.
        assert t_row == ("205000.00", "25000.00", "25000.00")
        assert h_row == ("350000.00", "50000.00", "50000.00")


def test_prior_delta_is_project_scoped() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db, t_oid, h_oid = _apply_both_projects(root)
        # harbor's FIRST run has no harbor prior — even though a (later-created) tropical run
        # exists in the same DB, it must NOT be picked up as harbor's prior.
        conn = sqlite3.connect(str(db))
        h_first_delta = conn.execute(
            "SELECT variance_to_prior_forecast FROM forecast_outputs WHERE output_id = ?",
            (h_oid,),
        ).fetchone()[0]
        n_cross = conn.execute(
            "SELECT COUNT(*) FROM forecast_output_changes "
            "WHERE output_id = ? AND change_type = 'current_vs_prior'",
            (h_oid,),
        ).fetchone()[0]
        conn.close()
        assert h_first_delta is None
        assert n_cross == 0

        # A SECOND harbor run (higher EAC) picks up the first harbor run as its prior.
        _seed_runs(db, [("h-run-2", HARBOR, "2026-02-01T00:00:00+00:00")])
        recs_b = [dict(r) for r in _HARBOR_RECS]
        recs_b[0]["recommended_projected_cost"] = "280000.00"  # 280000 + 100000 = 380000
        h_pkg_b = _make_analysis_package(
            root, project_key=HARBOR, stamp="20260201_000000", recs=recs_b
        )
        plan_b = eng.project_run_output(
            analysis_package=h_pkg_b, project_key=HARBOR, apply=True, db_path=db,
            run_id="h-run-2", now_utc="2026-02-01T00:00:00+00:00",
        )
        conn = sqlite3.connect(str(db))
        delta = conn.execute(
            "SELECT variance_to_prior_forecast FROM forecast_outputs WHERE output_id = ?",
            (plan_b["output_id"],),
        ).fetchone()[0]
        change = conn.execute(
            "SELECT delta_amount, prior_run_id FROM forecast_output_changes "
            "WHERE output_id = ? AND change_type = 'current_vs_prior'",
            (plan_b["output_id"],),
        ).fetchall()
        conn.close()
        # delta = 380000 - 350000 = 30000 (harbor's own prior). A non-scoped lookup would have
        # used the later-created tropical run (380000 - 205000 = 175000) and prior_run_id=t-run-1.
        assert delta == "30000.00"
        assert change == [("30000.00", H_RUN_1)]


def test_readmodel_filters_by_project_key() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, t_oid, h_oid = _apply_both_projects(Path(td))
        svc = ForecastRunReadModelService(db_path=str(db))
        harbor = svc.list_outputs(HARBOR)["outputs"]
        tropical = svc.list_outputs(TROPICAL)["outputs"]
        assert [o["output_id"] for o in harbor] == [h_oid]
        assert harbor[0]["estimated_final_cost"] == "350000.00"
        assert [o["output_id"] for o in tropical] == [t_oid]
        assert tropical[0]["estimated_final_cost"] == "205000.00"
