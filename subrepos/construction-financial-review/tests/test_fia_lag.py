"""Priority 4 actual-cost lag diagnostics tests."""
from construction_financial_review.forecast_improvement_audit import lag

from tests._fia_fixtures import budget_entry, minimal_inputs

K_LAG = "1000.15-03-100.SUB"
K_OK = "1000.15-04-100.SUB"
K_NONE = "1000.15-05-100.SUB"


def _inputs():
    return minimal_inputs(
        budget_by_key={
            K_LAG: budget_entry(K_LAG, "15-03-100", "x", costentries_total_amount="0"),
            K_OK: budget_entry(K_OK, "15-04-100", "y", costentries_total_amount="50000"),
            K_NONE: budget_entry(K_NONE, "15-05-100", "z", costentries_total_amount="0"),
        },
        trend_by_key={
            K_LAG: {"recency_gap_months": 5, "late_cost_emergence": False,
                    "months_of_completed_actuals": 4},
            K_OK: {"recency_gap_months": 0, "late_cost_emergence": False,
                   "months_of_completed_actuals": 6},
        },
        latest_sub_invoice_by_key={
            K_LAG: {"latest_work_completed_this_period": "12000", "latest_billing_date": "2026-05-15"}},
        sched_evidence_by_key={
            K_LAG: {"open_activity_count": 3, "schedule_remaining_work_status": "remaining_work"}})


def test_lag_risk_flagged():
    rows, _ = lag.build(_inputs(), {})
    r = next(r for r in rows if r["budget_code_key"] == K_LAG)
    assert r["lag_risk"] is True
    assert "invoice_ahead_of_costentries" in r["lag_flags"]
    assert "schedule_active_no_actuals" in r["lag_flags"]
    assert r["actual_cost_inferred_from_indicators"] is False
    assert r["requires_human_acceptance"] is True


def test_no_lag_code_not_emitted():
    rows, _ = lag.build(_inputs(), {})
    assert all(r["budget_code_key"] != K_OK for r in rows)   # current actuals -> no row


def test_insufficient_evidence_gap():
    _, gaps = lag.build(_inputs(), {})
    assert any(g.get("budget_code_key") == K_NONE and g["gap_type"] == "insufficient_lag_evidence"
               for g in gaps)


def test_census_gap_present():
    _, gaps = lag.build(_inputs(), {})
    assert any(g["gap_type"] == "lag_classification_census" for g in gaps)
