"""Confidence scoring (bounds, agreement, drivers) and backtest calibration."""
from construction_financial_review.forecast_accuracy import backtest as bt
from construction_financial_review.forecast_accuracy import confidence as cf


def _bundle(**over):
    b = {"project_key": "tropical", "budget_code_key": "k", "evidence_depth": 3,
         "latest_actual_month": "2026-05", "data_date": "2026-05-26", "burn_volatility_cov": "0.20"}
    b.update(over)
    return b


def _recon(n, divergence):
    return {"budget_code_key": "k", "n_independent_models": n, "model_divergence": divergence}


def test_confidence_in_unit_interval():
    out = cf.score_confidence(_bundle(), _recon(3, "0.10"))
    s = float(out["calibrated_confidence"])
    assert 0.0 <= s <= 1.0
    assert out["confidence_band"] in ("very_low", "low", "medium", "high", "very_high")


def test_higher_agreement_raises_confidence():
    low_div = cf.score_confidence(_bundle(), _recon(3, "0.05"))
    high_div = cf.score_confidence(_bundle(), _recon(3, "0.90"))
    assert float(low_div["calibrated_confidence"]) > float(high_div["calibrated_confidence"])


def test_sparse_evidence_lowers_confidence():
    rich = cf.score_confidence(_bundle(evidence_depth=5), _recon(3, "0.10"))
    sparse = cf.score_confidence(_bundle(evidence_depth=0), _recon(0, "0.00"))
    assert float(rich["calibrated_confidence"]) > float(sparse["calibrated_confidence"])


def test_drivers_listed():
    out = cf.score_confidence(_bundle(), _recon(3, "0.10"))
    assert set(out["confidence_drivers"]) == {"signal_density", "model_agreement",
                                              "data_recency", "burn_stability"}


def _ctx(key, actual, monthly, pct, committed=None, projected=None):
    return {
        "budget_code_key": key,
        "actuals": {"actual_cost_all_source_to_date": actual,
                    "monthly_actuals": [{"month": m, "amount_decimal_string": a,
                                         "actual_period_bucket": "through_may_2026"} for m, a in monthly]},
        "owner_pay_app": {"latest_percent_complete": pct},
        "budget_amounts": {"committed_costs": committed, "projected_costs": projected},
    }


def test_backtest_scores_methods_and_calibrates():
    # one near-complete code: owner reaches 1.0; mid-progress app at 0.6
    owner_hist = {"k": [
        {"period_to": "2026-01-25", "percent_complete": 0.30, "total_completed_and_stored_to_date": "300"},
        {"period_to": "2026-03-25", "percent_complete": 0.60, "total_completed_and_stored_to_date": "600"},
        {"period_to": "2026-05-25", "percent_complete": 1.00, "total_completed_and_stored_to_date": "1000"},
    ]}
    monthly = [("2026-01", "300"), ("2026-02", "150"), ("2026-03", "150"),
               ("2026-04", "200"), ("2026-05", "200")]
    ctx = _ctx("k", "1000.00", monthly, 1.00, committed="1000.00", projected="1000.00")
    res = bt.run_backtest([ctx], owner_hist, "tropical")
    assert res["cohort_size"] == 1
    # owner_percent_complete at 60% predicts ~ actual_to_T/0.6; calibration weights present
    methods = {m["method"]: m for m in res["summary_by_method"]}
    assert methods["owner_percent_complete"]["n"] == 1
    assert "owner_percent_complete" in res["calibration_weights"]
