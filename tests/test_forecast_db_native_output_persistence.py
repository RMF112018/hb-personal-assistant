"""Phase F — package-free persistence of a DB-native forecast result into the v63 tables.

Unit-level proof (no FastAPI, temp SQLite only): the builder maps result.public() to the v63 planned
dict (header + budget_codes + risks + narratives, every other detail table empty and no v66 rows),
persistence is idempotent and atomic, the certification preflight rejects malformed results without
writing, and the persisted payloads are redaction-safe and bounded.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.analytics import forecast_db_native_output_persistence as persist
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_run_output_persistence_service import (
    verify_run_output_persistence,
)
from hb_assistant.store.migrator import SQLiteMigrator

_PROJECT = "tropical"


def _result(**overrides) -> dict:
    """A generated comprehensive result.public() fixture (two valued lines, one risk)."""
    base = {
        "schema_version": 1,
        "project_key": _PROJECT,
        "generator_kind": "comprehensive",
        "status": "generated",
        "result_code": "db_native_forecast_generated",
        "message": "DB-native forecast generated.",
        "generation_scope": "financial_spine_db_native",
        "forecast_window": {
            "forecast_start_date": "2026-06-01",
            "forecast_cutoff_date": "2026-12-31",
        },
        "maturity": {"tier": "M3", "readiness_status": "ready"},
        "confidence": {"level": "medium", "forecast_basis": "financial_spine_db_native"},
        "forecast_lines": [
            {
                "budget_code_key": "01-100",
                "cost_code": "01-100",
                "category": "labor",
                "actual_cost_to_date": "350.00",
                "budget_basis": {"projected_costs": "1200.00", "revised_budget": "1000.00"},
                "cost_basis_source": "spine_budget_amounts",
                "cost_basis_classification": "budgetdetails_projected_cost_basis",
                "forecast_final_cost": "1200.00",
                "forecast_cost_to_complete": "850.00",
                "variance_to_budget": "200.00",
                "confidence": "medium",
                "method_code": "budgetdetails_projected_cost_basis",
                "reason_codes": ["projected_exceeds_model"],
                "row_status": "ok",
            },
            {
                "budget_code_key": "02-200",
                "cost_code": "02-200",
                "category": "material",
                "actual_cost_to_date": "500.00",
                "budget_basis": {"projected_costs": "100.00", "revised_budget": "500.00"},
                "cost_basis_source": "spine_budget_amounts",
                "cost_basis_classification": "actuals_floor",
                "forecast_final_cost": "500.00",
                "forecast_cost_to_complete": "0.00",
                "variance_to_budget": "0.00",
                "confidence": "medium",
                "method_code": "actuals_floor",
                "reason_codes": ["projected_below_actual"],
                "row_status": "ok",
            },
        ],
        "summary": {
            "budget_code_count": 2,
            "valued_budget_code_count": 2,
            "degraded_budget_code_count": 0,
            "total_forecast_final_cost": "1700.00",
            "total_cost_to_complete": "850.00",
            "total_actual_cost_to_date": "850.00",
            "total_revised_budget": "1500.00",
            "variance_to_budget": "200.00",
        },
        "assumptions": [
            {
                "scope": "budget_code",
                "budget_code_key": "01-100",
                "code": "budgetdetails_projected_cost_basis",
                "reason": ["projected_exceeds_model"],
            },
            {
                "scope": "budget_code",
                "budget_code_key": "02-200",
                "code": "actuals_floor",
                "reason": ["projected_below_actual"],
            },
        ],
        "risks": [
            {
                "budget_code_key": "01-100",
                "risk_type": "forecast_exceeds_revised_budget",
                "severity": "warning",
                "variance_to_budget": "200.00",
            }
        ],
        "unsupported_outputs": {"monthly": "db_native_monthly_requires_phasing_signals"},
        "warnings": [],
        "blockers": [],
        "provenance": {
            "engine_version": "db_native_generation_engine/1",
            "row_counts_by_family": {"budget_details": 2},
        },
    }
    base.update(overrides)
    return base


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "app" / "hb.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    return db


def _rows(db: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(str(db))
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


# -- builder ------------------------------------------------------------------


def test_build_planned_maps_v63_header_lines_risks_narratives() -> None:
    planned = persist.build_db_native_planned(
        _result(), output_id="fout-x", run_id="run-x", project_key=_PROJECT, now_utc="2026-06-25T00:00:00+00:00"
    )
    assert len(planned["outputs"]) == 1
    assert len(planned["budget_codes"]) == 2
    assert len(planned["risks"]) == 1
    assert len(planned["narratives"]) == 2
    # Every other v63 detail table is emitted empty.
    for key in ("monthly", "probability", "changes", "commitment_exposure", "staffing", "schedule_phasing"):
        assert planned[key] == []
    header = planned["outputs"][0]
    assert header["source_package"] == "db_native"
    assert header["estimated_final_cost"] == "1700.00"
    assert header["cost_to_complete"] == "850.00"
    assert header["forecast_period"] == "2026-06-01..2026-12-31"
    # Header raw_json is a bounded envelope — it must NOT carry the per-line detail.
    envelope = json.loads(header["raw_json"])
    assert "forecast_lines" not in envelope
    assert set(envelope) >= {"summary", "maturity", "confidence", "provenance", "status"}
    bc = {r["budget_code_key"]: r for r in planned["budget_codes"]}
    assert bc["01-100"]["recommended_projected_cost"] == "1200.00"
    assert bc["01-100"]["recommended_cost_to_complete"] == "850.00"
    assert bc["01-100"]["forecast_action"] == "budgetdetails_projected_cost_basis"
    assert planned["risks"][0]["risk_id"] == "01-100:forecast_exceeds_revised_budget"


def test_derive_output_id_is_deterministic_and_independent_of_run_id() -> None:
    a = persist.derive_output_id(project_key="tropical", generator_kind="comprehensive")
    b = persist.derive_output_id(project_key="tropical", generator_kind="comprehensive")
    c = persist.derive_output_id(project_key="other", generator_kind="comprehensive")
    assert a == b and a != c and a.startswith("fout-")


# -- persistence --------------------------------------------------------------


def test_persist_round_trip_writes_v63_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    outcome = persist.persist_db_native_result(
        result=_result(),
        project_key=_PROJECT,
        generator_kind="comprehensive",
        request_id="req-1",
        db_path=db,
    )
    assert outcome.db_persisted is True
    assert outcome.output_id and outcome.run_id
    counts = verify_run_output_persistence(db, _PROJECT)
    assert counts["forecast_outputs_count"] == 1
    assert counts["budget_code_rows_count"] == 2
    assert counts["risk_rows_count"] == 1
    # Empty detail tables stay empty.
    assert counts["monthly_rows_count"] == 0
    assert counts["probability_rows_count"] == 0
    assert counts["schedule_phasing_rows_count"] == 0
    # No v66 decision-support rows.
    assert _rows(db, "forecast_project_maturity_snapshots") == []
    assert _rows(db, "forecast_confidence_scorecards") == []
    # Narratives populated from assumptions; persisted payloads redaction-clean.
    narratives = _rows(db, "forecast_output_narratives")
    assert len(narratives) == 2
    assert find_redaction_leaks([json.loads(r["raw_json"]) for r in narratives]) == []


def test_persist_is_idempotent(tmp_path: Path) -> None:
    db = _db(tmp_path)
    first = persist.persist_db_native_result(
        result=_result(), project_key=_PROJECT, generator_kind="comprehensive",
        request_id="req-1", db_path=db,
    )
    second = persist.persist_db_native_result(
        result=_result(), project_key=_PROJECT, generator_kind="comprehensive",
        request_id="req-2", db_path=db,
    )
    assert first.output_id == second.output_id
    assert verify_run_output_persistence(db, _PROJECT)["forecast_outputs_count"] == 1
    assert verify_run_output_persistence(db, _PROJECT)["budget_code_rows_count"] == 2


# -- certification preflight (no partial writes) ------------------------------


@pytest.mark.parametrize(
    "mutate, kind",
    [
        (lambda r: r["forecast_lines"][0].pop("budget_code_key"), "comprehensive"),
        (lambda r: r["forecast_lines"].__setitem__(0, {**r["forecast_lines"][0], "forecast_final_cost": "10.00", "actual_cost_to_date": "999.00"}), "comprehensive"),
        (lambda r: r["forecast_lines"].__setitem__(0, {**r["forecast_lines"][0], "forecast_final_cost": "not-a-number"}), "comprehensive"),
        (lambda r: r.__setitem__("forecast_lines", []), "comprehensive"),
        (lambda r: None, "monthly"),  # unsupported kind
    ],
    ids=["missing_budget_code_key", "final_below_actual", "non_decimal_money", "no_lines", "unsupported_kind"],
)
def test_certification_failure_writes_nothing(tmp_path: Path, mutate, kind) -> None:
    db = _db(tmp_path)
    result = _result()
    mutate(result)
    outcome = persist.persist_db_native_result(
        result=result, project_key=_PROJECT, generator_kind=kind, request_id="req-1", db_path=db,
    )
    assert outcome.db_persisted is False
    assert outcome.failure_code == "db_native_output_certification_failed"
    assert verify_run_output_persistence(db, _PROJECT)["forecast_outputs_count"] == 0


def test_persistence_failure_rolls_back_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)

    def _partial_then_boom(conn, planned):
        # Write the header row, then fail — the transaction must roll the header back.
        persist.repo.upsert_output(conn, planned["outputs"][0])
        raise RuntimeError("injected write failure")

    monkeypatch.setattr(persist.repo, "apply_plan", _partial_then_boom)
    outcome = persist.persist_db_native_result(
        result=_result(), project_key=_PROJECT, generator_kind="comprehensive",
        request_id="req-1", db_path=db,
    )
    assert outcome.db_persisted is False
    assert outcome.failure_code == "db_persistence_failed"
    assert verify_run_output_persistence(db, _PROJECT)["forecast_outputs_count"] == 0
