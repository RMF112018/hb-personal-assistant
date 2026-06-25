"""Phase E — HB-side DB-native engine adapter.

Proves the read-only chain build_db_native_source_snapshot -> context_input_from_snapshot_public ->
build_db_native_context -> generate_db_native_forecast runs end-to-end against a controlled SQLite
fixture: comprehensive produces a financial-spine result, the chain reads no package directory and
writes nothing, unsupported kinds round-trip their curated codes, a project with no financial basis
fails closed with a path-free insufficient_basis result, and every result is redaction-safe.
The live db-native route stays fail-closed in Phase E — this adapter is not wired into it (ADR 317).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# CFR src on path for the lazy adapter import (the forecasting bundle sets PYTHONPATH itself).
_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.construction.analytics.forecast_db_native_engine_adapter import (  # noqa: E402
    compute_db_native_forecast,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.forecast.source_domain_repository import (  # noqa: E402
    upsert_budget_detail,
    upsert_cost_entry,
    upsert_monthly_actual,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402

_PKG = "twn_cost_forecast_json_package"

_BUDGET = [
    {"budget_code_key": "01-100", "cost_code": "01-100", "category": "labor",
     "revised_budget": "1000.00", "projected_costs": "1200.00"},
    {"budget_code_key": "02-200", "cost_code": "02-200", "category": "material",
     "revised_budget": "500.00", "projected_costs": "100.00"},  # projected < actual -> floor
]
_COST = [
    {"budget_code_key": "01-100", "accounting_month": "2026-05", "amount": "250.00"},
    {"budget_code_key": "01-100", "accounting_month": "2026-06", "amount": "100.00"},
    {"budget_code_key": "02-200", "accounting_month": "2026-05", "amount": "500.00"},
]
_MONTHLY = [
    {"budget_code_key": "01-100", "month": "2026-05", "type": "actual", "amount": "250.00",
     "entry_count": 1},
]


def _db() -> str:
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _seed_v59(db: str, project_key: str, *, source_package: str, budget=None, cost=None,
              monthly=None) -> None:
    conn = sqlite3.connect(db)
    try:
        for i, row in enumerate(budget or [], start=1):
            upsert_budget_detail(conn, {
                "project_key": project_key, "budget_code_key": row["budget_code_key"],
                "source_package": source_package, "cost_code": row.get("cost_code"),
                "category": row.get("category"), "source_row_number": i,
                "raw_json": json.dumps(row), "created_utc": "2026-06-20T00:00:00Z"})
        for i, row in enumerate(cost or [], start=1):
            upsert_cost_entry(conn, {
                "cost_entry_id": f"{project_key}|{source_package}|{i}", "project_key": project_key,
                "source_package": source_package, "source_row_number": i,
                "budget_code_key": row.get("budget_code_key"),
                "accounting_month": row.get("accounting_month"),
                "raw_json": json.dumps(row), "created_utc": "2026-06-20T00:00:00Z"})
        for i, row in enumerate(monthly or [], start=1):
            upsert_monthly_actual(conn, {
                "project_key": project_key, "budget_code_key": row["budget_code_key"],
                "month": row["month"], "type": row["type"], "source_package": source_package,
                "amount": row.get("amount"), "entry_count": row.get("entry_count"),
                "source_row_number": i, "raw_json": json.dumps(row),
                "created_utc": "2026-06-20T00:00:00Z"})
        conn.commit()
    finally:
        conn.close()


def _full_project(db: str, project_key: str, display_name: str) -> None:
    seed_procore_ep_project(db, project_key=project_key, display_name=display_name)
    _seed_v59(db, project_key, source_package=_PKG, budget=_BUDGET, cost=_COST, monthly=_MONTHLY)


# -- full DB -> snapshot -> context -> engine chain ---------------------------


def test_comprehensive_chain_against_db_fixture() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    result = compute_db_native_forecast(
        "tropical", "comprehensive",
        forecast_window={"forecast_start_date": "2026-06-01"}, db_path=db,
    )
    assert result["project_key"] == "tropical"
    assert result["status"] in ("generated", "generated_degraded")
    assert result["result_code"] == "db_native_forecast_generated"
    by_key = {ln["budget_code_key"]: ln for ln in result["forecast_lines"]}
    assert by_key["01-100"]["actual_cost_to_date"] == "350.00"
    assert by_key["01-100"]["forecast_final_cost"] == "1200.00"  # projected, existing-model basis
    # floor: projected 100 < actual 500 -> final floored to actual.
    assert by_key["02-200"]["forecast_final_cost"] == "500.00"
    assert by_key["02-200"]["forecast_cost_to_complete"] == "0.00"
    assert result["summary"]["total_actual_cost_to_date"] == "850.00"


def test_chain_reads_no_package_and_writes_nothing(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    compute_db_native_forecast("tropical", "comprehensive", db_path=db)
    # The DB-native chain opens no package directory and writes nothing under cwd.
    assert list(workdir.iterdir()) == []


def test_unsupported_kind_round_trips_curated_code() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    result = compute_db_native_forecast("tropical", "monthly", db_path=db)
    assert result["status"] == "unsupported"
    assert result["result_code"] == "db_native_monthly_requires_phasing_signals"
    assert result["forecast_lines"] == []


def test_no_financial_basis_fails_closed() -> None:
    db = _db()
    # Project identity present, but no v59 financial rows seeded.
    seed_procore_ep_project(db, project_key="barren", display_name="Barren Project")
    result = compute_db_native_forecast("barren", "comprehensive", db_path=db)
    assert result["status"] == "insufficient_basis"
    assert result["forecast_lines"] == []
    assert result["blockers"]  # curated, path-free coded reason


def test_results_are_redaction_safe() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    for kind in ("comprehensive", "probability"):
        result = compute_db_native_forecast("tropical", kind, db_path=db)
        assert find_redaction_leaks(result) == [], kind
