"""EAC estimators: floor-to-actuals, applicability gates, near-complete burn gate."""
from construction_financial_review.forecast_accuracy import estimators as es


def _bundle(**over):
    b = {
        "actual_cost_all_source_to_date": "100.00",
        "projected_costs": "120.00",
        "estimated_cost_at_completion": "125.00",
        "revised_budget": "200.00",
        "erp_job_to_date_costs": "100.00",
        "committed_costs": None,
        "commitment_invoiced": None,
        "commitment_pipeline_ratio": None,
        "avg_monthly_burn": "10.00",
        "burn_window_months": 6,
        "burn_volatility_cov": "0.20",
        "remaining_months_project": "5.00",
        "remaining_months_schedule": None,
        "owner_latest_percent_complete": None,
        "owner_mapping_status": "none",
        "schedule_mapping_status": "none",
        "schedule_open_activity_count": 0,
        "schedule_remaining_duration_days": None,
        "schedule_remaining_work_status": "no_schedule_evidence",
    }
    b.update(over)
    return b


def test_baseline_projected_floors_to_actuals():
    e = es.baseline_projected(_bundle(projected_costs="50.00", actual_cost_all_source_to_date="100.00"))
    assert e["applicable"] and e["eac"] == "100.00" and e["floored_to_actuals"] is True


def test_burn_rate_basic():
    e = es.burn_rate(_bundle())
    assert e["applicable"] and e["eac"] == "150.00"   # 100 + 10*5


def test_burn_rate_gated_for_near_complete_owner():
    e = es.burn_rate(_bundle(owner_latest_percent_complete=0.97, owner_mapping_status="mapped"))
    assert e["applicable"] is False                    # essentially complete -> no extrapolation


def test_burn_rate_gated_for_schedule_complete():
    e = es.burn_rate(_bundle(schedule_remaining_work_status="complete"))
    assert e["applicable"] is False


def test_owner_percent_complete():
    e = es.owner_percent_complete(_bundle(owner_mapping_status="mapped",
                                          owner_latest_percent_complete=0.50,
                                          actual_cost_all_source_to_date="100.00"))
    assert e["applicable"] and e["eac"] == "200.00"    # 100 / 0.50


def test_owner_percent_complete_full_is_actual():
    e = es.owner_percent_complete(_bundle(owner_mapping_status="mapped",
                                          owner_latest_percent_complete=1.0))
    assert e["eac"] == "100.00"


def test_commitment_floor_is_max():
    e = es.commitment_floor(_bundle(committed_costs="300.00", erp_job_to_date_costs="100.00"))
    assert e["applicable"] and e["eac"] == "300.00"


def test_commitment_floor_never_below_actuals():
    e = es.commitment_floor(_bundle(committed_costs="50.00", erp_job_to_date_costs="40.00",
                                    actual_cost_all_source_to_date="100.00"))
    assert e["eac"] == "100.00"                         # floored to actuals


def test_schedule_etc_uses_remaining_duration():
    e = es.schedule_etc(_bundle(schedule_mapping_status="mapped", schedule_open_activity_count=5,
                                schedule_remaining_duration_days="21.67"))
    assert e["applicable"] and e["eac"] == "110.00"     # 100 + 10 * (21.67/21.67)


def test_estimate_all_returns_all_methods_floored():
    rows = es.estimate_all(_bundle(committed_costs="300.00"))
    methods = {r["method"] for r in rows}
    assert methods == set(es.ERP_METHODS) | set(es.INDEPENDENT_METHODS)
    for r in rows:
        if r["applicable"]:
            assert float(r["eac"]) >= 100.0             # >= actual
