"""Stronger backtest: multi as-of-T reconstruction, before/after mapping, excluded reasons."""

from decimal import Decimal

from construction_financial_review.forecast_intelligence import backtest_strong as bt


def _near_complete_ctx():
    monthly = [
        {
            "month": f"2025-{m:02d}",
            "amount_decimal_string": "60000",
            "actual_period_bucket": "through_may_2026",
        }
        for m in range(1, 9)
    ]
    return {
        "budget_code_key": "1000.10-01-100.SUB",
        "actuals": {"actual_cost_all_source_to_date": "500000", "monthly_actuals": monthly},
        "owner_pay_app": {"latest_percent_complete": "0.98"},
        "budget_amounts": {"committed_costs": "480000", "projected_costs": "500000"},
    }


def _incomplete_ctx():
    return {
        "budget_code_key": "1000.20-01-200.SUB",
        "actuals": {"actual_cost_all_source_to_date": "300000", "monthly_actuals": []},
        "owner_pay_app": {"latest_percent_complete": "0.40"},
        "budget_amounts": {},
    }


OWNER_HISTORY = {
    "1000.10-01-100.SUB": [
        {"period_to": "2025-02-28", "percent_complete": "0.20"},
        {"period_to": "2025-04-30", "percent_complete": "0.40"},
        {"period_to": "2025-06-30", "percent_complete": "0.60"},
        {"period_to": "2025-08-31", "percent_complete": "0.98"},
    ]
}


def test_structure_and_cohort():
    res = bt.run_strong_backtest(
        [_near_complete_ctx(), _incomplete_ctx()], OWNER_HISTORY, "tropical"
    )
    for k in (
        "summary_by_method",
        "calibration_weights",
        "before_after_by_method",
        "cohort_breakdown_by_division",
        "cohort_breakdown_by_family",
        "excluded_rows",
        "detail_rows",
        "methodology",
    ):
        assert k in res
    assert res["cohort_size"] >= 1
    assert res["excluded_rows"].get("not_near_complete") == 1


def test_multi_asof_targets_used():
    res = bt.run_strong_backtest([_near_complete_ctx()], OWNER_HISTORY, "tropical")
    targets = {row["asof_target"] for row in res["detail_rows"]}
    assert len(targets) >= 2  # reconstructed at multiple as-of points


def test_before_after_semantic_mapping():
    prior = [
        {"method": "owner_percent_complete", "mape": "0.10"},
        {"method": "burn_rate", "mape": "1.00"},
    ]
    res = bt.run_strong_backtest([_near_complete_ctx()], OWNER_HISTORY, "tropical", prior)
    ba = {r["method"]: r for r in res["before_after_by_method"]}
    assert ba["owner_progress_eac"]["prior_method"] == "owner_percent_complete"
    assert ba["owner_progress_eac"]["prior_mape"] == "0.10"
    assert ba["trend_projection_eac"]["prior_method"] == "burn_rate"


def test_calibration_method_set_unchanged():
    # procore is reconstructable but must NOT enter the calibration set (would change production).
    assert bt.METHODS == (
        "owner_progress_eac",
        "trend_projection_eac",
        "commitment_exposure_eac",
        "cpi_blend_eac",
    )


def test_procore_pct_asof_per_commitment_latest_summed():
    rows = [
        {
            "period_end": "2025-01-25",
            "commitment_id": 1,
            "total_completed_and_stored_to_date": "40000",
            "scheduled_value": "100000",
        },
        {
            "period_end": "2025-03-25",
            "commitment_id": 1,
            "total_completed_and_stored_to_date": "70000",
            "scheduled_value": "100000",
        },
        {
            "period_end": "2025-02-25",
            "commitment_id": 2,
            "total_completed_and_stored_to_date": "20000",
            "scheduled_value": "50000",
        },
    ]
    # as-of 2025-02: commit1 latest<=feb = 40k/100k, commit2 = 20k/50k -> 60k/150k = 0.40
    assert bt._procore_pct_asof(rows, "2025-02") == Decimal("0.4")
    # as-of 2025-03: commit1 = 70k, commit2 = 20k -> 90k/150k = 0.60
    assert bt._procore_pct_asof(rows, "2025-03") == Decimal("0.6")
    # before any period -> None; empty -> None
    assert bt._procore_pct_asof(rows, "2024-12") is None
    assert bt._procore_pct_asof([], "2025-03") is None


def test_procore_pct_asof_capped_at_one():
    rows = [
        {
            "period_end": "2025-01-25",
            "commitment_id": 1,
            "total_completed_and_stored_to_date": "120000",
            "scheduled_value": "100000",
        }
    ]
    assert bt._procore_pct_asof(rows, "2025-01") == Decimal("1")
