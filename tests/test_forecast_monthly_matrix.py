"""Operator month-window monthly forecast matrix (v74).

Covers the four-field operator month-window contract end to end: DTO validation + derivation, the
schedule/actuals month-window defaults (no silent +12 horizon), the engine's window-bounded cells +
table-ready matrix rows + dense total row, the fail-closed certification of that matrix (warning-grade
budget-source divergence stays non-fatal), and the read-model's dense, redaction-safe matrix shape.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from construction_financial_review.context.db_native_context_builder import (  # noqa: E402
    DbNativeContextInput,
    build_db_native_context,
)
from construction_financial_review.generation.db_native_generation_engine import (  # noqa: E402
    DbNativeGenerationEngineInput,
    generate_db_native_forecast,
)

from hb_assistant.construction.analytics.forecast_db_native_output_persistence import (  # noqa: E402
    build_db_native_planned,
    certify_db_native_result,
    persist_db_native_result,
)
from hb_assistant.construction.analytics.forecast_generation_date_defaults import (  # noqa: E402
    ForecastGenerationDateDefaultsService,
)
from hb_assistant.construction.analytics.forecast_generation_request_dto import (  # noqa: E402
    validate_request,
)
from hb_assistant.construction.analytics.forecast_run_readmodel import (  # noqa: E402
    ForecastRunReadModelService,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402

_READINESS = {
    "forecast_maturity": "M4",
    "confidence_level": "medium",
    "readiness_status": "ready",
    "sparse": False,
    "initial_forecast": False,
    "prior_forecast_available": True,
}

# Two budget codes with a Procore-authoritative display row each (budget_code drives cost_type).
_BUDGET = [
    {"budget_code_key": "A", "cost_code": "03-01-1000", "projected_costs": "9000.00", "revised_budget": "9000.00"},
    {"budget_code_key": "B", "cost_code": "03-01-2000", "projected_costs": "4000.00", "revised_budget": "4000.00"},
]
_COST = [
    {"budget_code_key": "A", "amount": "300.00"},
    {"budget_code_key": "B", "amount": "100.00"},
]
_COST_BASIS = [
    {
        "budget_code_key": "A",
        "display_budget_code": "1000.03-01-1000.LAB",
        "display_cost_code": "03-01-1000",
        "display_projected_budget": "9000.00",
        "projected_costs": "9000.00",
    },
    {
        "budget_code_key": "B",
        "display_budget_code": "2000.03-01-2000.MAT",
        "display_cost_code": "03-01-2000",
        "display_projected_budget": "4000.00",
        "projected_costs": "4000.00",
    },
]
# Monthly actuals: A duplicated within 2026-01 (sums to 200), plus a stray 2026-04 OUTSIDE the actual
# window (must be excluded). B has a single in-window actual.
_MONTHLY = [
    {"budget_code_key": "A", "month": "2026-01", "type": "x", "amount": "120.00"},
    {"budget_code_key": "A", "month": "2026-01", "type": "y", "amount": "80.00"},
    {"budget_code_key": "A", "month": "2026-02", "type": "x", "amount": "100.00"},
    {"budget_code_key": "A", "month": "2026-04", "type": "x", "amount": "999.00"},  # out of window
    {"budget_code_key": "B", "month": "2026-02", "type": "x", "amount": "100.00"},
]

_WINDOW = {
    "actuals_start_month": "2026-01",
    "actuals_through_month": "2026-02",
    "forecast_start_month": "2026-03",
    "forecast_end_month": "2026-05",
    "forecast_end_date": "2026-05-31",
}


def _ctx():
    src = DbNativeContextInput(
        project_key="proj-x",
        display_name="Project X",
        project_number="PX-1",
        procore_project_id="999",
        forecast_window=dict(_WINDOW),
        readiness=dict(_READINESS),
        budget_details=list(_BUDGET),
        cost_entries=list(_COST),
        monthly_actuals=list(_MONTHLY),
        budgetdetails_cost_basis_inputs=list(_COST_BASIS),
    )
    return build_db_native_context(src)


def _result(window=None):
    return generate_db_native_forecast(
        DbNativeGenerationEngineInput("proj-x", "comprehensive", dict(window or _WINDOW), _ctx())
    ).public()


# -- 1. DTO validation + derivation -------------------------------------------


def test_dto_accepts_valid_month_window_and_derives_dates():
    parsed, errors = validate_request(
        {
            "project_key": "tropical",
            "actuals_start_month": "2026-01",
            "actuals_through_month": "2026-05",
            "forecast_start_month": "2026-06",
            "forecast_end_month": "2026-10",
        },
        mode="db_native",
    )
    assert errors == []
    assert parsed["actuals_start_month"] == "2026-01"
    assert parsed["forecast_end_month"] == "2026-10"
    # Internal legacy dates are derived from the months (actuals lower bound + month-end cutoff/end).
    assert parsed["forecast_start_date"] == "2026-01-01"
    assert parsed["forecast_cutoff_date"] == "2026-05-31"
    assert parsed["forecast_end_date"] == "2026-10-31"


def test_dto_rejects_invalid_year_month():
    _, errors = validate_request(
        {"project_key": "p", "actuals_start_month": "2026-13", "actuals_through_month": "2026-05",
         "forecast_start_month": "2026-06", "forecast_end_month": "2026-10"},
        mode="db_native",
    )
    assert "invalid_actuals_start_month" in errors


def test_dto_rejects_reversed_actual_window_single_code():
    _, errors = validate_request(
        {"project_key": "p", "actuals_start_month": "2026-06", "actuals_through_month": "2026-05",
         "forecast_start_month": "2026-07", "forecast_end_month": "2026-10"},
        mode="db_native",
    )
    assert errors == ["actuals_start_after_through"]


def test_dto_rejects_reversed_forecast_window():
    _, errors = validate_request(
        {"project_key": "p", "actuals_start_month": "2026-01", "actuals_through_month": "2026-05",
         "forecast_start_month": "2026-10", "forecast_end_month": "2026-06"},
        mode="db_native",
    )
    assert "forecast_start_after_end_month" in errors


def test_dto_rejects_overlapping_windows():
    _, errors = validate_request(
        {"project_key": "p", "actuals_start_month": "2026-01", "actuals_through_month": "2026-05",
         "forecast_start_month": "2026-05", "forecast_end_month": "2026-10"},
        mode="db_native",
    )
    assert "forecast_window_overlaps_actuals" in errors


# -- 2. engine: window-bounded cells + matrix invariants ----------------------


def test_engine_actual_cells_only_inside_actual_window():
    cells = _result()["monthly"]
    actual_months = {c["month"] for c in cells if c["value_type"] == "actual"}
    assert actual_months <= {"2026-01", "2026-02"}
    assert "2026-04" not in actual_months  # the stray out-of-window actual was excluded


def test_engine_forecast_cells_only_inside_forecast_window_no_implicit_horizon():
    cells = _result()["monthly"]
    forecast_months = {c["month"] for c in cells if c["value_type"] == "forecast"}
    assert forecast_months == {"2026-03", "2026-04", "2026-05"}  # explicit end honoured, no +N drift


def test_engine_aggregates_duplicate_actuals_by_month():
    cells = _result()["monthly"]
    a_jan = [c for c in cells if c["budget_code_key"] == "A" and c["month"] == "2026-01"]
    assert len(a_jan) == 1
    assert Decimal(a_jan[0]["value"]) == Decimal("200.00")  # 120 + 80


def test_engine_one_matrix_row_per_budget_code():
    pub = _result()
    row_keys = {r["budget_code_key"] for r in pub["monthly_table_rows"]}
    line_keys = {ln["budget_code_key"] for ln in pub["forecast_lines"]}
    assert row_keys == line_keys
    assert len(pub["monthly_table_rows"]) == len(pub["forecast_lines"])


def test_engine_row_formulas_and_cost_type():
    rows = {r["budget_code_key"]: r for r in _result()["monthly_table_rows"]}
    cells = _result()["monthly"]
    for key, r in rows.items():
        ctd = sum((Decimal(c["value"]) for c in cells if c["budget_code_key"] == key and c["value_type"] == "actual"), Decimal("0"))
        ftc = sum((Decimal(c["value"]) for c in cells if c["budget_code_key"] == key and c["value_type"] == "forecast"), Decimal("0"))
        assert Decimal(r["completed_to_date"]) == ctd
        assert Decimal(r["forecast_to_complete"]) == ftc
        assert Decimal(r["estimated_at_completion"]) == ctd + ftc
        # Variance = display projected budget - EAC (positive = under budget, negative = overrun).
        assert Decimal(r["variance_to_budget"]) == Decimal(r["projected_budget_display"]) - (ctd + ftc)
    assert rows["A"]["cost_type"] == "LAB"  # last 3 of 1000.03-01-1000.LAB
    assert rows["B"]["cost_type"] == "MAT"


def test_engine_total_row_reconciles_to_rows():
    pub = _result()
    rows = pub["monthly_table_rows"]
    totals = pub["monthly_table_totals"]
    for scalar in ("completed_to_date", "forecast_to_complete", "estimated_at_completion", "variance_to_budget"):
        assert Decimal(totals[f"{scalar}_total"]) == sum((Decimal(r[scalar]) for r in rows), Decimal("0"))
    assert Decimal(totals["projected_budget_total"]) == sum((Decimal(r["projected_budget_display"]) for r in rows), Decimal("0"))
    # Dense per-month total equals the per-month cell sum.
    for m in (mm["month"] for mm in pub["monthly_months"]):
        cell_sum = sum((Decimal(c["value"]) for c in pub["monthly"] if c["month"] == m), Decimal("0"))
        assert Decimal(totals["month_values"][m]) == cell_sum


def test_engine_no_matrix_without_operator_months():
    # Legacy date-only window: cells may be emitted, but NO matrix is built.
    pub = _result(window={"forecast_start_date": "2026-01-01", "forecast_cutoff_date": "2026-02-28", "forecast_end_date": "2026-05-31"})
    assert pub["monthly_table_rows"] == []
    assert pub["monthly_table_totals"] is None


# -- 3. certification fail-closed (warning-grade divergence stays non-fatal) ---


def _planned():
    return build_db_native_planned(_result(), output_id="o1", run_id="r1", project_key="proj-x", now_utc="2026-06-26T00:00:00+00:00")


def test_certification_clean_on_valid_matrix():
    assert certify_db_native_result(_result(), _planned(), request_id="q", project_key="proj-x", generator_kind="comprehensive") == []


def test_certification_fails_closed_on_duplicate_cell():
    planned = _planned()
    planned["monthly"].append(dict(planned["monthly"][0]))  # duplicate (code, month)
    reasons = certify_db_native_result(_result(), planned, request_id="q", project_key="proj-x", generator_kind="comprehensive")
    assert "monthly_duplicate_cell" in reasons


def test_certification_fails_closed_on_missing_matrix_row():
    planned = _planned()
    planned["monthly_table_rows"] = planned["monthly_table_rows"][:-1]  # drop one row
    reasons = certify_db_native_result(_result(), planned, request_id="q", project_key="proj-x", generator_kind="comprehensive")
    assert "monthly_matrix_row_budget_code_mismatch" in reasons


def test_certification_fails_closed_on_cell_outside_window():
    planned = _planned()
    for cell in planned["monthly"]:
        if cell["value_type"] == "forecast":
            cell["month"] = "2027-01"  # outside the forecast window
            break
    reasons = certify_db_native_result(_result(), planned, request_id="q", project_key="proj-x", generator_kind="comprehensive")
    assert "monthly_cell_outside_forecast_window" in reasons


# -- 4. persistence + read-model shape ----------------------------------------


def test_read_monthly_table_is_dense_and_redaction_safe():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "o.db")
        SQLiteMigrator(db_path=db).apply()
        outcome = persist_db_native_result(
            result=_result(), project_key="proj-x", generator_kind="comprehensive",
            request_id="q", db_path=db, source_snapshot_id="s1",
        )
        assert outcome.db_persisted
        table = ForecastRunReadModelService(db_path=db).read_monthly_table(outcome.output_id)
    assert table["status"] == "ready"
    months = [m["month"] for m in table["months"]]
    assert months == sorted(months)  # chronological
    # Dense: every row has a value for every displayed month (read-fill of 0.00).
    for row in table["rows"]:
        assert set(row["month_values"]) == set(months)
    assert set(table["total_row"]["month_values"]) == set(months)
    # Redaction: no raw payloads / paths / run ids leak.
    import json as _json

    blob = _json.dumps(table)
    for forbidden in ("raw_json", "run_id", ".sqlite", "source_path", "source_package"):
        assert forbidden not in blob


def _seed_actual_month(conn, project_key, month, amount):
    conn.execute(
        "INSERT INTO forecast_monthly_actuals_by_budget_code(project_key, budget_code_key, month, type, "
        "source_package, amount, raw_json, created_utc) VALUES(?,?,?,?,?,?,?,?)",
        (project_key, "A", month, "cost", "pkg", amount, "{}", "2026-06-26T00:00:00+00:00"),
    )


def test_month_defaults_resolve_from_actuals_and_no_silent_horizon():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "d.db")
        SQLiteMigrator(db_path=db).apply()
        conn = sqlite3.connect(db)
        _seed_actual_month(conn, "proj-x", "2026-01", 100.0)
        _seed_actual_month(conn, "proj-x", "2026-03", 250.0)
        conn.commit()
        conn.close()
        defaults = ForecastGenerationDateDefaultsService(db_path=db).resolve("proj-x")
    assert defaults.actuals_start_month == "2026-01"
    assert defaults.actuals_through_month == "2026-03"
    assert defaults.forecast_start_month == "2026-04"  # month after actuals_through
    # No schedule activities → NO silent +12 horizon; forecast end is left for operator confirmation.
    assert defaults.forecast_end_month is None
    assert "no_forecast_end_month_default_operator_confirmation_required" in defaults.warnings


def test_read_monthly_table_legacy_output_has_no_fabricated_window():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "legacy.db")
        SQLiteMigrator(db_path=db).apply()
        # Insert a header WITHOUT month-window metadata (a pre-v74-style output).
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO forecast_outputs(output_id, project_key, source_package, raw_json, created_utc) "
            "VALUES('fout-legacy','proj-x','db_native','{}','2026-06-26T00:00:00+00:00')"
        )
        conn.commit()
        conn.close()
        table = ForecastRunReadModelService(db_path=db).read_monthly_table("fout-legacy")
    assert table["status"] == "legacy_output_no_operator_window"
    assert "months" not in table  # nothing fabricated
