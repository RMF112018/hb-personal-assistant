"""Unit tests for the reconciled (production-forecast) as-of backtest."""

from __future__ import annotations

from decimal import Decimal

from construction_financial_review.forecast_intelligence import reconciled_backtest as rb


def test_asof_reliabilities_use_real_rules():
    # owner < 0.50 -> low; trend months < 6 -> low; commitment + cpi always low.
    r = rb._asof_reliabilities(
        Decimal("0.40"), {"months_of_completed_actuals": 4, "cost_volatility_cov": "0.20"}
    )
    assert r == {
        "owner_progress_eac": "low",
        "trend_projection_eac": "low",
        "commitment_exposure_eac": "low",
        "cpi_blend_eac": "low",
    }
    # owner >= 0.50 -> medium; trend months>=6 & cov<=0.75 -> medium.
    r2 = rb._asof_reliabilities(
        Decimal("0.60"), {"months_of_completed_actuals": 8, "cost_volatility_cov": "0.30"}
    )
    assert r2["owner_progress_eac"] == "medium"
    assert r2["trend_projection_eac"] == "medium"
    # high volatility -> trend low even with enough months.
    r3 = rb._asof_reliabilities(
        Decimal("0.60"), {"months_of_completed_actuals": 8, "cost_volatility_cov": "0.90"}
    )
    assert r3["trend_projection_eac"] == "low"


def test_asof_estimates_carry_supplied_reliability():
    m = {
        "actual_to_t": Decimal("50000"),
        "erp_projected": Decimal("90000"),
        "owner_pct_to_t": Decimal("0.40"),
        "burn_to_t": Decimal("10000"),
        "remaining_months": Decimal("5"),
        "committed_costs": Decimal("80000"),
    }
    rels = {
        "owner_progress_eac": "low",
        "trend_projection_eac": "medium",
        "commitment_exposure_eac": "low",
        "cpi_blend_eac": "low",
    }
    ests = rb._asof_estimates(m, rels)
    by = {e["method"]: e["reliability"] for e in ests}
    assert by["owner_progress_eac"] == "low"
    assert by["trend_projection_eac"] == "medium"


def _owner_row(period_to, pct):
    return {
        "period_to": period_to,
        "application_no": period_to,
        "percent_complete": pct,
        "total_completed_and_stored_to_date": None,
        "this_period_completed": None,
    }


def _near_complete_ctx(key="0000.10-20-030.SUB"):
    # 4 owner snapshots spanning 40/60/80/97%; 4 completed months of even burn.
    months = ["2025-01", "2025-02", "2025-03", "2025-04"]
    monthly = [
        {
            "month": m,
            "amount_decimal_string": "25000.00",
            "actual_period_bucket": "through_may_2026",
        }
        for m in months
    ]
    ctx = {
        "budget_code_key": key,
        "actuals": {"actual_cost_all_source_to_date": "100000.00", "monthly_actuals": monthly},
        "owner_pay_app": {"latest_percent_complete": "0.97"},
        "budget_amounts": {
            "projected_costs": "100000.00",
            "revised_budget": "100000.00",
            "committed_costs": "90000.00",
        },
    }
    owner_rows = [
        _owner_row("2025-01-31", "0.40"),
        _owner_row("2025-02-28", "0.60"),
        _owner_row("2025-03-31", "0.80"),
        _owner_row("2025-04-30", "0.97"),
    ]
    return ctx, {key: owner_rows}


METHOD_SUMMARY = [
    {"method": "commitment_exposure_eac", "mape": "0.0700"},
    {"method": "owner_progress_eac", "mape": "0.2500"},
]


def test_reconciled_backtest_scores_near_complete_code():
    ctx, owner = _near_complete_ctx()
    out = rb.run_reconciled_backtest([ctx], owner, "tropical", {}, METHOD_SUMMARY)
    assert out["cohort_size"] == 1
    assert out["observation_count"] >= 1
    assert out["reconciled_final_mape"] is not None
    assert out["worst_credible_coverage_rate"] is not None
    # best single method picked as the lowest-MAPE entry from the summary.
    assert out["best_single_method"] == "commitment_exposure_eac"
    assert out["best_single_method_mape"] == "0.0700"
    # detail rows present, sorted, and each ran the real select_final (basis present).
    assert out["detail_rows"]
    for d in out["detail_rows"]:
        assert d["reconciliation_basis"]
        assert d["realized_within_worst_ceiling"] in (True, False)


def test_reconciled_backtest_emits_recalibrated_block():
    ctx, owner = _near_complete_ctx()
    out = rb.run_reconciled_backtest([ctx], owner, "tropical", {}, METHOD_SUMMARY)
    r = out["recalibrated"]
    assert "recalibrated_final_mape" in r
    assert "mape_improvement" in r and "bias_abs_improvement" in r
    assert r["stage_gate_lo"] and r["stage_gate_hi"]
    for d in out["detail_rows"]:
        assert "recalibrated_recommended_final_cost" in d
        assert "recalibrated_abs_pct_error" in d


def test_reconciled_backtest_emits_damped_block():
    ctx, owner = _near_complete_ctx()
    out = rb.run_reconciled_backtest([ctx], owner, "tropical", {}, METHOD_SUMMARY)
    d = out["damped"]
    assert "damped_final_mape" in d
    assert "incremental_mape_improvement_over_recalibrated" in d
    assert "total_mape_improvement_over_baseline" in d
    assert d["damped_methods"] == ["owner_progress_eac", "trend_projection_eac"]
    for row in out["detail_rows"]:
        assert "damped_recommended_final_cost" in row
        assert "damped_abs_pct_error" in row


def test_reconciled_backtest_deterministic():
    ctx, owner = _near_complete_ctx()
    a = rb.run_reconciled_backtest([ctx], owner, "tropical", {}, METHOD_SUMMARY)
    b = rb.run_reconciled_backtest([ctx], owner, "tropical", {}, METHOD_SUMMARY)
    assert a == b


def test_reconciled_backtest_empty_cohort():
    # Not near-complete (owner < 0.95) -> excluded -> empty cohort, no crash.
    ctx, owner = _near_complete_ctx()
    ctx["owner_pay_app"]["latest_percent_complete"] = "0.50"
    out = rb.run_reconciled_backtest([ctx], owner, "tropical", {}, METHOD_SUMMARY)
    assert out["cohort_size"] == 0
    assert out["observation_count"] == 0
    assert out["reconciled_final_mape"] is None
