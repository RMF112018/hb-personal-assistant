"""Read-model tests for the consolidated DB-native Forecast Summary bridge.

Exercises ``ForecastRunReadModelService.read_output(...)["summary"]`` directly: the typed KPI
object whitelist-extracted from the v63 header ``raw_json`` envelope (the envelope itself is never
surfaced), variance-to-budget reconciliation, prior-forecast variance computed at read time,
missing-vs-zero semantics, and readiness confidence/maturity sourced from v63 (never the empty v66
decision-support tables). DB-native stays package-free; no schema change.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_run_readmodel import ForecastRunReadModelService
from hb_assistant.store.migrator import SQLiteMigrator

PROJECT = "tropical"
RUN_ID = "20260101_000000"  # stamp-format — must never reach a payload


def _envelope(
    *,
    eac: str,
    ctc: str,
    cost_to_date: str | None,
    revised_budget: str | None,
    variance: str,
    confidence_level: str = "medium",
    forecast_basis: str = "cost_informed_financial_spine",
    maturity_tier: str = "cost_informed",
    basis_limitations: list[str] | None = None,
) -> str:
    summary: dict[str, object] = {
        "total_forecast_final_cost": eac,
        "total_cost_to_complete": ctc,
        "variance_to_budget": variance,
    }
    if cost_to_date is not None:
        summary["total_actual_cost_to_date"] = cost_to_date
    if revised_budget is not None:
        summary["total_revised_budget"] = revised_budget
    return json.dumps(
        {
            "schema_version": 1,
            "generation_mode": "db_native",
            "maturity": {"tier": maturity_tier, "readiness_status": "ready"},
            "confidence": {
                "level": confidence_level,
                "forecast_basis": forecast_basis,
                "basis_limitations": basis_limitations or [],
            },
            "summary": summary,
        },
        sort_keys=True,
    )


def _insert_output(
    db: Path,
    *,
    output_id: str,
    eac: str,
    ctc: str,
    variance: str,
    raw_json: str,
    created_utc: str,
    source_package: str = "db_native",
) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO forecast_runs (run_id, project_key, created_utc) VALUES (?,?,?)",
            (RUN_ID, PROJECT, created_utc),
        )
        conn.execute(
            "INSERT INTO forecast_outputs (output_id, run_id, project_key, source_package, "
            "estimated_final_cost, forecast_at_completion, cost_to_complete, variance_to_budget, "
            "variance_to_prior_forecast, source_path, raw_json, created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (output_id, RUN_ID, PROJECT, source_package, eac, eac, ctc, variance,
             None, None, raw_json, created_utc),
        )
        conn.commit()
    finally:
        conn.close()


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "hb.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    return db


def _summary(db: Path, output_id: str) -> dict:
    return ForecastRunReadModelService(db_path=str(db)).read_output(output_id)["summary"]


def test_summary_typed_fields_and_reconciled_variance(tmp_path):
    db = _db(tmp_path)
    env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="600.00", revised_budget="800.00",
                    variance="200.00")
    _insert_output(db, output_id="fout-a", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=env, created_utc="2026-06-20T00:00:00+00:00")
    s = _summary(db, "fout-a")
    assert s["estimated_at_completion"] == "1000.00"
    assert s["cost_to_complete"] == "400.00"
    assert s["total_cost_to_date"] == "600.00"
    assert s["current_budget"] == "800.00"
    assert s["budget_basis_label"] == "Revised budget"
    assert s["budget_status"] == "available"
    assert s["variance_to_budget"] == "200.00"
    assert s["variance_to_budget_status"] == "reconciled"  # 1000 - 800 == 200
    assert s["forecast_confidence_label"] == "Medium"
    assert s["forecast_maturity_label"] == "Cost-informed"
    assert s["variance_to_prior_forecast_status"] == "no_prior_forecast"
    assert s["variance_to_prior_forecast"] is None


def test_variance_reconciliation_mismatch_surfaces_status_not_swapped_value(tmp_path):
    db = _db(tmp_path)
    # persisted variance disagrees with EAC - current_budget (1000 - 800 = 200, not 999)
    env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="600.00", revised_budget="800.00",
                    variance="999.00")
    _insert_output(db, output_id="fout-m", eac="1000.00", ctc="400.00", variance="999.00",
                   raw_json=env, created_utc="2026-06-20T00:00:00+00:00")
    s = _summary(db, "fout-m")
    assert s["variance_to_budget"] == "999.00"  # persisted value preserved, not silently replaced
    assert s["variance_to_budget_status"] == "reconciliation_mismatch"


def test_missing_budget_is_null_not_zero_and_status_budget_unavailable(tmp_path):
    db = _db(tmp_path)
    # zero cost-to-date is a real "0.00"; revised_budget absent -> missing, not zero
    env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="0.00", revised_budget=None,
                    variance="200.00")
    _insert_output(db, output_id="fout-b", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=env, created_utc="2026-06-20T00:00:00+00:00")
    s = _summary(db, "fout-b")
    assert s["total_cost_to_date"] == "0.00"  # real zero preserved
    assert s["current_budget"] is None  # missing, never coerced to "0.00"
    assert s["budget_basis_label"] is None
    assert s["budget_status"] == "budget_unavailable"
    assert s["variance_to_budget_status"] == "budget_unavailable"


def test_prior_forecast_variance_computed_for_comparable_older_output(tmp_path):
    db = _db(tmp_path)
    prior_env = _envelope(eac="900.00", ctc="300.00", cost_to_date="600.00", revised_budget="800.00",
                          variance="100.00")
    cur_env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="600.00", revised_budget="800.00",
                        variance="200.00")
    _insert_output(db, output_id="fout-prior", eac="900.00", ctc="300.00", variance="100.00",
                   raw_json=prior_env, created_utc="2026-06-19T00:00:00+00:00")
    _insert_output(db, output_id="fout-cur", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=cur_env, created_utc="2026-06-20T00:00:00+00:00")
    s = _summary(db, "fout-cur")
    assert s["variance_to_prior_forecast"] == "100.00"  # 1000 - 900
    assert s["variance_to_prior_forecast_status"] == "computed"


def test_prior_forecast_variance_zero_renders_canonical_zero(tmp_path):
    db = _db(tmp_path)
    env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="600.00", revised_budget="800.00",
                    variance="200.00")
    _insert_output(db, output_id="fout-p0", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=env, created_utc="2026-06-19T00:00:00+00:00")
    _insert_output(db, output_id="fout-c0", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=env, created_utc="2026-06-20T00:00:00+00:00")
    s = _summary(db, "fout-c0")
    assert s["variance_to_prior_forecast"] == "0.00"  # equal EACs -> real zero, not "no prior"
    assert s["variance_to_prior_forecast_status"] == "computed"


def test_confidence_maturity_from_v63_envelope_without_any_v66_rows(tmp_path):
    db = _db(tmp_path)
    env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="600.00", revised_budget="800.00",
                    variance="200.00", confidence_level="high", maturity_tier="full_context",
                    basis_limitations=["owner_procore_evidence_unavailable"])
    _insert_output(db, output_id="fout-cm", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=env, created_utc="2026-06-20T00:00:00+00:00")
    # No v66 decision-support rows seeded — confidence/maturity must still resolve from v63.
    s = _summary(db, "fout-cm")
    assert s["forecast_confidence_label"] == "High"
    assert s["forecast_maturity_label"] == "Full context"
    assert s["forecast_maturity_basis"] == "owner_procore_evidence_unavailable"


def test_malformed_envelope_yields_null_fields_not_exception(tmp_path):
    db = _db(tmp_path)
    _insert_output(db, output_id="fout-x", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json="not json{", created_utc="2026-06-20T00:00:00+00:00")
    s = _summary(db, "fout-x")
    # header-derived values survive; envelope-derived go null (no raise)
    assert s["estimated_at_completion"] == "1000.00"
    assert s["total_cost_to_date"] is None
    assert s["current_budget"] is None
    assert s["forecast_confidence_label"] is None
    assert s["forecast_maturity_label"] is None
    assert s["variance_to_budget_status"] == "budget_unavailable"


def test_summary_never_leaks_raw_json_or_envelope(tmp_path):
    db = _db(tmp_path)
    env = _envelope(eac="1000.00", ctc="400.00", cost_to_date="600.00", revised_budget="800.00",
                    variance="200.00")
    _insert_output(db, output_id="fout-r", eac="1000.00", ctc="400.00", variance="200.00",
                   raw_json=env, created_utc="2026-06-20T00:00:00+00:00")
    body = ForecastRunReadModelService(db_path=str(db)).read_output("fout-r")
    assert "raw_json" not in body and "raw_json" not in body["summary"]
    assert "generation_mode" not in body["summary"]  # envelope internals not surfaced
    assert find_redaction_leaks(body) == []
    assert RUN_ID not in json.dumps(body)
