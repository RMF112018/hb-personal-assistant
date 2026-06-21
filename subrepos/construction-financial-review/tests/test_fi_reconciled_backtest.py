"""Unit tests for the reconciled (production-forecast) as-of backtest."""

from __future__ import annotations

from construction_financial_review.forecast_intelligence import reconciled_backtest as rb


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
