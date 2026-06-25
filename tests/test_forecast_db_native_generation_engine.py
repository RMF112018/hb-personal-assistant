"""Phase E — package-free DB-native forecast generation engine (CFR).

Proves the engine turns a Phase D ``DbNativeForecastContext`` into a typed forecast result by reusing
the canonical ``forecast_cost_basis`` rules — financial-spine-only ``comprehensive`` output, honest
*unsupported* results for the other three kinds, coded degraded rows (never fabricated values),
money-safe lines, and a redaction-safe, hb_assistant-free module. The realistic DB-native spine
carries no ``erp_direct_costs`` breakdown, so the projected-cost formula cannot reconcile and
committed-cost codes route to ``manual_review_required`` (the no-fabrication safety property of the
asymmetric BudgetDetails basis is preserved). Dormancy/operator suppression and the asymmetric raise
itself require input families that are not yet DB-native (see ADR 317).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# CFR src on path for direct invocation (the forecasting bundle sets PYTHONPATH itself).
_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from construction_financial_review.context.db_native_context_builder import (  # noqa: E402
    DbNativeContextInput,
    build_db_native_context,
)
from construction_financial_review.generation.db_native_generation_engine import (  # noqa: E402
    DbNativeForecastResult,
    DbNativeGenerationEngineInput,
    generate_db_native_forecast,
)

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402

_MODULE = (
    _CFR_SRC
    / "construction_financial_review/generation/db_native_generation_engine.py"
)

_READINESS = {
    "forecast_maturity": "M4",
    "confidence_level": "medium",
    "readiness_status": "ready",
    "sparse": False,
    "initial_forecast": False,
    "prior_forecast_available": True,
}

# A realistic mixed budget: existing-model, committed (formula can't reconcile -> manual review),
# actuals-floor, zero-committed suppression, and a no-basis degraded code.
_BUDGET = [
    {"budget_code_key": "10-EXIST", "cost_code": "10", "category": "labor",
     "projected_costs": "1200.00", "revised_budget": "1000.00"},
    {"budget_code_key": "20-COMMIT", "projected_costs": "1000.00",
     "committed_costs": "800.00", "revised_budget": "1000.00"},
    {"budget_code_key": "30-FLOOR", "projected_costs": "100.00", "revised_budget": "100.00"},
    {"budget_code_key": "40-SUPPRESS", "committed_costs": "0.00", "revised_budget": "0.00"},
    {"budget_code_key": "50-DEGRADED"},
]
_COST = [
    {"budget_code_key": "10-EXIST", "amount": "350.00"},
    {"budget_code_key": "20-COMMIT", "amount": "200.00"},
    {"budget_code_key": "30-FLOOR", "amount": "500.00"},
]


def _ctx(budget=None, cost=None, monthly=None, readiness=None, cost_basis=None):
    src = DbNativeContextInput(
        project_key="proj-x",
        display_name="Project X",
        project_number="PX-1",
        procore_project_id="999",
        forecast_window={"forecast_start_date": "2026-06-01", "forecast_cutoff_date": "2026-12-31"},
        readiness=dict(readiness or _READINESS),
        budget_details=list(budget if budget is not None else _BUDGET),
        cost_entries=list(cost if cost is not None else _COST),
        monthly_actuals=list(monthly or []),
        budgetdetails_cost_basis_inputs=list(cost_basis or []),
    )
    return build_db_native_context(src)


def _run(ctx, kind="comprehensive", window=None) -> DbNativeForecastResult:
    return generate_db_native_forecast(
        DbNativeGenerationEngineInput("proj-x", kind, dict(window or {}), ctx)
    )


def _lines_by_key(result: DbNativeForecastResult) -> dict:
    return {ln["budget_code_key"]: ln for ln in result.public()["forecast_lines"]}


# -- 1. comprehensive produces a result from a minimal valid fixture ----------


def test_comprehensive_produces_result() -> None:
    pub = _run(_ctx(), window={"forecast_start_date": "2026-06-01"}).public()
    assert pub["generator_kind"] == "comprehensive"
    assert pub["result_code"] == "db_native_forecast_generated"
    assert pub["generation_scope"] == "financial_spine_db_native"
    assert pub["status"] == "generated_degraded"  # one no-basis code present
    # The result window is the requested generation window (echoed from the engine input).
    assert pub["forecast_window"]["forecast_start_date"] == "2026-06-01"
    assert pub["maturity"]["tier"] == "M4"
    assert pub["confidence"]["level"] == "medium"
    assert pub["summary"]["valued_budget_code_count"] == 4
    assert pub["summary"]["degraded_budget_code_count"] == 1


def test_summary_revised_budget_and_variance_from_nested_amounts() -> None:
    """Regression: real DB-native budget_details nest money under `amounts`. The engine summary must
    then carry a NON-ZERO total_revised_budget and variance_to_budget = EAC - revised_budget — not
    the full EAC (the false-$0 budget-basis bug)."""
    from decimal import Decimal

    budget = [
        {"budget_code_key": "10-EXIST", "cost_code": "10", "category": "labor",
         "amounts": {"projected_costs": "1200.00", "revised_budget": "1000.00"}},
    ]
    cost = [{"budget_code_key": "10-EXIST", "amount": "350.00"}]
    summary = _run(_ctx(budget=budget, cost=cost)).public()["summary"]
    assert summary["total_revised_budget"] == "1000.00"  # resolved from nested amounts, not 0.00
    eac = summary["total_forecast_final_cost"]
    assert summary["variance_to_budget"] == str(Decimal(eac) - Decimal("1000.00"))
    assert summary["variance_to_budget"] != eac  # variance is over revised budget, not full EAC


# -- comprehensive reuses the cost_basis classify/apply path ------------------


def test_comprehensive_uses_cost_basis_classifications() -> None:
    by_key = _lines_by_key(_run(_ctx()))
    # existing_model_basis when no committed cost is present.
    assert by_key["10-EXIST"]["cost_basis_classification"] == "existing_model_basis"
    assert by_key["10-EXIST"]["method_code"] == "existing_model_basis"
    # committed cost + non-reconciling formula (no erp_direct_costs on the spine) -> manual review.
    assert by_key["20-COMMIT"]["cost_basis_classification"] == "manual_review_required"
    # zero committed + no remaining evidence -> suppression to actuals.
    assert by_key["40-SUPPRESS"]["cost_basis_classification"] == "suppressed_no_remaining_commitment"


def test_final_cost_floored_to_actuals() -> None:
    by_key = _lines_by_key(_run(_ctx()))
    # projected 100 < actual 500 -> final is floored up to the actual cost to date.
    assert by_key["30-FLOOR"]["actual_cost_to_date"] == "500.00"
    assert by_key["30-FLOOR"]["forecast_final_cost"] == "500.00"
    assert by_key["30-FLOOR"]["forecast_cost_to_complete"] == "0.00"


def test_manual_review_does_not_fabricate_projected_basis() -> None:
    # The formula-guard (a present-but-non-reconciling formula never yields a projected basis) is
    # preserved: a committed-cost code surfaces the projected number but flags it for review.
    line = _lines_by_key(_run(_ctx()))["20-COMMIT"]
    assert line["forecast_final_cost"] == "1000.00"  # inbound projected, not a synthesised raise
    assert "projected_cost_formula_mismatch" in line["reason_codes"]
    risks = {(r["budget_code_key"], r["risk_type"]) for r in _run(_ctx()).public()["risks"]}
    assert ("20-COMMIT", "cost_basis_manual_review_required") in risks


def test_cost_to_complete_never_negative_and_final_ge_actual() -> None:
    from decimal import Decimal

    for line in _run(_ctx()).public()["forecast_lines"]:
        if line["row_status"] != "ok":
            continue
        final = Decimal(line["forecast_final_cost"])
        actual = Decimal(line["actual_cost_to_date"])
        ctc = Decimal(line["forecast_cost_to_complete"])
        assert final >= actual
        assert ctc >= 0
        assert ctc == max(final - actual, Decimal("0"))


def test_overrun_risk_flagged() -> None:
    risks = {(r["budget_code_key"], r["risk_type"]) for r in _run(_ctx()).public()["risks"]}
    assert ("10-EXIST", "forecast_exceeds_revised_budget") in risks  # 1200 > 1000
    assert ("30-FLOOR", "forecast_exceeds_revised_budget") in risks  # 500 > 100


# -- missing required row inputs -> coded degraded row, NOT fabricated values --


def test_no_basis_code_produces_degraded_row() -> None:
    line = _lines_by_key(_run(_ctx()))["50-DEGRADED"]
    assert line["row_status"] == "degraded_no_basis"
    assert line["cost_basis_classification"] == "insufficient_row_basis"
    assert line["forecast_final_cost"] is None
    assert line["forecast_cost_to_complete"] is None
    assert line["confidence"] == "none"


def test_all_degraded_is_insufficient_basis() -> None:
    # A project whose only budget code has no basis and no actuals -> insufficient_basis.
    pub = _run(_ctx(budget=[{"budget_code_key": "99-EMPTY"}], cost=[])).public()
    assert pub["status"] == "insufficient_basis"
    assert pub["result_code"] == "db_native_insufficient_financial_basis"
    assert "db_native_insufficient_financial_basis" in pub["blockers"]


def test_sparse_readiness_degrades_status() -> None:
    sparse = dict(_READINESS, sparse=True, forecast_maturity="M1")
    pub = _run(
        _ctx(
            budget=[{"budget_code_key": "10-EXIST", "projected_costs": "100.00"}],
            cost=[{"budget_code_key": "10-EXIST", "amount": "10.00"}],
            readiness=sparse,
        )
    ).public()
    assert pub["status"] == "generated_degraded"
    assert pub["maturity"]["sparse"] is True


# -- 2. each non-comprehensive kind returns a specific unsupported code --------


def test_unsupported_kinds_return_curated_codes() -> None:
    expected = {
        "monthly": "db_native_monthly_requires_phasing_signals",
        "probability": "db_native_probability_requires_monte_carlo_inputs",
        "model_controls": "db_native_model_controls_requires_operator_config",
    }
    ctx = _ctx()
    for kind, code in expected.items():
        pub = _run(ctx, kind=kind).public()
        assert pub["status"] == "unsupported"
        assert pub["result_code"] == code
        assert pub["blockers"] == [code]
        assert pub["generator_kind"] == kind
        # no fabricated forecast values on an unsupported path.
        assert pub["forecast_lines"] == []
        assert pub["summary"] == {}
        assert pub["assumptions"] == []
        assert pub["risks"] == []
        assert pub["message"]  # curated, path-free copy


def test_unknown_kind_is_unsupported() -> None:
    pub = _run(_ctx(), kind="totally_made_up").public()
    assert pub["status"] == "unsupported"
    assert pub["result_code"] == "db_native_unknown_generator_kind"
    assert pub["forecast_lines"] == []


# -- comprehensive discloses what it does NOT produce on the DB-native path ----


def test_comprehensive_discloses_unsupported_outputs_and_spine_only_warning() -> None:
    # No forecast_end_date in the window -> monthly is honestly degraded with the horizon-specific
    # reason (not the generic phasing-signals code, which only applies to the standalone monthly kind).
    pub = _run(_ctx()).public()
    assert pub["unsupported_outputs"] == {
        "monthly": "db_native_monthly_requires_forecast_end_date",
        "probability": "db_native_probability_requires_monte_carlo_inputs",
        "model_controls": "db_native_model_controls_requires_operator_config",
    }
    assert "owner_procore_crosswalk_evidence_unavailable_financial_spine_only" in pub["warnings"]


# =====================================================================================
# DB-native comprehensive monthly output — window-bounded actuals + even-spread forecast.
# =====================================================================================

# 10-A: projected 1000 > actual 300 -> existing_model_basis, final 1000, CTC 700.
_M_BUDGET = [{"budget_code_key": "10-A", "projected_costs": "1000.00", "revised_budget": "2000.00"}]
_M_COST = [{"budget_code_key": "10-A", "amount": "300.00"}]
_M_MONTHLY = [
    {"budget_code_key": "10-A", "month": "2026-04", "type": "actual", "amount": "100.00"},
    {"budget_code_key": "10-A", "month": "2026-05", "type": "actual", "amount": "200.00"},
]
_M_WINDOW = {
    "forecast_start_date": "2026-04-01",
    "forecast_cutoff_date": "2026-05-31",
    "forecast_end_date": "2026-08-31",
}


def _monthly_run():
    return _run(_ctx(budget=_M_BUDGET, cost=_M_COST, monthly=_M_MONTHLY), window=_M_WINDOW).public()


def test_comprehensive_emits_monthly_actuals_and_forecast() -> None:
    from decimal import Decimal

    pub = _monthly_run()
    rows = pub["monthly"]
    actuals = [r for r in rows if r["is_actual"] == 1]
    forecast = [r for r in rows if r["is_actual"] == 0]
    # Window-bounded actuals: both source months sit inside [2026-04, 2026-05].
    assert {(r["month"], r["value"]) for r in actuals} == {
        ("2026-04", "100.00"),
        ("2026-05", "200.00"),
    }
    # CTC 700 even-spread across the 3 future months after the effective actual boundary (2026-05).
    assert [r["month"] for r in forecast] == ["2026-06", "2026-07", "2026-08"]
    # Deterministic residual lands on the final month: 700/3 -> 233.33, 233.33, 233.34.
    assert [r["value"] for r in forecast] == ["233.33", "233.33", "233.34"]
    assert sum(Decimal(r["value"]) for r in forecast) == Decimal("700.00")
    # monthly no longer unsupported; even-spread is disclosed; the other two kinds remain unsupported.
    assert "monthly" not in pub["unsupported_outputs"]
    assert set(pub["unsupported_outputs"]) == {"probability", "model_controls"}
    assert "db_native_monthly_even_spread_not_schedule_weighted" in pub["warnings"]


def test_monthly_forecast_reconciles_to_header_ctc() -> None:
    from decimal import Decimal

    pub = _monthly_run()
    forecast = [r for r in pub["monthly"] if r["is_actual"] == 0]
    assert sum(Decimal(r["value"]) for r in forecast) == Decimal(pub["summary"]["total_cost_to_complete"])


def test_monthly_actual_rows_bounded_by_requested_window() -> None:
    # An older source actual (2026-01) outside the selected [start, cutoff] window is excluded.
    monthly = _M_MONTHLY + [
        {"budget_code_key": "10-A", "month": "2026-01", "type": "actual", "amount": "999.00"}
    ]
    rows = _run(_ctx(budget=_M_BUDGET, cost=_M_COST, monthly=monthly), window=_M_WINDOW).public()["monthly"]
    actual_months = {r["month"] for r in rows if r["is_actual"] == 1}
    assert actual_months == {"2026-04", "2026-05"}


def test_monthly_actuals_aggregated_across_type() -> None:
    # Two rows for the same (code, month) under different ``type`` are summed into one actual row.
    monthly = [
        {"budget_code_key": "10-A", "month": "2026-05", "type": "actual", "amount": "200.00"},
        {"budget_code_key": "10-A", "month": "2026-05", "type": "actual_committed", "amount": "50.00"},
    ]
    rows = _run(_ctx(budget=_M_BUDGET, cost=_M_COST, monthly=monthly), window=_M_WINDOW).public()["monthly"]
    may = [r for r in rows if r["is_actual"] == 1 and r["month"] == "2026-05"]
    assert len(may) == 1
    assert may[0]["value"] == "250.00"


def test_monthly_degraded_without_forecast_end_date() -> None:
    pub = _run(
        _ctx(budget=_M_BUDGET, cost=_M_COST, monthly=_M_MONTHLY),
        window={"forecast_start_date": "2026-04-01", "forecast_cutoff_date": "2026-05-31"},
    ).public()
    assert pub["monthly"] == []
    assert pub["unsupported_outputs"]["monthly"] == "db_native_monthly_requires_forecast_end_date"
    assert "db_native_monthly_requires_forecast_end_date" in pub["warnings"]


def test_monthly_degraded_when_end_not_after_boundary() -> None:
    # forecast_end_date == the effective actual boundary -> no future horizon -> honest degrade.
    pub = _run(
        _ctx(budget=_M_BUDGET, cost=_M_COST, monthly=_M_MONTHLY),
        window={**_M_WINDOW, "forecast_end_date": "2026-05-31"},
    ).public()
    assert pub["monthly"] == []
    assert pub["unsupported_outputs"]["monthly"] == "db_native_monthly_no_future_horizon"


def test_monthly_forecast_without_source_actuals_uses_cutoff_boundary() -> None:
    from decimal import Decimal

    pub = _run(_ctx(budget=_M_BUDGET, cost=_M_COST, monthly=[]), window=_M_WINDOW).public()
    rows = pub["monthly"]
    assert [r for r in rows if r["is_actual"] == 1] == []
    forecast = [r for r in rows if r["is_actual"] == 0]
    # Cut-off 2026-05 anchors the start when no actuals fall in the window -> 2026-06..2026-08.
    assert [r["month"] for r in forecast] == ["2026-06", "2026-07", "2026-08"]
    assert sum(Decimal(r["value"]) for r in forecast) == Decimal("700.00")
    assert "db_native_monthly_no_source_actuals_in_window" in pub["warnings"]


# -- determinism --------------------------------------------------------------


def test_deterministic_output() -> None:
    assert _run(_ctx()).public() == _run(_ctx()).public()


# -- redaction-safe -----------------------------------------------------------


def test_result_is_redaction_safe() -> None:
    for kind in ("comprehensive", "monthly", "probability", "totally_made_up"):
        assert find_redaction_leaks(_run(_ctx(), kind=kind).public()) == [], kind


# -- module is package-free and imports no hb_assistant -----------------------


def test_module_imports_no_hb_assistant_or_package_code() -> None:
    names: set[str] = set()
    for node in ast.walk(ast.parse(_MODULE.read_text())):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    forbidden = (
        "hb_assistant",
        "generate_forecast_context_package",
        "generate_forecast_analysis_package",
        "run_lineage",
        "package_resolution",
        "resolve_upstream",
        "SRC_FILES",
    )
    leaked = sorted(n for n in forbidden if any(n in name for name in names))
    assert leaked == [], f"forbidden references in engine module: {leaked}"


# =====================================================================================
# Phase E2 — engine uses DB-native BudgetDetails cost-basis inputs when available.
# =====================================================================================

# A single budget code with cost entries summing 200 (the actuals floor).
_E2_BUDGET = [{"budget_code_key": "1000.15-01-426.MAT", "cost_code": "15-01-426",
               "category": "MAT", "revised_budget": "900.00"}]
_E2_COST = [{"budget_code_key": "1000.15-01-426.MAT", "amount": "200.00"}]


def _cbi(**over) -> list[dict]:
    base = {
        "budget_code_key": "1000.15-01-426.MAT",
        "committed_costs": "600.00", "erp_direct_costs": "300.00", "pending_cost_changes": "100.00",
        "projected_costs": "1000.00", "actual_cost": "200.00", "commitment_invoiced": "550.00",
        "estimated_cost_at_completion": "850.00", "formula_reconciles": True, "formula_variance": "0.00",
        "missing_formula_fields": [], "selected_budget_view_id": "5885", "selection_warnings": [],
    }
    base.update(over)
    return [base]


def test_reconciling_formula_reaches_budgetdetails_projected_basis() -> None:
    # committed 600 + erp 300 + pending 100 == projected 1000, and projected (1000) > EAC (850) -> raise.
    line = _lines_by_key(_run(_ctx(budget=_E2_BUDGET, cost=_E2_COST, cost_basis=_cbi())))[
        "1000.15-01-426.MAT"
    ]
    assert line["cost_basis_classification"] == "budgetdetails_projected_cost_basis"
    assert line["cost_basis_source"] == "db_native_budgetdetails"
    assert line["forecast_final_cost"] == "1000.00"
    assert line["forecast_cost_to_complete"] == "800.00"  # 1000 - 200 actual
    assert line["budget_basis"]["formula_reconciles"] is True


def test_non_reconciling_formula_routes_to_manual_review() -> None:
    # pending_cost_changes missing -> formula cannot reconcile -> manual_review_required (no fabrication).
    cbi = _cbi(pending_cost_changes=None, formula_reconciles=False,
               missing_formula_fields=["pending_cost_changes"], formula_variance=None)
    line = _lines_by_key(_run(_ctx(budget=_E2_BUDGET, cost=_E2_COST, cost_basis=cbi)))[
        "1000.15-01-426.MAT"
    ]
    assert line["cost_basis_classification"] == "manual_review_required"
    assert line["cost_basis_source"] == "db_native_budgetdetails"


def test_cost_basis_inputs_preserve_money_invariants() -> None:
    from decimal import Decimal

    line = _lines_by_key(_run(_ctx(budget=_E2_BUDGET, cost=_E2_COST, cost_basis=_cbi())))[
        "1000.15-01-426.MAT"
    ]
    final = Decimal(line["forecast_final_cost"])
    actual = Decimal(line["actual_cost_to_date"])
    ctc = Decimal(line["forecast_cost_to_complete"])
    assert final >= actual
    assert ctc == max(final - actual, Decimal("0"))


def test_reconciling_but_eac_above_projected_keeps_existing_model() -> None:
    # EAC (1200) already >= projected (1000): never cap an overrun down to ERP -> existing_model_basis.
    cbi = _cbi(estimated_cost_at_completion="1200.00")
    line = _lines_by_key(_run(_ctx(budget=_E2_BUDGET, cost=_E2_COST, cost_basis=cbi)))[
        "1000.15-01-426.MAT"
    ]
    assert line["cost_basis_classification"] == "existing_model_basis"
    assert line["forecast_final_cost"] == "1200.00"  # model EAC preserved, not lowered to ERP


def test_phase_e_behavior_unchanged_without_cost_basis_inputs() -> None:
    # No cost_basis_inputs -> v59-spine fallback: committed code still routes to manual_review.
    by_key = _lines_by_key(_run(_ctx()))
    assert by_key["20-COMMIT"]["cost_basis_classification"] == "manual_review_required"
    assert by_key["20-COMMIT"]["cost_basis_source"] == "spine_budget_amounts"


def test_cost_basis_inputs_result_redaction_safe() -> None:
    res = _run(_ctx(budget=_E2_BUDGET, cost=_E2_COST, cost_basis=_cbi()))
    assert find_redaction_leaks(res.public()) == []
